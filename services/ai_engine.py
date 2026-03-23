"""
services/ai_engine.py
The heart of Flareposts — takes any content and produces
6 platform-ready posts using the Google Gemini API (free).
"""

import re
import aiohttp
import google.generativeai as genai
from bs4 import BeautifulSoup
from config import GEMINI_KEY

genai.configure(api_key=GEMINI_KEY)
gemini = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    system_instruction=None,  # injected per-call below
)

# ── Content extraction ────────────────────────────────────────────

async def extract_from_url(url: str) -> str:
    """Fetch a webpage and extract its main text content."""
    headers = {"User-Agent": "Mozilla/5.0 (compatible; FlarepostsBot/1.0)"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                html = await resp.text()
        soup = BeautifulSoup(html, "html.parser")

        # Remove junk tags
        for tag in soup(["script","style","nav","footer","header","aside","form","iframe"]):
            tag.decompose()

        # Try to get article body first
        for sel in ["article", "main", ".post-content", ".article-body", "#content"]:
            el = soup.select_one(sel)
            if el:
                text = el.get_text(separator="\n", strip=True)
                if len(text) > 300:
                    return text[:6000]

        # Fallback to all body text
        text = soup.body.get_text(separator="\n", strip=True) if soup.body else soup.get_text()
        return text[:6000]
    except Exception as e:
        raise ValueError(f"Couldn't fetch that URL: {e}")


async def extract_youtube_transcript(url: str) -> str:
    """
    Extract YouTube video title + description as content seed.
    For full transcripts, youtube-transcript-api can be added.
    """
    try:
        # Extract video ID
        vid_id = None
        for pattern in [r"v=([^&]+)", r"youtu\.be/([^?]+)", r"shorts/([^?]+)"]:
            m = re.search(pattern, url)
            if m:
                vid_id = m.group(1)
                break

        if not vid_id:
            raise ValueError("Invalid YouTube URL")

        # Try to get transcript via youtube-transcript-api
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            transcript = YouTubeTranscriptApi.get_transcript(vid_id)
            text = " ".join([t["text"] for t in transcript])
            return text[:6000]
        except Exception:
            pass

        # Fallback: fetch oEmbed for title/description
        oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={vid_id}&format=json"
        async with aiohttp.ClientSession() as session:
            async with session.get(oembed_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                data = await resp.json()
        title  = data.get("title", "")
        author = data.get("author_name", "")
        return f"YouTube Video: {title}\nBy: {author}\nVideo ID: {vid_id}"

    except Exception as e:
        raise ValueError(f"Couldn't process that YouTube link: {e}")


def is_youtube_url(text: str) -> bool:
    return bool(re.search(r"(youtube\.com|youtu\.be)", text))


def is_url(text: str) -> bool:
    return bool(re.match(r"https?://", text.strip()))


# ── AI Generation ─────────────────────────────────────────────────

SYSTEM_PROMPT = """You are Flareposts, an expert content repurposing AI.
Your job: take ANY content and transform it into 6 platform-ready social media posts.
Each post must feel native to its platform — not copy-pasted.
You always return structured output with clear headers.
You write in a natural, engaging, human tone — never robotic or generic.
Make the content punchy, specific, and shareable."""

GENERATION_PROMPT = """Here is the source content:

\"\"\"
{content}
\"\"\"

Transform this into 6 platform-optimized posts. Use this EXACT format:

---TWITTER---
[A punchy Twitter/X thread. Start with a hook tweet, then 4-6 numbered tweets (use 1/ 2/ 3/ etc.), end with a CTA tweet. Max 280 chars per tweet. Use line breaks between tweets.]

---LINKEDIN---
[A professional LinkedIn post. Start with a bold opening line (no "I'm excited to share"). Tell a story or share an insight. 150-300 words. Use line breaks for readability. End with a question to drive comments.]

---INSTAGRAM---
[An Instagram caption. Engaging opener, 3-5 sentences of value, 5 relevant hashtags at the end. Conversational and visual in language.]

---YOUTUBE---
[A YouTube video description. SEO-optimized title suggestion on first line, then a 100-word description, then 5 tags separated by commas.]

---EMAIL---
[An email newsletter hook. Subject line on first line (format: Subject: ...), then a short 80-word email that teases the content and ends with a CTA button text in brackets like [Read More]]

---TIKTOK---
[A TikTok/Reels script. Hook (first 3 seconds), main content in short punchy sentences (15-30 seconds), CTA. Format it as a spoken script with [action] notes.]

Keep each section self-contained and genuinely useful. Make it feel human-written."""


async def generate_content(raw_input: str) -> dict:
    """
    Main entry point. Accepts URL, YouTube link, or plain text.
    Returns dict with source_summary + 6 platform posts.
    """
    # Step 1: Extract content
    source_type = "text"
    if is_youtube_url(raw_input):
        content = await extract_youtube_transcript(raw_input)
        source_type = "youtube"
    elif is_url(raw_input):
        content = await extract_from_url(raw_input)
        source_type = "url"
    else:
        content = raw_input
        source_type = "text"

    if len(content.strip()) < 30:
        raise ValueError("Content is too short to work with. Please provide more text.")

    # Step 2: Generate with Gemini (free)
    full_prompt = SYSTEM_PROMPT + "\n\n" + GENERATION_PROMPT.format(content=content[:5000])
    response    = gemini.generate_content(full_prompt)
    raw_output  = response.text

    # Step 3: Parse sections
    sections = {}
    platforms = ["TWITTER", "LINKEDIN", "INSTAGRAM", "YOUTUBE", "EMAIL", "TIKTOK"]
    for i, platform in enumerate(platforms):
        start_tag = f"---{platform}---"
        end_tag   = f"---{platforms[i+1]}---" if i + 1 < len(platforms) else None

        start = raw_output.find(start_tag)
        if start == -1:
            sections[platform] = "⚠️ Could not generate this section."
            continue

        start += len(start_tag)
        end = raw_output.find(end_tag) if end_tag else len(raw_output)
        sections[platform] = raw_output[start:end].strip()

    return {
        "source_type": source_type,
        "platforms": sections,
        "raw": raw_output,
    }
