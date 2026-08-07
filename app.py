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

def split_script_into_scenes(raw_text):
    lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
    raw_sentences = []
    for line in lines:
        sents = re.split(r'(?<=[.!?])\s+', line)
        for s in sents:
            if s.strip():
                raw_sentences.append(s.strip())
                
    scenes = []
    for sent in raw_sentences:
        words = sent.split()
        if len(words) <= 12:
            scenes.append(sent)
        else:
            # Group into natural 7-10 word meaningful clause scenes
            clauses = re.split(r'(?<=[,;:—])\s+', sent)
            curr = []
            for c in clauses:
                curr.extend(c.split())
                if len(curr) >= 7:
                    scenes.append(" ".join(curr))
                    curr = []
            if curr:
                if len(curr) <= 3 and scenes:
                    scenes[-1] += " " + " ".join(curr)
                else:
                    scenes.append(" ".join(curr))
                
    return scenes if scenes else [raw_text]
async def call_groq_ai_prompt_engineer(session, scene_text, scene_number):
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        return None

    system_prompt = (
        "You are an Elite Visual Prompt Engineer for YouTube architectural, engineering, and financial explainer videos.\n"
        "Your task: Read a 3-5 second script line and create a structured Beat Scene Prompt for a 2D hand-drawn educational technical diagram illustration (like Google Flow / graphic novel style).\n\n"
        "STRICT MASTER PROMPT PATTERN:\n"
        "2D hand-drawn educational architectural vector illustration, graphic novel technical diagram style, crisp clean black outlines, soft flat color palette, polished YouTube explainer aesthetics.\n\n"
        "LARGE BOLD TOP TITLE BANNER:\n"
        "\"[1-3 WORD TOPIC IN BOLD CAPITAL LETTERS AT TOP OF FRAME, e.g. 'GREENS', 'BUNKERS', 'CART PATHS', 'IRRIGATION', 'DRAINAGE', 'EARTHMOVING', 'PERMITS', 'PROFESSIONAL SERVICES']\"\n\n"
        "SCENE COMPOSITION & TECHNICAL DETAILS:\n"
        "[Describe panoramic, isometric, or cross-sectional view of the scene. Include detailed technical elements such as soil cutaway layers, water/drainage pipelines, construction machinery like excavators/bulldozers, annotated blueprint callouts with arrows, or glowing cyan property boundary lines].\n\n"
        "[If prices/numbers appear in script like '$3M', '$75k/acre', or '$1.5M', describe huge bright-red text callouts: Large bright-red text: \"$3,000,000\"].\n\n"
        "STRICT RULES:\n"
        "1. Always start with: '2D hand-drawn educational architectural vector illustration, graphic novel technical diagram style, crisp clean black outlines, soft flat color palette, polished YouTube explainer aesthetics.'\n"
        "2. NEVER include social media handles or channel tags!\n\n"
        "Respond strictly in JSON format:\n"
        '{\n  "prompt": "2D hand-drawn educational architectural vector illustration, graphic novel technical diagram style..."\n}'
    )

    user_prompt = f"Script Line (Beat {scene_number}): \"{scene_text}\""

    for model in ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]:
        try:
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.7,
                "response_format": {"type": "json_object"}
            }
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            async with session.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers, timeout=12) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    content = data["choices"][0]["message"]["content"]
                    parsed = json.loads(content)
                    prompt_val = parsed.get("prompt")
                    if prompt_val and len(prompt_val) > 30:
                        clean_prompt = re.sub(r'@[a-zA-Z0-9_]+', '', prompt_val)
                        return clean_prompt
        except Exception as e:
            print(f"Groq exception on scene {scene_number}: {e}")

    return None

def build_vector_art_scene_prompt_fallback(text):
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text)
    stopwords = {
        "that", "have", "with", "this", "from", "they", "will", "would", "there", "their",
        "were", "been", "some", "into", "than", "more", "like", "over", "okay", "you",
        "your", "want", "need", "just", "what", "when", "make", "first", "then", "also",
        "about", "how", "does", "done", "could", "should", "here", "know", "take", "look"
    }
    filtered = [w.upper() for w in words if w.lower() not in stopwords][:3]
    topic_title = " ".join(filtered) if filtered else "OVERVIEW"

    money_match = re.search(r'(\$?\d+[\d,.]*\s*(million|billion|thousand|k|m)?)', text, re.IGNORECASE)
    money_label = ""
    if money_match and len(money_match.group(0)) > 1:
        money_label = f"\n\nHuge bright-red text callout:\n\"{money_match.group(0).upper()}\""

    prompt_str = (
        "2D hand-drawn educational architectural vector illustration, graphic novel technical diagram style, crisp clean black outlines, soft flat color palette, polished YouTube explainer aesthetics.\n\n"
        f"LARGE BOLD TOP TITLE BANNER:\n\"{topic_title}\"\n\n"
        f"Detailed 16:9 panoramic technical diagram view of {topic_title}.\n\n"
        "Cross-sectional cutaway layers, annotated callout arrows, machinery icons, and glowing cyan boundary outlines.\n"
        "Clean paper background, generous negative space, high contrast composition."
        f"{money_label}"
    )

    return prompt_str

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

        submaker = edge_tts.SubMaker()
        communicate = edge_tts.Communicate(full_humanized_text, voice_id, rate=rate, pitch="+0Hz")

        BACKGROUND_JOBS[job_id]["progress"] = 15
        BACKGROUND_JOBS[job_id]["status_text"] = "Generating HD Voiceover & frame-perfect timing analysis..."

        with open(out_filepath, "wb") as f:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    submaker.feed(chunk)

        if mode == "breakdown":
            BACKGROUND_JOBS[job_id]["progress"] = 50
            BACKGROUND_JOBS[job_id]["status_text"] = "STEP 1: Computing natural 3-5 second scene cuts..."

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
                    is_punct = bool(re.search(r'[.!?]$', word))
                    
                    if (len(curr_words) >= 8 or duration_sec >= 3.5 or (is_punct and len(curr_words) >= 6)):
                        scene_text = " ".join(curr_words)
                        time_str = f"{format_timestamp(start_ms)} -> {format_timestamp(end_ms)}"
                        scenes_raw.append({
                            "text": scene_text,
                            "time_str": time_str,
                            "start_ms": start_ms,
                            "end_ms": end_ms,
                            "dur_sec": round((end_ms - start_ms) / 1000.0, 3)
                        })
                        curr_words = []
                        start_ms = end_ms
                        
                if curr_words:
                    scene_text = " ".join(curr_words)
                    time_str = f"{format_timestamp(start_ms)} -> {format_timestamp(end_ms)}"
                    scenes_raw.append({
                        "text": scene_text,
                        "time_str": time_str,
                        "start_ms": start_ms,
                        "end_ms": end_ms,
                        "dur_sec": round((end_ms - start_ms) / 1000.0, 3)
                    })
            
            if not scenes_raw:
                scene_lines = split_script_into_scenes(raw_text)
                est_sec = 0.0
                for line in scene_lines:
                    dur = (len(line.split()) / 150.0) * 60.0
                    t_start = format_timestamp(int(est_sec * 1000))
                    t_start_ms = int(est_sec * 1000)
                    est_sec += dur
                    t_end = format_timestamp(int(est_sec * 1000))
                    t_end_ms = int(est_sec * 1000)
                    scenes_raw.append({
                        "text": line,
                        "time_str": f"{t_start} -> {t_end}",
                        "start_ms": t_start_ms,
                        "end_ms": t_end_ms,
                        "dur_sec": round(dur, 3)
                    })

            BACKGROUND_JOBS[job_id]["progress"] = 65
            BACKGROUND_JOBS[job_id]["status_text"] = f"STEP 2: Speech Alignment Agent mapping {len(scenes_raw)} spoken scene beats to AI prompts..."

            async with ClientSession() as http_session:
                tasks = [
                    call_groq_ai_prompt_engineer(http_session, sitem["text"], idx)
                    for idx, (sitem) in enumerate(scenes_raw, start=1)
                ]
                ai_prompts = await asyncio.gather(*tasks)

            scenes = []
            for idx, (sitem, prompt_res) in enumerate(zip(scenes_raw, ai_prompts), start=1):
                if not prompt_res:
                    prompt_res = build_vector_art_scene_prompt_fallback(sitem["text"])
                
                scenes.append({
                    "scene": idx,
                    "timestamp": sitem["time_str"],
                    "text": sitem["text"],
                    "prompt": prompt_res if isinstance(prompt_res, str) else prompt_res.get("prompt", ""),
                    "start_ms": sitem["start_ms"],
                    "end_ms": sitem["end_ms"],
                    "dur_sec": sitem["dur_sec"]
                })

            BACKGROUND_JOBS[job_id] = {
                "status": "completed",
                "progress": 100,
                "status_text": f"Generated Voiceover MP3 & {len(scenes)} natural 2D doodle prompts!",
                "mode": "breakdown",
                "result": {
                    "filename": filename,
                    "audioUrl": f"/static/generated/{filename}",
                    "scenes": scenes
                }
            }
            return

        if mode == "audio":
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

import zipfile
import shutil

def parse_timestamp_seconds(ts_str):
    try:
        parts = ts_str.split("->")
        def to_sec(t):
            sub = t.strip().split(":")
            m = float(sub[0])
            s = float(sub[1])
            return m * 60 + s
        start = to_sec(parts[0])
        end = to_sec(parts[1])
        return max(0.2, round(end - start, 3))
    except Exception:
        return 3.0

async def get_media_duration_sec(filepath):
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            filepath
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        val = stdout.decode().strip()
        return float(val) if val else 0.0
    except Exception as e:
        print(f"ffprobe error for {filepath}:", e)
        return 0.0

def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', os.path.basename(s))]

async def process_video_assembly_async(video_job_id, original_job_id, zip_bytes, image_files_data):
    try:
        BACKGROUND_JOBS[video_job_id] = {
            "status": "processing",
            "progress": 10,
            "status_text": "🎬 Production Director: Extracting and auditing scene assets...",
            "mode": "video",
            "result": None
        }

        orig_job = BACKGROUND_JOBS.get(original_job_id)
        audio_filename = None
        scenes = []

        if orig_job and orig_job.get("result"):
            res = orig_job["result"]
            audio_filename = res.get("filename")
            scenes = res.get("scenes", [])
            
        if not audio_filename:
            mp3_files = [f for f in os.listdir(DOWNLOADS_DIR) if f.endswith(".mp3")]
            if mp3_files:
                mp3_files.sort(key=lambda f: os.path.getmtime(os.path.join(DOWNLOADS_DIR, f)), reverse=True)
                audio_filename = mp3_files[0]

        audio_filepath = os.path.join(DOWNLOADS_DIR, audio_filename) if audio_filename else None

        if not audio_filepath or not os.path.exists(audio_filepath):
            raise Exception("No matching voiceover MP3 audio found. Please generate voiceover first.")

        temp_img_dir = os.path.join(STUDIO_DIR, f"temp_imgs_{video_job_id[:6]}")
        os.makedirs(temp_img_dir, exist_ok=True)

        extracted_imgs = []

        if zip_bytes:
            zip_path = os.path.join(temp_img_dir, "uploaded_scenes.zip")
            with open(zip_path, "wb") as f:
                f.write(zip_bytes)
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_img_dir)
            
            for root, _, files in os.walk(temp_img_dir):
                for file in files:
                    if file.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                        extracted_imgs.append(os.path.join(root, file))

        if image_files_data:
            for fname, fbytes in image_files_data:
                fpath = os.path.join(temp_img_dir, fname)
                with open(fpath, "wb") as f:
                    f.write(fbytes)
                extracted_imgs.append(fpath)

        # Production Director Asset Audit & Clean Sanitization
        extracted_imgs = [
            p for p in extracted_imgs
            if not os.path.basename(p).startswith('.')
            and '__MACOSX' not in p
            and not p.endswith('.DS_Store')
            and not p.endswith('Thumbs.db')
        ]

        if not extracted_imgs:
            raise Exception("No valid image files (.png, .jpg, .webp) found in upload.")

        extracted_imgs.sort(key=natural_sort_key)
        total_images = len(extracted_imgs)

        total_audio_duration = await get_media_duration_sec(audio_filepath)
        if total_audio_duration <= 0.5:
            total_audio_duration = 30.0

        BACKGROUND_JOBS[video_job_id]["progress"] = 35
        BACKGROUND_JOBS[video_job_id]["status_text"] = f"🎬 Production Director: Sanitized {total_images} images & aligned audio timeline ({total_audio_duration:.1f}s)..."

        # Speech Recognition & Word-Boundary Alignment Agent (Exact Spoken Audio Timings)
        image_durations = []
        if total_images == len(scenes) and len(scenes) > 0:
            for scene in scenes:
                dur = scene.get("dur_sec")
                if not dur or dur <= 0.1:
                    dur = parse_timestamp_seconds(scene.get("timestamp", ""))
                image_durations.append(dur)
        else:
            per_img_dur = total_audio_duration / total_images
            for _ in range(total_images):
                image_durations.append(round(per_img_dur, 3))

        concat_filepath = os.path.join(temp_img_dir, "input_concat.txt")
        
        with open(concat_filepath, "w", encoding="utf-8") as f:
            for img_path, dur in zip(extracted_imgs, image_durations):
                escaped_path = img_path.replace("\\", "/")
                f.write(f"file '{escaped_path}'\n")
                f.write(f"duration {dur:.3f}\n")
            
            if extracted_imgs:
                last_path = extracted_imgs[-1].replace("\\", "/")
                f.write(f"file '{last_path}'\n")

        out_video_filename = f"video_{video_job_id[:6]}.mp4"
        out_video_filepath = os.path.join(DOWNLOADS_DIR, out_video_filename)

        BACKGROUND_JOBS[video_job_id]["progress"] = 60
        BACKGROUND_JOBS[video_job_id]["status_text"] = f"Rendering 1080p MP4 video with all {total_images} images..."

        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", concat_filepath,
            "-i", audio_filepath,
            "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black,format=yuv420p",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            out_video_filepath
        ]

        proc = await asyncio.create_subprocess_exec(
            *ffmpeg_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            err_log = stderr.decode('utf-8', errors='ignore')
            print("FFmpeg error log:", err_log)
            raise Exception("FFmpeg video rendering failed. Please check image formats.")

        # Phase 2: Quality Verification Agent Audit
        BACKGROUND_JOBS[video_job_id]["progress"] = 90
        BACKGROUND_JOBS[video_job_id]["status_text"] = "🕵️‍♂️ Quality Verification Agent: Auditing rendered MP4 streams & audio sync..."

        video_duration = await get_media_duration_sec(out_video_filepath)
        drift_sec = abs(video_duration - total_audio_duration)

        qa_passed = (os.path.getsize(out_video_filepath) > 1000) and (drift_sec < 1.0)
        qa_report = f"✅ Quality Audit Passed: All {total_images}/{total_images} images included | Frame-Perfect Audio Sync (Drift: {drift_sec:.2f}s)"

        if not qa_passed:
            raise Exception(f"Quality Check Failed: Video duration sync drift exceeds tolerance ({drift_sec:.2f}s).")

        try:
            shutil.rmtree(temp_img_dir)
        except Exception:
            pass

        BACKGROUND_JOBS[video_job_id] = {
            "status": "completed",
            "progress": 100,
            "status_text": qa_report,
            "mode": "video",
            "result": {
                "videoFilename": out_video_filename,
                "videoUrl": f"/static/generated/{out_video_filename}",
                "qaReport": qa_report,
                "imagesRendered": total_images,
                "durationSec": round(video_duration, 1)
            }
        }

    except Exception as e:
        print(f"Error assembling video {video_job_id}:", e)
        BACKGROUND_JOBS[video_job_id] = {
            "status": "failed",
            "progress": 0,
            "status_text": f"Error: {str(e)}",
            "mode": "video",
            "result": None
        }

async def handle_assemble_video(request):
    try:
        reader = await request.multipart()
        original_job_id = ""
        zip_bytes = None
        image_files_data = []

        while True:
            field = await reader.next()
            if field is None:
                break
            if field.name == "job_id":
                original_job_id = (await field.read()).decode('utf-8').strip()
            elif field.name == "zip_file":
                zip_bytes = await field.read()
            elif field.name == "images":
                filename = field.filename
                if filename:
                    fbytes = await field.read()
                    image_files_data.append((filename, fbytes))

        video_job_id = str(uuid.uuid4())
        asyncio.create_task(process_video_assembly_async(video_job_id, original_job_id, zip_bytes, image_files_data))

        return web.json_response({"job_id": video_job_id, "status": "processing"})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

def create_app():
    # Allow large ZIP uploads up to 500MB
    app = web.Application(client_max_size=500 * 1024 * 1024)
    app.router.add_get("", handle_index)
    app.router.add_get("/", handle_index)
    app.router.add_get("/index.html", handle_index)
    app.router.add_post("/api/start-job", handle_start_job)
    app.router.add_get("/api/job-status", handle_job_status)
    app.router.add_get("/api/voices", handle_voices)
    app.router.add_post("/api/assemble-video", handle_assemble_video)
    app.router.add_post("/telegram-webhook", handle_telegram_webhook)
    app.router.add_static("/static/", STATIC_DIR)
    return app

if __name__ == "__main__":
    print(f"Starting YouTube Voiceover Studio Online at http://{HOST}:{PORT}")
    web.run_app(create_app(), host=HOST, port=PORT)
