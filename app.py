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
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()

STUDIO_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(STUDIO_DIR, "public")
DOWNLOADS_DIR = os.path.join(STATIC_DIR, "generated")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

INDEX_HTML_PATH = os.path.join(STATIC_DIR, "index.html")

VOICE_PRESETS = {
    "andrew": {"id": "en-US-AndrewNeural", "name": "Andrew (YouTube Documentary)", "desc": "High energy, warm & engaging (Recommended for YouTube monetization)"},
    "christopher": {"id": "en-US-ChristopherNeural", "name": "Christopher (Deep Storyteller)", "desc": "Deep, authoritative, cinematic business tone"},
    "ava": {"id": "en-US-AvaNeural", "name": "Ava (Modern Expressive)", "desc": "Clear, modern, expressive narrator voice"},
    "guy": {"id": "en-US-GuyNeural", "name": "Guy (News & Commentary)", "desc": "Clear American news broadcaster style"}
}

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

def format_timestamp(ms):
    seconds = int(ms / 1000)
    minutes = int(seconds / 60)
    rem_sec = seconds % 60
    tenths = int((ms % 1000) / 100)
    return f"{minutes:02d}:{rem_sec:02d}.{tenths}"

async def call_groq_ai_prompt_engineer(scene_text, scene_number):
    api_key = GROQ_API_KEY or os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        return None

    system_prompt = (
        "You are an Elite 16:9 Visual Prompt Engineer for top educational YouTube channels like @misterfinanceyt and @TheWealthCortexx.\n"
        "Your task: Read a 3-5 second script line and create a stunning, long, highly-detailed 16:9 standalone image prompt packed with vibrant visual props, character poses, and visual humor.\n\n"
        "STRICT MASTER PROMPT PATTERN:\n"
        "Image Prompt - Hand-drawn professional educational 2D vector cartoon illustration in 16:9 widescreen aspect ratio, clean studio-quality digital vector artwork with thick, smooth black outlines, crisp linework, vibrant soft flat colors, and polished modern explainer-animation aesthetics inspired by @misterfinanceyt and @TheWealthCortexx. [Describe character pose, facial expression, and action on the left/center]. FEATURED VISUAL PROPS: [List 3-5 rich, specific, vibrant physical props, tech equipment, financial charts, glowing cables, coins, or meters relevant to the concept]. Above his head, a large white thought bubble with bold black outlines contains [describe a minimal 2D vector icon or silhouette]. Pure white background, generous negative space, balanced 16:9 composition, zero clutter, ultra-crisp 2D vector style --ar 16:9\n\n"
        "RULES:\n"
        "1. Do NOT repeat the script line verbatim. Write a rich, detailed visual description with characters & props.\n"
        "2. Always include FEATURED VISUAL PROPS with 3 to 5 vivid physical objects.\n"
        "3. Always end with '--ar 16:9'.\n\n"
        "OUTPUT FORMAT (JSON ONLY):\n"
        "{\"prompt\": \"Image Prompt - Hand-drawn professional educational 2D vector... --ar 16:9\"}"
    )

    user_prompt = f"Script Line (Scene {scene_number}): \"{scene_text}\""

    try:
        async with ClientSession() as session:
            payload = {
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.75,
                "response_format": {"type": "json_object"}
            }
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            async with session.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers, timeout=15) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    content = data["choices"][0]["message"]["content"]
                    parsed = json.loads(content)
                    return parsed.get("prompt")
    except Exception as e:
        print("Groq API Exception:", e)

    return None

def build_vector_art_scene_prompt_fallback(text):
    clean_text = text.strip()
    return (
        f"Image Prompt - Hand-drawn professional educational 2D vector cartoon illustration in 16:9 widescreen aspect ratio, "
        f"clean studio-quality digital vector artwork with thick, smooth black outlines, crisp linework, vibrant soft flat colors, "
        f"and polished modern explainer-animation aesthetics inspired by @misterfinanceyt and @TheWealthCortexx. "
        f"A relaxed character sitting in a chair daydreaming about {clean_text}. FEATURED VISUAL PROPS: glowing 3D golden coins, "
        f"a sleek black tech server rack with cyan LEDs, and a percentage chart board. Large white thought bubble overhead. "
        f"Pure white background, generous negative space, zero clutter, 2D vector style --ar 16:9"
    )

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

            progress_pct = int((i / total_paras) * 40) + 5
            BACKGROUND_JOBS[job_id]["progress"] = progress_pct
            BACKGROUND_JOBS[job_id]["status_text"] = f"Audio timing analysis ({progress_pct}%)..."

        if mode == "breakdown":
            BACKGROUND_JOBS[job_id]["progress"] = 50
            BACKGROUND_JOBS[job_id]["status_text"] = "STEP 1: Computing 3-5 second scene cuts from speech audio..."

            cues = submaker.cues
            scenes_raw = []
            
            if cues:
                curr_words = []
                start_ms = cues[0].start
                end_ms = cues[0].end
                
                for cue in cues:
                    word = cue.text.strip()
                    curr_words.append(word)
                    end_ms = cue.end
                    
                    duration_sec = (end_ms - start_ms) / 1000.0
                    is_punct = bool(re.search(r'[,.!?]$', word))
                    
                    if (len(curr_words) >= 8 or duration_sec >= 3.8 or (is_punct and len(curr_words) >= 5)):
                        scene_text = " ".join(curr_words)
                        time_str = f"{format_timestamp(start_ms)} -> {format_timestamp(end_ms)}"
                        scenes_raw.append((scene_text, time_str))
                        curr_words = []
                        start_ms = end_ms
                        
                if curr_words:
                    scene_text = " ".join(curr_words)
                    time_str = f"{format_timestamp(start_ms)} -> {format_timestamp(end_ms)}"
                    scenes_raw.append((scene_text, time_str))

            BACKGROUND_JOBS[job_id]["progress"] = 60
            BACKGROUND_JOBS[job_id]["status_text"] = "STEP 2: Groq AI generating stunning 16:9 vector prompts & props..."

            scenes = []
            total_scenes = len(scenes_raw)

            for idx, (scene_text, time_str) in enumerate(scenes_raw, start=1):
                pct = 60 + int((idx / total_scenes) * 38)
                BACKGROUND_JOBS[job_id]["progress"] = pct
                BACKGROUND_JOBS[job_id]["status_text"] = f"Groq AI crafting 16:9 prompt {idx} of {total_scenes}..."

                ai_prompt = await call_groq_ai_prompt_engineer(scene_text, idx)
                if not ai_prompt:
                    ai_prompt = build_vector_art_scene_prompt_fallback(scene_text)

                scenes.append({
                    "scene": idx,
                    "timestamp": time_str,
                    "text": scene_text,
                    "prompt": ai_prompt
                })

            for chunk_file in temp_chunks:
                try:
                    os.remove(chunk_file)
                except Exception:
                    pass

            BACKGROUND_JOBS[job_id] = {
                "status": "completed",
                "progress": 100,
                "status_text": f"Generated {len(scenes)} rich 16:9 vector prompts!",
                "mode": "breakdown",
                "result": {
                    "scenes": scenes
                }
            }
            return

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
                    "wordCount": len(full_humanized_text.split())
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
                    "wordCount": len(full_humanized_text.split())
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
