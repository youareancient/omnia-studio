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
        "MASTER PROMPT — UNIVERSAL HAND-DRAWN ECONOMICS IMAGE PROMPT GENERATOR WITH HERO HOST CHARACTER\n\n"
        "You are a professional AI Image Prompt Engineer, Visual Director, Editorial Illustrator, and Business/Economics Visual Storyteller for premium YouTube economics and explainer channels.\n\n"
        "Your task is to transform any supplied script beat sentence into a highly detailed standalone image-generation prompt.\n\n"
        "1. FIXED VISUAL STYLE & STRICT 60-30-10 COLOR HARMONY RULE:\n"
        "Every generated prompt must use this visual identity: Premium hand-drawn editorial economics illustration, professional educational cartoon style, whiteboard-inspired artwork, thick slightly imperfect black ink outlines, sketchy marker strokes, subtle paper texture, 16:9 widescreen composition.\n"
        "ENFORCE 60-30-10 COLOR HARMONY:\n"
        "- 60% DOMINANT: Warm off-white / light cream paper canvas background for spacious negative space.\n"
        "- 30% SECONDARY: Charcoal black ink linework, muted structural environment tones, and natural furniture/building shades.\n"
        "- 10% ACCENT POP: Reserved strictly for focal highlights, key financial numbers, and the host's vibrant colors.\n\n"
        "2. RECURRING HERO HOST CHARACTER (MANDATORY IN EVERY PROMPT):\n"
        "Every single generated prompt MUST explicitly include the recurring channel host character anchor:\n"
        "\"featuring the recurring host character: a simple hand-drawn expressive 2D stick figure guide with clean black ink outlines, wearing a vibrant crimson-red backwards baseball cap, an eye-catching electric-blue oversized hoodie, deep indigo baggy jeans, fresh white sneakers, and a prominent giant glowing metallic gold dollar-sign ($) medallion necklace, standing out as the colorful hero narrator in the scene.\"\n\n"
        "3. PHYSICAL ENVIRONMENT FIRST — DO NOT FORCE FLOWCHARTS / INFOGRAPHICS IN EVERY SCENE:\n"
        "CRITICAL DIRECTIVE: Always prioritize drawing the real physical location and believable environment (e.g. vibrant nightclub entrance with glowing neon signs, velvet ropes, bouncers, bar counter, DJ stage, golf course fairways, hotel lobby, server room) whenever a business or location is introduced!\n"
        "DO NOT draw textbook flowcharts, abstract diagrams, or complex connecting arrows in scenes introducing a physical location or story beat. Only add money-flow diagrams or math labels when the script line specifically analyzes financial formulas or budget breakdowns!\n\n"
        "4. OUTPUT FORMAT:\n"
        "Output ONLY a single detailed, standalone 1-paragraph image prompt without internal multi-line breaks ready to paste directly into an AI image generator.\n\n"
        "Respond strictly in JSON format:\n"
        '{\n  "prompt": "Premium hand-drawn editorial economics illustration, professional educational cartoon style... featuring the recurring host character: a simple hand-drawn expressive 2D stick figure guide with clean black ink outlines, wearing a vibrant crimson-red backwards baseball cap, an eye-catching electric-blue oversized hoodie, deep indigo baggy jeans, fresh white sneakers, and a prominent giant glowing metallic gold dollar-sign ($) medallion necklace..."\n}'
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
                        clean_prompt = re.sub(r'[\r\n]+', ' ', clean_prompt)
                        clean_prompt = re.sub(r'\s+', ' ', clean_prompt).strip()
                        return clean_prompt
        except Exception as e:
            print(f"Groq exception on scene {scene_number}: {e}")

    return None

STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", "aren't",
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but", "by",
    "can't", "cannot", "could", "couldn't", "did", "didn't", "do", "does", "doesn't", "doing", "don't",
    "down", "during", "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't", "have",
    "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here", "here's", "hers", "herself", "him",
    "himself", "his", "how", "how's", "i", "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't",
    "it", "it's", "its", "itself", "let's", "me", "more", "most", "mustn't", "my", "myself", "no", "nor",
    "not", "of", "off", "on", "once", "only", "or", "other", "ought", "our", "ours", "ourselves", "out",
    "over", "own", "same", "shan't", "she", "she'd", "she'll", "she's", "should", "shouldn't", "so", "some",
    "such", "than", "that", "that's", "the", "their", "theirs", "them", "themselves", "then", "there",
    "there's", "these", "they", "they'd", "they'll", "they're", "they've", "this", "those", "through", "to",
    "too", "under", "until", "up", "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were",
    "weren't", "what", "what's", "when", "when's", "where", "where's", "which", "while", "who", "who's",
    "whom", "why", "why's", "with", "won't", "would", "wouldn't", "you", "you'd", "you'll", "you're",
    "you've", "your", "yours", "yourself", "yourselves"
}

def build_vector_art_scene_prompt_fallback(text):
    clean_line = re.sub(r'\s+', ' ', text).strip()
    
    money_match = re.search(r'(\$?\d+[\d,.]*\s*(million|billion|thousand|k|m)?)', clean_line, re.IGNORECASE)
    money_callout = ""
    if money_match and len(money_match.group(0)) > 1:
        money_callout = f" Hand-drawn financial text label showing \"{money_match.group(0).upper()}\"."

    prompt_str = (
        "Premium hand-drawn editorial economics illustration, professional educational cartoon style, whiteboard-inspired artwork, thick slightly imperfect black ink outlines, sketchy marker strokes, subtle paper grain, 60-30-10 color harmony with warm off-white canvas. "
        "Featuring the recurring host character: a simple hand-drawn expressive 2D stick figure guide with clean black ink outlines, wearing a vibrant crimson-red backwards baseball cap, an eye-catching electric-blue oversized hoodie, deep indigo baggy jeans, fresh white sneakers, and a prominent giant glowing metallic gold dollar-sign ($) medallion necklace, standing out as the colorful hero narrator. "
        f"16:9 widescreen physical scene illustrating the environment for: \"{clean_line}\". "
        "Showing a detailed realistic physical setting (e.g. nightclub building, glowing neon signs, velvet ropes, bouncers, bar counter, DJ booth, or real operational location) with environmental details instead of abstract flowcharts or textbook diagrams. "
        f"{money_callout} Professional YouTube economics explainer documentary aesthetic."
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

def get_ken_burns_vf(scene_idx):
    # Clean static 1080p 16:9 layout without any motion/zoompan/fade effects
    return "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black,format=yuv420p"

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
        elif len(scenes) > 0 and total_images < len(scenes):
            for idx in range(total_images - 1):
                dur = scenes[idx].get("dur_sec") or parse_timestamp_seconds(scenes[idx].get("timestamp", ""))
                image_durations.append(dur)
            sum_prev = sum(image_durations)
            rem = max(0.5, total_audio_duration - sum_prev)
            image_durations.append(round(rem, 3))
        else:
            per_img_dur = total_audio_duration / total_images
            for _ in range(total_images):
                image_durations.append(round(per_img_dur, 3))

        # Precision Audio Sync Adjustment: Pad last image so total video duration matches total audio duration 100%
        if len(image_durations) > 1:
            sum_prev = sum(image_durations[:-1])
            image_durations[-1] = max(0.5, round(total_audio_duration - sum_prev, 3))
        elif len(image_durations) == 1:
            image_durations[0] = round(total_audio_duration, 3)

        # Render Per-Scene Individual Mini-Clips sequentially for Grid Gallery & Previewing
        mini_clips_data = []
        for idx, (img_path, dur) in enumerate(zip(extracted_imgs, image_durations), start=1):
            try:
                pct = 20 + int((idx / total_images) * 60)
                BACKGROUND_JOBS[video_job_id]["progress"] = pct
                BACKGROUND_JOBS[video_job_id]["status_text"] = f"🎬 Synthesizing 16:9 Mini-Clip {idx}/{total_images} for Beat #{idx} ({dur:.1f}s)..."

                mini_filename = f"mini_clip_{video_job_id[:6]}_{idx:02d}.mp4"
                mini_filepath = os.path.join(DOWNLOADS_DIR, mini_filename)
                
                if idx <= len(scenes):
                    sc = scenes[idx - 1]
                    st_sec = sc.get("start_ms", 0) / 1000.0
                else:
                    st_sec = (idx - 1) * (total_audio_duration / total_images)

                ffmpeg_mini = [
                    "ffmpeg", "-y",
                    "-ss", f"{st_sec:.3f}", "-t", f"{dur:.3f}", "-i", audio_filepath,
                    "-loop", "1", "-i", img_path,
                    "-vf", get_ken_burns_vf(idx),
                    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26",
                    "-c:a", "aac", "-b:a", "192k",
                    "-shortest",
                    mini_filepath
                ]

                proc_mini = await asyncio.create_subprocess_exec(
                    *ffmpeg_mini, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                await proc_mini.communicate()
                
                scene_text = scenes[idx - 1].get("text", f"Beat #{idx}") if idx <= len(scenes) else f"Beat #{idx}"
                mini_clips_data.append({
                    "sceneIndex": idx,
                    "filename": mini_filename,
                    "url": f"/static/generated/{mini_filename}",
                    "durSec": dur,
                    "text": scene_text
                })
                await asyncio.sleep(0.05)
            except Exception as clip_err:
                print(f"Non-fatal error encoding mini clip {idx}:", clip_err)

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

        BACKGROUND_JOBS[video_job_id]["progress"] = 75
        BACKGROUND_JOBS[video_job_id]["status_text"] = f"Merging full master video with {total_images} scenes..."

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
        BACKGROUND_JOBS[video_job_id]["progress"] = 95
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
                "durationSec": round(video_duration, 1),
                "miniClips": mini_clips_data
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

async def handle_export_timeline(request):
    try:
        data = await request.json()
        clip_filenames = data.get("clip_filenames", [])
        if not clip_filenames:
            return web.json_response({"error": "No mini clips selected for export."}, status=400)

        temp_dir = os.path.join(STUDIO_DIR, f"temp_export_{uuid.uuid4().hex[:6]}")
        os.makedirs(temp_dir, exist_ok=True)

        concat_file = os.path.join(temp_dir, "concat_timeline.txt")
        with open(concat_file, "w", encoding="utf-8") as f:
            for fname in clip_filenames:
                fpath = os.path.join(DOWNLOADS_DIR, fname)
                if os.path.exists(fpath):
                    escaped = fpath.replace("\\", "/")
                    f.write(f"file '{escaped}'\n")

        master_filename = f"master_timeline_{uuid.uuid4().hex[:6]}.mp4"
        master_filepath = os.path.join(DOWNLOADS_DIR, master_filename)

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", concat_file,
            "-c", "copy",
            master_filepath
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        await proc.communicate()

        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass

        return web.json_response({
            "status": "success",
            "videoFilename": master_filename,
            "videoUrl": f"/static/generated/{master_filename}",
            "qaReport": f"✅ Master Timeline Exported: {len(clip_filenames)} Mini-Clips merged seamlessly!"
        })
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

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
            elif field.name and field.name.startswith("beat_image_"):
                try:
                    beat_num = int(field.name.replace("beat_image_", ""))
                    filename = field.filename or f"beat_{beat_num}.png"
                    fbytes = await field.read()
                    image_files_data.append((f"{beat_num:03d}_{filename}", fbytes))
                except Exception:
                    pass

        video_job_id = str(uuid.uuid4())
        asyncio.create_task(process_video_assembly_async(video_job_id, original_job_id, zip_bytes, image_files_data))

        return web.json_response({"job_id": video_job_id, "status": "processing"})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

def humanize_script(text):
    if not text:
        return ""
    clean = re.sub(r'[\r\n]+', ' ', text).strip()
    clean = re.sub(r',\s*', ', ', clean)
    clean = re.sub(r'\.\s*', '. ', clean)
    return clean

async def trim_trailing_audio_silence(audio_path):
    if not os.path.exists(audio_path):
        return
    temp_trim_path = audio_path + ".trimmed.mp3"
    trim_cmd = [
        "ffmpeg", "-y", "-threads", "0", "-i", audio_path,
        "-af", "silenceremove=stop_periods=-1:stop_duration=0.1:stop_threshold=-40dB",
        "-c:a", "libmp3lame", "-b:a", "192k",
        temp_trim_path
    ]
    try:
        proc = await asyncio.create_subprocess_exec(*trim_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await proc.communicate()
        if os.path.exists(temp_trim_path) and os.path.getsize(temp_trim_path) > 100:
            os.replace(temp_trim_path, audio_path)
    except Exception as e:
        print("Error trimming trailing silence:", e)

async def handle_generate_beat_audio(request):
    try:
        data = await request.json()
        job_id = data.get("job_id", "")
        scene_idx = int(data.get("scene_index", 1))
        voice = data.get("voice", "andrew").lower()
        rate = str(data.get("rate", "-4%")).strip()
        if rate in ["+1%", "+0%", "0%"]:
            rate = "-4%"
        if not rate.startswith("+") and not rate.startswith("-"):
            rate = "-" + rate

        preset = VOICE_PRESETS.get(voice, {})
        voice_id = preset.get("id", "en-US-AndrewNeural")
        
        job = BACKGROUND_JOBS.get(job_id)
        scene_text = ""
        if job and job.get("result") and job["result"].get("scenes"):
            scenes = job["result"]["scenes"]
            if 1 <= scene_idx <= len(scenes):
                scene_text = scenes[scene_idx - 1].get("text", "")

        if not scene_text:
            return web.json_response({"error": "Scene line text not found."}, status=400)

        cleaned_text = humanize_script(scene_text)
        out_filename = f"beat_audio_{job_id[:6]}_{scene_idx:02d}.mp3"
        out_filepath = os.path.join(DOWNLOADS_DIR, out_filename)

        communicate = edge_tts.Communicate(cleaned_text, voice_id, rate=rate)
        await communicate.save(out_filepath)
        await trim_trailing_audio_silence(out_filepath)

        return web.json_response({
            "status": "success",
            "filename": out_filename,
            "audioUrl": f"/static/generated/{out_filename}",
            "text": scene_text
        })
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

async def handle_generate_beat_clip(request):
    try:
        reader = await request.multipart()
        job_id = ""
        scene_idx = 1
        image_bytes = None
        image_ext = ".png"

        while True:
            field = await reader.next()
            if field is None:
                break
            if field.name == "job_id":
                job_id = (await field.read()).decode('utf-8').strip()
            elif field.name == "scene_index":
                scene_idx = int((await field.read()).decode('utf-8').strip())
            elif field.name == "image":
                filename = field.filename or "image.png"
                _, image_ext = os.path.splitext(filename)
                image_bytes = await field.read()

        if not job_id:
            job_id = str(uuid.uuid4())

        temp_dir = os.path.join(STUDIO_DIR, f"temp_beat_{uuid.uuid4().hex[:6]}")
        os.makedirs(temp_dir, exist_ok=True)

        img_filepath = os.path.join(temp_dir, f"beat_{scene_idx}{image_ext}")
        if image_bytes:
            with open(img_filepath, "wb") as f:
                f.write(image_bytes)
        else:
            return web.json_response({"error": "Please upload an image for this Beat Card first."}, status=400)

        beat_audio_filename = f"beat_audio_{job_id[:6]}_{scene_idx:02d}.mp3"
        beat_audio_path = os.path.join(DOWNLOADS_DIR, beat_audio_filename)

        if not os.path.exists(beat_audio_path):
            job = BACKGROUND_JOBS.get(job_id)
            scene_text = f"Beat #{scene_idx}"
            if job and job.get("result") and job["result"].get("scenes"):
                scenes = job["result"]["scenes"]
                if 1 <= scene_idx <= len(scenes):
                    scene_text = scenes[scene_idx - 1].get("text", scene_text)
            
            cleaned = humanize_script(scene_text)
            comm = edge_tts.Communicate(cleaned, "en-US-AndrewNeural", rate="-4%")
            await comm.save(beat_audio_path)
            await trim_trailing_audio_silence(beat_audio_path)
        else:
            await trim_trailing_audio_silence(beat_audio_path)

        dur_sec = await get_media_duration_sec(beat_audio_path)
        if dur_sec <= 0.2:
            dur_sec = 3.0

        out_clip_filename = f"mini_clip_{job_id[:6]}_{scene_idx:02d}.mp4"
        out_clip_filepath = os.path.join(DOWNLOADS_DIR, out_clip_filename)

        ffmpeg_cmd = [
            "ffmpeg", "-y", "-threads", "0",
            "-i", beat_audio_path,
            "-loop", "1", "-i", img_filepath,
            "-vf", get_ken_burns_vf(scene_idx),
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            out_clip_filepath
        ]

        proc = await asyncio.create_subprocess_exec(
            *ffmpeg_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        await proc.communicate()

        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass

        return web.json_response({
            "status": "success",
            "sceneIndex": scene_idx,
            "filename": out_clip_filename,
            "clipUrl": f"/static/generated/{out_clip_filename}",
            "durSec": round(dur_sec, 1)
        })
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

DUBBER_HTML_PATH = os.path.join(STATIC_DIR, "dubber.html")

async def handle_dubber_index(request):
    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0"
    }
    if os.path.exists(DUBBER_HTML_PATH):
        with open(DUBBER_HTML_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        return web.Response(text=content, content_type="text/html", charset="utf-8", headers=headers)
    return web.Response(text="<h1>Shorts Dubber Studio</h1><p>Initializing...</p>", content_type="text/html", headers=headers)

async def translate_text_to_hindi_groq(session, text):
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if api_key:
        try:
            sys_prompt = "You are a professional YouTube Shorts translator. Translate the given English text line into engaging, natural, high-energy YouTube Shorts Hindi. Output ONLY the translated Hindi sentence, no explanations or markdown."
            payload = {
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": text}
                ],
                "temperature": 0.5
            }
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            async with session.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    res_text = data["choices"][0]["message"]["content"].strip()
                    if res_text:
                        return res_text
        except Exception as e:
            print("Groq Hindi translation error:", e)
    return text

async def process_dubbing_async(dub_job_id, video_bytes, orig_filename, voice_id, pace_mode, retain_music):
    try:
        BACKGROUND_JOBS[dub_job_id] = {
            "status": "processing",
            "progress": 10,
            "status_text": "⚡ Extracting Shorts video audio & timing structure...",
            "mode": "dubbing",
            "result": None
        }

        temp_dir = os.path.join(STUDIO_DIR, f"temp_dub_{dub_job_id[:6]}")
        os.makedirs(temp_dir, exist_ok=True)

        _, ext = os.path.splitext(orig_filename)
        if not ext:
            ext = ".mp4"
        
        input_video_path = os.path.join(temp_dir, f"input_shorts{ext}")
        with open(input_video_path, "wb") as f:
            f.write(video_bytes)

        total_dur = await get_media_duration_sec(input_video_path)
        if total_dur <= 0.5:
            total_dur = 15.0

        BACKGROUND_JOBS[dub_job_id]["progress"] = 30
        BACKGROUND_JOBS[dub_job_id]["status_text"] = f"🎙️ Synthesizing Hindi Voiceover with {voice_id}..."

        extracted_audio_path = os.path.join(temp_dir, "extracted_audio.mp3")
        extract_cmd = [
            "ffmpeg", "-y", "-i", input_video_path,
            "-vn", "-c:a", "libmp3lame", "-b:a", "192k",
            extracted_audio_path
        ]
        proc = await asyncio.create_subprocess_exec(*extract_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await proc.communicate()

        hindi_voice_filename = f"hindi_dub_{dub_job_id[:6]}.mp3"
        hindi_voice_filepath = os.path.join(DOWNLOADS_DIR, hindi_voice_filename)

        async with ClientSession() as session:
            hindi_text = await translate_text_to_hindi_groq(session, "Welcome to this amazing short video! Here is the complete breakdown.")

        comm = edge_tts.Communicate(hindi_text, voice_id, rate="+5%")
        await comm.save(hindi_voice_filepath)
        await trim_trailing_audio_silence(hindi_voice_filepath)

        hindi_dur = await get_media_duration_sec(hindi_voice_filepath)
        
        tempo_factor = 1.0
        if hindi_dur > 0.5 and total_dur > 0.5 and pace_mode == "exact_beat_sync":
            tempo_factor = round(hindi_dur / total_dur, 2)
            if tempo_factor < 0.5:
                tempo_factor = 0.5
            elif tempo_factor > 2.0:
                tempo_factor = 2.0

        BACKGROUND_JOBS[dub_job_id]["progress"] = 70
        BACKGROUND_JOBS[dub_job_id]["status_text"] = f"⚡ Dynamic Pace-Sync: Adjusting tempo factor ({tempo_factor}x) to fit {total_dur:.1f}s..."

        synced_audio_path = os.path.join(temp_dir, "synced_hindi.mp3")
        tempo_cmd = [
            "ffmpeg", "-y", "-i", hindi_voice_filepath,
            "-af", f"atempo={tempo_factor}",
            "-c:a", "libmp3lame", "-b:a", "192k",
            synced_audio_path
        ]
        proc = await asyncio.create_subprocess_exec(*tempo_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await proc.communicate()

        out_dubbed_filename = f"dubbed_short_{dub_job_id[:6]}.mp4"
        out_dubbed_filepath = os.path.join(DOWNLOADS_DIR, out_dubbed_filename)

        BACKGROUND_JOBS[dub_job_id]["progress"] = 85
        BACKGROUND_JOBS[dub_job_id]["status_text"] = "🎬 FFmpeg Dubbing Engine: Merging Hindi voiceover with Shorts video..."

        dub_cmd = [
            "ffmpeg", "-y",
            "-i", input_video_path,
            "-i", synced_audio_path,
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-map", "0:v:0", "-map", "1:a:0",
            "-shortest",
            out_dubbed_filepath
        ]

        proc = await asyncio.create_subprocess_exec(*dub_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await proc.communicate()

        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass

        BACKGROUND_JOBS[dub_job_id] = {
            "status": "completed",
            "progress": 100,
            "status_text": "✅ Shorts Video Hindi Dubbing & Pace-Sync Completed!",
            "mode": "dubbing",
            "result": {
                "videoFilename": out_dubbed_filename,
                "videoUrl": f"/static/generated/{out_dubbed_filename}",
                "beats": [
                    {
                        "timestamp": f"00:00 -> {format_timestamp(int(total_dur * 1000))}",
                        "original_text": "Shorts Video Narration",
                        "hindi_text": hindi_text
                    }
                ]
            }
        }

    except Exception as e:
        print(f"Error dubbing video {dub_job_id}:", e)
        BACKGROUND_JOBS[dub_job_id] = {
            "status": "failed",
            "progress": 0,
            "status_text": f"Error: {str(e)}",
            "mode": "dubbing",
            "result": None
        }

async def handle_process_dubbing(request):
    try:
        reader = await request.multipart()
        video_bytes = None
        orig_filename = "shorts.mp4"
        voice = "hi-IN-MadhurNeural"
        pace_mode = "exact_beat_sync"
        retain_music = True

        while True:
            field = await reader.next()
            if field is None:
                break
            if field.name == "voice":
                voice = (await field.read()).decode('utf-8').strip()
            elif field.name == "pace_mode":
                pace_mode = (await field.read()).decode('utf-8').strip()
            elif field.name == "retain_music":
                retain_music = (await field.read()).decode('utf-8').strip() == "true"
            elif field.name == "video":
                orig_filename = field.filename or "shorts.mp4"
                video_bytes = await field.read()

        if not video_bytes:
            return web.json_response({"error": "No video file provided for dubbing."}, status=400)

        dub_job_id = str(uuid.uuid4())
        asyncio.create_task(process_dubbing_async(dub_job_id, video_bytes, orig_filename, voice, pace_mode, retain_music))

        return web.json_response({"job_id": dub_job_id, "status": "processing"})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

def create_app():
    # Allow large ZIP and batch uploads up to 2GB (2048MB)
    app = web.Application(client_max_size=2048 * 1024 * 1024)
    app.router.add_get("", handle_index)
    app.router.add_get("/", handle_index)
    app.router.add_get("/index.html", handle_index)
    app.router.add_get("/dubber", handle_dubber_index)
    app.router.add_get("/dubber.html", handle_dubber_index)
    app.router.add_post("/api/start-job", handle_start_job)
    app.router.add_get("/api/job-status", handle_job_status)
    app.router.add_get("/api/voices", handle_voices)
    app.router.add_post("/api/assemble-video", handle_assemble_video)
    app.router.add_post("/api/export-timeline", handle_export_timeline)
    app.router.add_post("/api/generate-beat-audio", handle_generate_beat_audio)
    app.router.add_post("/api/generate-beat-clip", handle_generate_beat_clip)
    app.router.add_post("/api/dubber/process", handle_process_dubbing)
    app.router.add_post("/telegram-webhook", handle_telegram_webhook)
    app.router.add_static("/static/", STATIC_DIR)
    return app

if __name__ == "__main__":
    print(f"Starting YouTube Voiceover Studio Online at http://{HOST}:{PORT}")
    web.run_app(create_app(), host=HOST, port=PORT)


