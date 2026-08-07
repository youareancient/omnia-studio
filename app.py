import asyncio
import json
import os
import re
import uuid
import edge_tts
from aiohttp import web, ClientSession, FormData

HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", 7860))
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()

STUDIO_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(STUDIO_DIR, "public")
DOWNLOADS_DIR = os.path.join(STATIC_DIR, "generated")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

INDEX_HTML_PATH = os.path.join(STATIC_DIR, "index.html")

MASTER_THUMBNAIL_PROMPT_TEMPLATE = """Generate a premium-quality, designer-level 16:9 image based on the video title: "{VIDEO_TITLE}". The thumbnail should instantly communicate the business, brand, industry, product, or concept mentioned in the title while emphasizing its money, investment, costs, revenue, profitability, and business economics. At the very top, create an oversized, bold, uppercase headline derived directly from the video title using a clean sans-serif font. The headline should occupy approximately the top 30–40% of the canvas with strong hierarchy and maximum readability. Keep the wording extremely short by extracting only the most impactful words from the title (for example: "SO YOU WANT TO OWN A RESTAURANT", "BUY A HOTEL", "OPEN A COFFEE SHOP", "BUILD A TESLA FACTORY", "RUN A YOUTUBE CHANNEL", etc.). Use solid black typography on a clean white background with generous spacing and a thin red underline beneath the headline to create a strong visual divider. Directly below the headline, place a professionally illustrated, highly recognizable hero scene representing the business or subject from the title. If the title references a company, depict its signature products, headquarters, stores, ecosystem, or branding cues without copying copyrighted artwork exactly. If it references an industry, show its most recognizable environment, equipment, architecture, vehicles, products, or operations. The central illustration should feel like a polished editorial infographic with clean perspective, premium lighting, realistic proportions, crisp outlines, subtle shadows, vibrant yet controlled colors, and an overall handcrafted digital illustration style that resembles artwork created by a professional thumbnail designer rather than AI. Surround the main subject with only 6–10 carefully selected business or financial callouts, each connected by elegant hand-drawn arrows pointing toward the relevant area of the illustration. Every label should be handwritten-style black text with a simple red underline, positioned cleanly around the composition without clutter. The labels must be intelligently generated from the video title and should represent topics such as startup costs, capital investment, infrastructure, equipment, employees, operations, manufacturing, supply chain, logistics, maintenance, utilities, marketing, branding, advertising, licensing, inventory, software, technology, customer acquisition, subscriptions, labor, regulations, insurance, taxes, scalability, competition, revenue streams, cash flow, margins, pricing, profitability, ROI, risks, or other concepts that naturally fit the subject. Never use generic or irrelevant labels, generate them dynamically so they accurately match the specific business or brand in the title. Include a few clean supporting objects that reinforce the economics theme, such as stacks of cash, coins, profit charts, invoices, machinery, products, customers, vehicles, tools, factory equipment, storefront items, digital dashboards, or service icons, but only when they naturally fit the topic. Every supporting element should help explain where money is spent or earned, creating an immediate "business breakdown" visual. Maintain a spacious composition with plenty of white space, avoiding unnecessary decorations, excessive text, busy backgrounds, glowing effects, lens flares, random icons, stickers, or visual noise. The thumbnail should look modern, premium, educational, highly clickable, and trustworthy, with a clean infographic aesthetic suitable for finance, entrepreneurship, business case studies, economics, and documentary-style YouTube content. Prioritize excellent composition, perfect typography, consistent spacing, sharp edges, high contrast, accurate visual storytelling, and flawless readability even on mobile devices. The final output should appear as if it were designed by an experienced professional YouTube thumbnail artist."""

VOICE_PRESETS = {
    "andrew": {"id": "en-US-AndrewNeural", "name": "Andrew (YouTube Documentary)", "desc": "High energy, warm & engaging (Recommended for YouTube monetization)"},
    "christopher": {"id": "en-US-ChristopherNeural", "name": "Christopher (Deep Storyteller)", "desc": "Deep, authoritative, cinematic business tone"},
    "ava": {"id": "en-US-AvaNeural", "name": "Ava (Modern Expressive)", "desc": "Clear, modern, expressive narrator voice"},
    "guy": {"id": "en-US-GuyNeural", "name": "Guy (News & Commentary)", "desc": "Clear American news broadcaster style"}
}

# Global Background Jobs Dictionary
BACKGROUND_JOBS = {}

def humanize_text_for_speech(text):
    lines = [line.strip() for line in text.strip().split('\n')]
    paragraphs = []
    current_para = []
    
    for line in lines:
        if not line:
            if current_para:
                paragraphs.append(" ".join(current_para))
                current_para = []
        else:
            current_para.append(line)
            
    if current_para:
        paragraphs.append(" ".join(current_para))
        
    humanized_text = "\n\n".join(paragraphs)
    humanized_text = re.sub(r'\.{3,}', '...', humanized_text)
    return humanized_text, paragraphs

def extract_video_title(text, custom_filename=""):
    if custom_filename:
        title = custom_filename.replace('.mp3', '').replace('_', ' ').replace('-', ' ').title()
        if len(title) > 5:
            return title
    
    lines = [line.strip() for line in text.strip().split('\n') if line.strip()]
    if lines:
        first_line = lines[0]
        words = first_line.split()[:10]
        return " ".join(words).upper()
    return "YOUR VIDEO TITLE"

async def process_job_async(job_id, raw_text, voice_preset, rate, filename, mode):
    try:
        BACKGROUND_JOBS[job_id] = {
            "status": "processing",
            "progress": 5,
            "status_text": "Humanizing script...",
            "mode": mode,
            "result": None
        }

        voice_info = VOICE_PRESETS.get(voice_preset, VOICE_PRESETS["andrew"])
        voice_id = voice_info["id"]

        full_humanized_text, paragraphs = humanize_text_for_speech(raw_text)
        total_paras = len(paragraphs)

        video_title = extract_video_title(raw_text, filename)
        thumbnail_prompt = MASTER_THUMBNAIL_PROMPT_TEMPLATE.replace("{VIDEO_TITLE}", video_title)

        if mode == "thumbnail":
            BACKGROUND_JOBS[job_id] = {
                "status": "completed",
                "progress": 100,
                "status_text": "Thumbnail Master Prompt generated!",
                "mode": "thumbnail",
                "result": {
                    "videoTitle": video_title,
                    "thumbnailPrompt": thumbnail_prompt
                }
            }
            return

        if not filename:
            filename = f"voiceover_{voice_preset}_{job_id[:6]}.mp3"
        elif not filename.endswith(".mp3"):
            filename += ".mp3"

        base_name = os.path.splitext(filename)[0]
        srt_filename = f"{base_name}.srt"

        out_filepath = os.path.join(DOWNLOADS_DIR, filename)
        srt_filepath = os.path.join(DOWNLOADS_DIR, srt_filename)

        temp_chunks = []
        temp_dir = os.path.join(STUDIO_DIR, "temp_chunks")
        os.makedirs(temp_dir, exist_ok=True)
        submaker = edge_tts.SubMaker()

        for i, para in enumerate(paragraphs, start=1):
            if not para.strip():
                continue
            
            chunk_path = os.path.join(temp_dir, f"chunk_{uuid.uuid4().hex}.mp3")
            communicate = edge_tts.Communicate(para, voice_id, rate=rate, pitch="+0Hz")
            
            with open(chunk_path, "wb") as f:
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        f.write(chunk["data"])
                    elif chunk["type"] == "WordBoundary":
                        submaker.feed(chunk)

            temp_chunks.append(chunk_path)

            progress_pct = int((i / total_paras) * 90) + 5
            BACKGROUND_JOBS[job_id]["progress"] = progress_pct
            BACKGROUND_JOBS[job_id]["status_text"] = f"Synthesizing paragraph {i} of {total_paras} ({progress_pct}%)..."

        if mode == "audio":
            BACKGROUND_JOBS[job_id]["progress"] = 96
            BACKGROUND_JOBS[job_id]["status_text"] = "Merging audio tracks into HD MP3..."

            with open(out_filepath, "wb") as outfile:
                for chunk_file in temp_chunks:
                    with open(chunk_file, "rb") as infile:
                        outfile.write(infile.read())

            BACKGROUND_JOBS[job_id] = {
                "status": "completed",
                "progress": 100,
                "status_text": "Voiceover MP3 generated successfully!",
                "mode": "audio",
                "result": {
                    "filename": filename,
                    "audioUrl": f"/static/generated/{filename}",
                    "wordCount": len(full_humanized_text.split()),
                    "videoTitle": video_title,
                    "thumbnailPrompt": thumbnail_prompt
                }
            }
        else: # mode == "srt"
            BACKGROUND_JOBS[job_id]["progress"] = 96
            BACKGROUND_JOBS[job_id]["status_text"] = "Generating .SRT subtitle timestamps..."

            srt_content = submaker.get_srt()
            with open(srt_filepath, "w", encoding="utf-8") as srt_file:
                srt_file.write(srt_content)

            BACKGROUND_JOBS[job_id] = {
                "status": "completed",
                "progress": 100,
                "status_text": ".SRT Subtitles generated successfully!",
                "mode": "srt",
                "result": {
                    "srtFilename": srt_filename,
                    "srtUrl": f"/static/generated/{srt_filename}",
                    "wordCount": len(full_humanized_text.split()),
                    "videoTitle": video_title,
                    "thumbnailPrompt": thumbnail_prompt
                }
            }

        for chunk_file in temp_chunks:
            try:
                os.remove(chunk_file)
            except Exception:
                pass

    except Exception as e:
        print(f"Error processing job {job_id}:", e)
        BACKGROUND_JOBS[job_id] = {
            "status": "failed",
            "progress": 0,
            "status_text": f"Error: {str(e)}",
            "mode": mode,
            "result": None
        }

async def handle_index(request):
    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0"
    }
    if os.path.exists(INDEX_HTML_PATH):
        with open(INDEX_HTML_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        return web.Response(text=content, content_type="text/html", charset="utf-8", headers=headers)
    return web.Response(text="<h1>YouTube Voiceover Studio</h1><p>Initializing...</p>", content_type="text/html", headers=headers)

async def handle_voices(request):
    return web.json_response(VOICE_PRESETS)

async def handle_start_job(request):
    try:
        data = await request.json()
        raw_text = data.get("text", "").strip()
        voice_preset = data.get("voice", "andrew")
        rate = data.get("rate", "+1%")
        filename = data.get("filename", "").strip()
        mode = data.get("mode", "audio")

        if not raw_text:
            return web.json_response({"error": "Script text cannot be empty"}, status=400)

        job_id = str(uuid.uuid4())
        asyncio.create_task(process_job_async(job_id, raw_text, voice_preset, rate, filename, mode))

        return web.json_response({"job_id": job_id, "status": "processing"})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

async def handle_job_status(request):
    job_id = request.query.get("id", "").strip()
    if not job_id or job_id not in BACKGROUND_JOBS:
        return web.json_response({"error": "Job not found"}, status=404)

    return web.json_response(BACKGROUND_JOBS[job_id])

async def handle_telegram_webhook(request):
    token = TELEGRAM_BOT_TOKEN or os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        return web.Response(text="Telegram Bot Token not configured", status=400)

    try:
        data = await request.json()
        message = data.get("message") or data.get("edited_message")
        if not message:
            return web.Response(text="OK")

        chat_id = message.get("chat", {}).get("id")
        text = message.get("text", "").strip()

        if not text or not chat_id:
            return web.Response(text="OK")

        if text.startswith("/start"):
            welcome_msg = (
                "🎙️ *Welcome to YouTube Voiceover Bot!*\n\n"
                "Simply send or paste any script text to this bot, and I will generate an HD humanized voiceover MP3 using Andrew's voice!"
            )
            async with ClientSession() as session:
                await session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={
                    "chat_id": chat_id,
                    "text": welcome_msg,
                    "parse_mode": "Markdown"
                })
            return web.Response(text="OK")

        async with ClientSession() as session:
            await session.post(f"https://api.telegram.org/bot{token}/sendMessage", json={
                "chat_id": chat_id,
                "text": "⚡ Processing script and generating HD Voiceover MP3..."
            })

        humanized_text, paragraphs = humanize_text_for_speech(text)
        out_filename = f"voiceover_tg_{uuid.uuid4().hex[:6]}.mp3"
        out_filepath = os.path.join(DOWNLOADS_DIR, out_filename)

        communicate = edge_tts.Communicate(humanized_text, "en-US-AndrewNeural", rate="+1%", pitch="+0Hz")
        await communicate.save(out_filepath)

        async with ClientSession() as session:
            form = FormData()
            form.add_field("chat_id", str(chat_id))
            form.add_field("caption", f"🎙️ Voiceover generated for: {humanized_text[:40]}...")
            form.add_field("audio", open(out_filepath, "rb"), filename=out_filename)

            await session.post(f"https://api.telegram.org/bot{token}/sendAudio", data=form)

    except Exception as e:
        print("Telegram error:", e)

    return web.Response(text="OK")

def create_app():
    app = web.Application()
    app.router.add_get("", handle_index)
    app.router.add_get("/", handle_index)
    app.router.add_get("/index.html", handle_index)
    app.router.add_post("/api/start-job", handle_start_job)
    app.router.add_get("/api/job-status", handle_job_status)
    app.router.add_get("/api/voices", handle_voices)
    app.router.add_post("/telegram-webhook", handle_telegram_webhook)
    app.router.add_static("/static/", STATIC_DIR)
    return app

if __name__ == "__main__":
    print(f"Starting YouTube Voiceover Studio Online at http://{HOST}:{PORT}")
    web.run_app(create_app(), host=HOST, port=PORT)
