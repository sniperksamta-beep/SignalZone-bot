"""
services/ai_engine.py — Flareposts AI engine using Gemini REST API directly.
No library version issues — pure HTTP calls.
"""

import re
import aiohttp
from bs4 import BeautifulSoup
from config import GROQ_KEY

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


async def extract_from_url(url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; FlarepostsBot/1.0)"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                html = await resp.text()
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script","style","nav","footer","header","aside","form","iframe"]):
            tag.decompose()
        for sel in ["article", "main", ".post-content", ".article-body", "#content"]:
            el = soup.select_one(sel)
            if el:
                text = el.get_text(separator="\n", strip=True)
                if len(text) > 300:
                    return text[:6000]
        text = soup.body.get_text(separator="\n", strip=True) if soup.body else soup.get_text()
        return text[:6000]
    except Exception as e:
        raise ValueError(f"Couldn't fetch that URL: {e}")

async def extract_youtube_transcript(url: str) -> str:
    try:
        vid_id = None
        for pattern in [r"v=([^&]+)", r"youtu\.be/([^?]+)", r"shorts/([^?]+)"]:
            m = re.search(pattern, url)
            if m:
                vid_id = m.group(1)
                break
        if not vid_id:
            raise ValueError("Invalid YouTube URL")
        oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={vid_id}&format=json"
        async with aiohttp.ClientSession() as session:
            async with session.get(oembed_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                data = await resp.json()
        return f"YouTube Video: {data.get('title','')}\nBy: {data.get('author_name','')}"
    except Exception as e:
        raise ValueError(f"Couldn't process that YouTube link: {e}")

def is_youtube_url(text: str) -> bool:
    return bool(re.search(r"(youtube\.com|youtu\.be)", text))

def is_url(text: str) -> bool:
    return bool(re.match(r"https?://", text.strip()))

PROMPT_TEMPLATE = """You are Flareposts, an expert content repurposing AI.
Transform the content below into 6 platform-ready social media posts.

SOURCE CONTENT:
{content}

Use this EXACT format:

---TWITTER---
[Twitter/X thread. Hook tweet, 4-6 numbered tweets, CTA. Max 280 chars each.]

---LINKEDIN---
[LinkedIn post. Bold opener, insight, 150-300 words, end with question.]

---INSTAGRAM---
[Instagram caption. Opener, 3-5 sentences, 5 hashtags.]

---YOUTUBE---
[YouTube description. SEO title, 100-word description, 5 tags.]

---EMAIL---
[Email. Subject: ... on first line, 80-word body, CTA in brackets.]

---TIKTOK---
[TikTok script. Hook, main content, CTA with [action] notes.]"""

async def generate_content(raw_input: str) -> dict:
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
        raise ValueError("Content is too short. Please provide more text.")

    payload = {
        "contents": [{"parts": [{"text": PROMPT_TEMPLATE.format(content=content[:5000])}]}],
        "generationConfig": {"temperature": 0.8, "maxOutputTokens": 3000}
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            GEMINI_URL, json=payload,
            headers={"Content-Type": "application/json"},
            timeout=aiohttp.ClientTimeout(total=60)
        ) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                raise ValueError(f"Gemini API error {resp.status}: {error_text[:300]}")
            data = await resp.json()

    raw_output = data["candidates"][0]["content"]["parts"][0]["text"]

    sections = {}
    platforms = ["TWITTER", "LINKEDIN", "INSTAGRAM", "YOUTUBE", "EMAIL", "TIKTOK"]
    for i, platform in enumerate(platforms):
        start_tag = f"---{platform}---"
        end_tag = f"---{platforms[i+1]}---" if i + 1 < len(platforms) else None
        start = raw_output.find(start_tag)
        if start == -1:
            sections[platform] = "Could not generate this section."
            continue
        start += len(start_tag)
        end = raw_output.find(end_tag) if end_tag else len(raw_output)
        sections[platform] = raw_output[start:end].strip()

    return {"source_type": source_type, "platforms": sections, "raw": raw_output}
