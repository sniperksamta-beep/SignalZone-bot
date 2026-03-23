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
                html = await resp.text(encoding="utf-8", errors="replace")
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script","style","nav","footer","header","aside","form","iframe"]):
            tag.decompose()
        for sel in ["article", "main", ".post-content", ".article-body", "#content", ".content", ".entry-content"]:
            el = soup.select_one(sel)
            if el:
                text = el.get_text(separator="\n", strip=True)
                if len(text) > 200:
                    return text[:6000]
        text = soup.body.get_text(separator="\n", strip=True) if soup.body else soup.get_text()
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        return "\n".join(lines)[:6000]
    except Exception as e:
        raise ValueError(f"تعذّر جلب الرابط: {e}")


async def extract_youtube_transcript(url: str) -> str:
    try:
        vid_id = None
        for pattern in [r"v=([^&]+)", r"youtu\.be/([^?&]+)", r"shorts/([^?]+)"]:
            m = re.search(pattern, url)
            if m:
                vid_id = m.group(1)
                break
        if not vid_id:
            raise ValueError("رابط يوتيوب غير صالح")

        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            for lang in [["ar"], ["en"], None]:
                try:
                    if lang:
                        transcript = YouTubeTranscriptApi.get_transcript(vid_id, languages=lang)
                    else:
                        transcript = YouTubeTranscriptApi.get_transcript(vid_id)
                    text = " ".join([t["text"] for t in transcript])
                    if len(text) > 100:
                        return text[:6000]
                except Exception:
                    continue
        except Exception:
            pass

        oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={vid_id}&format=json"
        async with aiohttp.ClientSession() as session:
            async with session.get(oembed_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                data = await resp.json()
        title  = data.get("title", "")
        author = data.get("author_name", "")
        if not title:
            raise ValueError("تعذّر الحصول على معلومات الفيديو.")
        return f"[معلومات محدودة — العنوان فقط، لا يوجد نص مفرغ]\nعنوان الفيديو: {title}\nالقناة: {author}\nالرابط: {url}"

    except Exception as e:
        raise ValueError(f"تعذّر معالجة رابط يوتيوب: {e}")


def is_youtube_url(text: str) -> bool:
    return bool(re.search(r"(youtube\.com|youtu\.be)", text))

def is_url(text: str) -> bool:
    return bool(re.match(r"https?://", text.strip()))


PROMPT_TEMPLATE = """أنت خبير في إعادة توظيف المحتوى للشبكات الاجتماعية.

القواعد الصارمة:
- استخدم التفاصيل والأسماء والأحداث الحقيقية الموجودة في المحتوى المصدر فقط
- لا تكتب أبدًا جملًا عامة مثل "اكتشف المزيد" أو "لا تفوّت" أو "تعلّم أكثر"
- لا تخترع تفاصيل غير موجودة في المصدر
- اكتب جميع المنشورات باللغة العربية
- إذا كانت المعلومات محدودة، كن صادقًا واذكر ما هو متاح فقط
- كل منشور يجب أن يذكر تفاصيل حقيقية ومحددة من المحتوى

المحتوى المصدر:
{content}

استخدم هذا التنسيق بالضبط — لا تضف أي نص قبله أو بعده:

---TWITTER---
[خيط تويتر/X. ابدأ بتغريدة جذّابة بتفصيلة حقيقية مثيرة، ثم 4-5 تغريدات مرقّمة (1/ 2/ 3/) كل منها بتفصيلة حقيقية من المحتوى. انتهِ بدعوة للتفاعل. الحد الأقصى 280 حرفًا لكل تغريدة.]

---LINKEDIN---
[منشور لينكدإن. ابدأ بأبرز نقطة محددة من المحتوى. 150-300 كلمة. انتهِ بسؤال للنقاش.]

---INSTAGRAM---
[تعليق إنستغرام. مقدمة جذّابة بتفصيلة حقيقية، 3-5 جمل، 5 هاشتاقات مناسبة في النهاية.]

---YOUTUBE---
[وصف يوتيوب. عنوان SEO محدد في السطر الأول، وصف 100 كلمة بتفاصيل حقيقية، ثم 5 كلمات مفتاحية.]

---EMAIL---
[بريد إلكتروني. الموضوع: ... في السطر الأول، ثم نص 80 كلمة بتفاصيل حقيقية، ودعوة للعمل بين قوسين.]

---TIKTOK---
[سكريبت تيك توك. خطّاف (3 ثوانٍ) بحقيقة مثيرة محددة، محتوى رئيسي (15-30 ثانية)، دعوة للعمل مع ملاحظات [action].]"""


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
        raise ValueError("المحتوى قصير جدًا. الرجاء إرسال نص أطول.")

    headers = {
        "Authorization": f"Bearer {GROQ_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {
                "role": "system",
                "content": "أنت خبير في إعادة توظيف المحتوى. تستخدم دائمًا التفاصيل الحقيقية من المصدر. لا تكتب أبدًا محتوى عامًا. تكتب جميع المنشورات باللغة العربية."
            },
            {
                "role": "user",
                "content": PROMPT_TEMPLATE.format(content=content[:5000])
            }
        ],
        "max_tokens": 3000,
        "temperature": 0.7
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            GROQ_URL, json=payload, headers=headers,
            timeout=aiohttp.ClientTimeout(total=60)
        ) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                raise ValueError(f"خطأ في Groq API {resp.status}: {error_text[:300]}")
            data = await resp.json()

    raw_output = data["choices"][0]["message"]["content"]

    sections = {}
    platforms = ["TWITTER", "LINKEDIN", "INSTAGRAM", "YOUTUBE", "EMAIL", "TIKTOK"]
    for i, platform in enumerate(platforms):
        start_tag = f"---{platform}---"
        end_tag = f"---{platforms[i+1]}---" if i + 1 < len(platforms) else None
        start = raw_output.find(start_tag)
        if start == -1:
            sections[platform] = "تعذّر توليد هذا القسم."
            continue
        start += len(start_tag)
        end = raw_output.find(end_tag) if end_tag else len(raw_output)
        sections[platform] = raw_output[start:end].strip()

    return {"source_type": source_type, "platforms": sections, "raw": raw_output}
