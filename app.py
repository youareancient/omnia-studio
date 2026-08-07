import asyncio
import json
import os
import re
import uuid
import wave
import struct
import subprocess
import edge_tts
from aiohttp import web, ClientSession, FormData
from sfx_generator import create_sub_bass_boom, create_whoosh, create_glitch, create_click

HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", 7860))
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()

STUDIO_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(STUDIO_DIR, "public")
DOWNLOADS_DIR = os.path.join(STATIC_DIR, "generated")
SFX_DIR = os.path.join(STATIC_DIR, "sfx")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)
os.makedirs(SFX_DIR, exist_ok=True)

# Generate SFX files on startup
create_sub_bass_boom()
create_whoosh()
create_glitch()
create_click()

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

def extract_shorts_clips(text):
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    full_str = " ".join(lines)
    sentences = re.split(r'(?<=[.!?])\s+', full_str)
    
    shorts = []
    current_chunk = []
    current_words = 0
    
    for s in sentences:
        words = len(s.split())
        if current_words + words <= 110:
            current_chunk.append(s)
            current_words += words
        else:
            if current_chunk:
                shorts.append(" ".join(current_chunk))
            current_chunk = [s]
            current_words = words
            
    if current_chunk and len(shorts) < 5:
        shorts.append(" ".join(current_chunk))
        
    return shorts[:5]

def get_audio_duration(file_path):
    try:
        cmd = [
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
            file_path
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return float(result.stdout.strip())
    except Exception as e:
        print("ffprobe error:", e)
        return 2.5

def mix_sfx_into_audio(speech_file, chunk_files, out_file):
    boom_file = os.path.join(SFX_DIR, "boom.wav")
    whoosh_file = os.path.join(SFX_DIR, "whoosh.wav")

    # Calculate timestamps for paragraph transitions
    offsets = [0.0]
    curr_time = 0.0
    for cf in chunk_files:
        dur = get_audio_duration(cf)
        curr_time += dur
        offsets.append(curr_time)

    # Build FFmpeg filter_complex command
    # Input 0: Speech MP3
    # Input 1: Boom WAV (at intro)
    # Inputs 2..N: Whoosh WAV (at transitions)
    inputs = ["-i", speech_file, "-i", boom_file]
    filter_parts = [
        "[0:a]volume=1.0[speech]",
        "[1:a]adelay=0|0,volume=0.4[sfx0]"
    ]
    mix_labels = ["[speech]", "[sfx0]"]

    # Limit whooshes to at most 6 transitions to prevent audio crowding
    max_whooshes = min(len(offsets) - 1, 6)
    for idx in range(1, max_whooshes):
        ms_delay = int(offsets[idx] * 1000)
        inputs.extend(["-i", whoosh_file])
        filter_idx = len(mix_labels)
        label = f"[sfx{idx}]"
        filter_parts.append(f"[{idx+1}:a]adelay={ms_delay}|{ms_delay},volume=0.3[{label[1:-1]}]")
        mix_labels.append(label)

    filter_complex = ";".join(filter_parts) + f";{''.join(mix_labels)}amix=inputs={len(mix_labels)}:duration=first:dropout_transition=2[outa]"

    cmd = ["ffmpeg", "-y"] + inputs + ["-filter_complex", filter_complex, "-map", "[outa]", "-c:a", "libmp3lame", "-b:a", "320k", out_file]
    
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode != 0:
            print("FFmpeg mix error:", res.stderr)
            # Fallback to direct raw copy if ffmpeg mix fails
            with open(out_file, "wb") as outfile:
                with open(speech_file, "rb") as infile:
                    outfile.write(infile.read())
    except Exception as ex:
        print("FFmpeg execution error:", ex)
        with open(out_file, "wb") as outfile:
            with open(speech_file, "rb") as infile:
                outfile.write(infile.read())

async def process_job_async(job_id, raw_text, voice_preset, rate, filename, mode, enable_sfx):
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

        if mode == "shorts":
            shorts_clips = extract_shorts_clips(raw_text)
            BACKGROUND_JOBS[job_id] = {
                "status": "completed",
                "progress": 100,
                "status_text": f"Extracted {len(shorts_clips)} YouTube Shorts scripts!",
                "mode": "shorts",
                "result": {
                    "shorts": shorts_clips
                }
            }
            return

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

            clean_para = re.sub(r'\[sfx:[^\]]+\]', '', para).strip()
            
            chunk_path = os.path.join(temp_dir, f"chunk_{uuid.uuid4().hex}.mp3")
            communicate = edge_tts.Communicate(clean_para, voice_id, rate=rate, pitch="+0Hz")
            
            with open(chunk_path, "wb") as f:
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        f.write(chunk["data"])
                    elif chunk["type"] == "WordBoundary":
                        submaker.feed(chunk)

            temp_chunks.append(chunk_path)

            progress_pct = int((i / total_paras) * 85) + 5
            BACKGROUND_JOBS[job_id]["progress"] = progress_pct
            BACKGROUND_JOBS[job_id]["status_text"] = f"Synthesizing paragraph {i} of {total_paras} ({progress_pct}%)..."

        if mode == "audio":
            BACKGROUND_JOBS[job_id]["progress"] = 92
            BACKGROUND_JOBS[job_id]["status_text"] = "Merging audio tracks..."

            speech_raw = os.path.join(temp_dir, f"speech_raw_{uuid.uuid4().hex}.mp3")
            with open(speech_raw, "wb") as outfile:
                for chunk_file in temp_chunks:
                    with open(chunk_file, "rb") as infile:
                        outfile.write(infile.read())

            if enable_sfx:
                BACKGROUND_JOBS[job_id]["progress"] = 96
                BACKGROUND_JOBS[job_id]["status_text"] = "Mixing HD Sub-Bass Booms & Whooshes into audio track..."
                mix_sfx_into_audio(speech_raw, temp_chunks, out_filepath)
            else:
                with open(out_filepath, "wb") as outfile:
                    with open(speech_raw, "rb") as infile:
                        outfile.write(infile.read())

            try:
                os.remove(speech_raw)
            except Exception:
                pass

            BACKGROUND_JOBS[job_id] = {
                "status": "completed",
                "progress": 100,
                "status_text": "Voiceover MP3 generated successfully!",
                "mode": "audio",
                "result": {
                    "filename": filename,
                    "audioUrl": f"/static/generated/{filename}",
                    "wordCount": len(full_humanized_text.split()),
                    "sfxActive": enable_sfx
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
        enable_sfx = data.get("enableSfx", False)

        if not raw_text:
            return web.json_response({"error": "Script text cannot be empty"}, status=400)

        job_id = str(uuid.uuid4())
        asyncio.create_task(process_job_async(job_id, raw_text, voice_preset, rate, filename, mode, enable_sfx))

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
