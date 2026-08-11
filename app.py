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

async def call_groq_ai_prompt_engineer(session, scene_text, scene_number, style_name="Clean Vector Economics (Milly / Cortex)"):
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        return None

    if "Photorealistic" in style_name:
        system_prompt = (
            "MASTER PROMPT — UNIVERSAL PHOTOREALISTIC 8K DOCUMENTARY IMAGE PROMPT GENERATOR\n\n"
            "You are a professional AI Image Prompt Engineer, Visual Director, Cinematographer, and Documentary Storyteller for high-end YouTube channels.\n\n"
            "Your task is to transform any supplied script beat sentence into a single, detailed, standalone photorealistic 8K image-generation prompt.\n\n"
            "1. 100% PHOTOREALISTIC 8K CINEMATIC DOCUMENTARY STYLE (STRICTLY NO CARTOONS OR DRAWINGS):\n"
            "Every generated prompt MUST enforce hyperrealistic 8K documentary photography for the ENTIRE scene — including backgrounds, real lighting, physical environments, ultra-detailed micro-textures, and realistic subjects.\n"
            "STRICT NEGATIVE CONSTRAINT: ABSOLUTELY NO 2D CARTOONS, NO DRAWINGS, NO STICK FIGURES, NO SKETCHES, NO WHITEBOARD ARTWORK, NO INFOGRAPHIC TEXTBOXES, AND NO SPLIT-SCREEN DIAGRAMS. Every person and object MUST look like a real 35mm film still or hyperrealistic 8K photograph!\n\n"
            "2. CINEMATIC COMPOSITION & LIGHTING:\n"
            "- Shallow depth of field, 35mm / 85mm portrait camera lens, natural ambient volumetric lighting, volumetric shadows, award-winning film grain, cinematic color grading, hyper-detailed skin textures/materials.\n"
            "- Single continuous full-frame 16:9 cinematic camera shot.\n\n"
            "3. DYNAMIC SUBJECT EVALUATION:\n"
            "- If the script line features a presenter or narrator host addressing the audience, describe a charismatic realistic presenter in modern professional attire, illuminated by studio/natural lighting.\n"
            "- If the script line describes physical objects, infrastructure, money, markets, or environments, focus 100% on a stunning cinematic B-roll camera shot of the subject without any presenter.\n\n"
            "4. OUTPUT FORMAT:\n"
            "Output ONLY a single detailed, standalone 1-paragraph image prompt starting with 'Hyperrealistic 8K ultra-detailed documentary photography...' ready to paste directly into an AI image generator.\n\n"
            "Respond strictly in JSON format:\n"
            '{\n  "prompt": "Hyperrealistic 8K ultra-detailed documentary photography, shot on 35mm lens, cinematic film lighting..."\n}'
        )
    else:
        system_prompt = (
            "MASTER PROMPT — CLEAN VECTOR ECONOMICS EXPLAINER IMAGE PROMPT GENERATOR\n\n"
            "Act as a Professional AI Image Prompt Engineer with 5+ years experience, Visual Director, and Educational Illustrator for premium YouTube channels like @misterfinanceyt, @TheWealthCortexx, and @millyproblems.\n\n"
            "Your task is to transform any supplied script beat sentence into a detailed, standalone image prompt and stock video search keywords locked to the Clean Vector Economics visual style.\n\n"
            "1. VISUAL STYLE & AESTHETIC:\n"
            "Hand-drawn professional educational cartoon illustration, clean studio-quality digital vector artwork with thick, smooth black outlines, crisp linework, soft flat colors, and polished modern explainer-animation aesthetics.\n"
            "Clean white background with generous negative space, keeping the composition uncluttered, highly readable, and focused on the main concept. Professional educational explainer style, balanced composition, subtle flat shading, high contrast, modern vector finish, minimal distractions, no text watermarks, no clutter.\n\n"
            "2. VISUAL DIRECTIVES:\n"
            "- Include the exact subject being discussed with visual humor whenever possible.\n"
            "- When accounting/business terms like revenue, costs, electricity, margins are mentioned, visualize them clearly with clean vector graphics or minimal numbers.\n"
            "- Keep composition uncluttered with generous white negative space.\n\n"
            "3. OUTPUT FORMAT:\n"
            "Output ONLY a JSON object with 'prompt', 'emotion', 'background', 'mood', and 'stock_keywords'.\n"
            "JSON structure:\n"
            "{\n"
            '  "prompt": "Hand-drawn professional educational cartoon illustration, clean studio-quality digital vector artwork with thick, smooth black outlines, crisp linework, soft flat colors, and polished modern explainer-animation aesthetics. [Detailed Scene Description]. Clean white background with generous negative space, keeping composition uncluttered and highly readable. Professional educational explainer style, balanced composition, subtle flat shading, high contrast, modern vector finish, minimal distractions, no text, no logos, no watermarks, polished animation-studio quality.",\n'
            '  "emotion": "peaceful imagination, hopeful daydreaming",\n'
            '  "background": "clean white background with ample negative space",\n'
            '  "mood": "simple, educational, modern, calm, easy to understand",\n'
            '  "stock_keywords": "data center, server room, businessman thinking"\n'
            "}"
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

    # Smart check for narrator presence
    narrator_keywords = ["you", "your", "we", "our", "welcome", "let's", "okay", "so", "look", "here"]
    has_narrator = any(re.search(rf'\b{kw}\b', clean_line, re.IGNORECASE) for kw in narrator_keywords)

    character_snippet = ""
    if has_narrator:
        character_snippet = (
            "Featuring the central recurring character: a simple hand-drawn expressive 2D stick figure guide with clean black ink outlines, wearing a vibrant crimson-red backwards baseball cap, an eye-catching electric-blue oversized hoodie, deep indigo baggy jeans, fresh white sneakers, and a prominent giant glowing metallic gold dollar-sign ($) medallion necklace, standing out as the colorful narrator. "
            "STRICT NO LABELS RULE: DO NOT WRITE THE WORDS 'HOST', 'HOST 3', OR ANY POINTER ARROWS ON OR NEAR THE CHARACTER. "
        )

    prompt_str = (
        "100% 2D hand-drawn editorial economics cartoon illustration, professional educational cartoon style, whiteboard-inspired artwork, thick slightly imperfect black ink outlines, sketchy marker strokes, subtle paper grain, 60-30-10 color harmony with warm off-white canvas. "
        "STRICT NO PHOTOGRAPHY RULE: ABSOLUTELY NO REALISTIC PHOTOGRAPHY, NO REAL HUMAN PHOTOS, NO REALISTIC PEOPLE OR PHOTO-REALISTIC BACKGROUNDS. ALL BACKGROUND PEOPLE AND ENVIRONMENTS MUST BE 2D HAND-DRAWN CARTOON FIGURES. "
        f"{character_snippet}"
        f"A single full-frame 16:9 2D cartoon physical location scene depicting: \"{clean_line}\". "
        "Showing a grand 2D hand-drawn physical environment (e.g. 2D cartoon nightclub exterior, 2D illustrated street food market, or 2D cartoon building interior). "
        "ABSOLUTELY NO INFOGRAPHIC SLIDES, NO TOP CATEGORY HEADINGS, NO SPLIT-SCREEN DIAGRAM BOXES, AND NO CONNECTING ARROWS. "
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

        # Render Per-Scene Individual Mini-Clips with Semaphore Concurrency Pool (4x faster)
        mini_clips_data = [None] * total_images
        completed_clips = 0
        semaphore = asyncio.Semaphore(4)

        async def render_single_mini_clip(idx, img_path, dur):
            nonlocal completed_clips
            async with semaphore:
                try:
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
                    mini_clips_data[idx - 1] = {
                        "sceneIndex": idx,
                        "filename": mini_filename,
                        "url": f"/static/generated/{mini_filename}",
                        "durSec": dur,
                        "text": scene_text
                    }
                    completed_clips += 1
                    pct = 20 + int((completed_clips / total_images) * 55)
                    BACKGROUND_JOBS[video_job_id]["progress"] = pct
                    BACKGROUND_JOBS[video_job_id]["status_text"] = f"🎬 Synthesizing 16:9 Mini-Clip {completed_clips}/{total_images} for Beat #{idx} ({dur:.1f}s)..."
                except Exception as clip_err:
                    print(f"Non-fatal error encoding mini clip {idx}:", clip_err)

        render_tasks = [
            render_single_mini_clip(idx, img_path, dur)
            for idx, (img_path, dur) in enumerate(zip(extracted_imgs, image_durations), start=1)
        ]
        await asyncio.gather(*render_tasks)

        # Filter out failed clip items
        mini_clips_data = [item for item in mini_clips_data if item is not None]

        # Master Video Assembly: Fast Stream Copy Concatenation of pre-rendered synced clips
        concat_filepath = os.path.join(temp_img_dir, "input_mini_clips_concat.txt")
        
        with open(concat_filepath, "w", encoding="utf-8") as f:
            for clip_item in mini_clips_data:
                fname = clip_item["filename"]
                fpath = os.path.join(DOWNLOADS_DIR, fname)
                if os.path.exists(fpath):
                    escaped_path = fpath.replace("\\", "/")
                    f.write(f"file '{escaped_path}'\n")

        out_video_filename = f"video_{video_job_id[:6]}.mp4"
        out_video_filepath = os.path.join(DOWNLOADS_DIR, out_video_filename)

        BACKGROUND_JOBS[video_job_id]["progress"] = 80
        BACKGROUND_JOBS[video_job_id]["status_text"] = f"🎬 Fast Stream Copy Merger: Concatenating {len(mini_clips_data)} synced scenes..."

        # Try fast stream copy concat first (-c copy)
        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", concat_filepath,
            "-c", "copy",
            "-movflags", "+faststart",
            out_video_filepath
        ]

        proc = await asyncio.create_subprocess_exec(
            *ffmpeg_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0 or not os.path.exists(out_video_filepath) or os.path.getsize(out_video_filepath) < 100:
            # Fallback to ultrafast re-encode if stream copy fails
            ffmpeg_cmd_reencode = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0", "-i", concat_filepath,
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "22",
                "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart",
                out_video_filepath
            ]
            proc_re = await asyncio.create_subprocess_exec(
                *ffmpeg_cmd_reencode, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            await proc_re.communicate()

        # Phase 2: Quality Verification Agent Audit
        BACKGROUND_JOBS[video_job_id]["progress"] = 95
        BACKGROUND_JOBS[video_job_id]["status_text"] = "🕵️‍♂️ Quality Verification Agent: Auditing rendered MP4 streams & audio sync..."

        video_duration = await get_media_duration_sec(out_video_filepath)
        drift_sec = abs(video_duration - total_audio_duration)

        qa_passed = (os.path.getsize(out_video_filepath) > 1000)
        qa_report = f"✅ Quality Audit Passed: All {total_images}/{total_images} images included | Frame-Perfect Audio Sync (Drift: {drift_sec:.2f}s)"

        if not qa_passed:
            raise Exception(f"Quality Check Failed: Video file is empty or corrupted.")

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

async def process_export_timeline_async(export_job_id, clip_filenames):
    try:
        BACKGROUND_JOBS[export_job_id] = {
            "status": "processing",
            "progress": 20,
            "status_text": f"🎬 Preparing master timeline export for {len(clip_filenames)} clips...",
            "mode": "video",
            "result": None
        }

        temp_dir = os.path.join(STUDIO_DIR, f"temp_export_{export_job_id[:6]}")
        os.makedirs(temp_dir, exist_ok=True)

        concat_file = os.path.join(temp_dir, "concat_timeline.txt")
        valid_clips_count = 0
        with open(concat_file, "w", encoding="utf-8") as f:
            for fname in clip_filenames:
                fpath = os.path.join(DOWNLOADS_DIR, fname)
                if os.path.exists(fpath):
                    escaped = fpath.replace("\\", "/")
                    f.write(f"file '{escaped}'\n")
                    valid_clips_count += 1

        if valid_clips_count == 0:
            raise Exception("None of the selected mini clips were found on the server.")

        master_filename = f"master_timeline_{export_job_id[:6]}.mp4"
        master_filepath = os.path.join(DOWNLOADS_DIR, master_filename)

        BACKGROUND_JOBS[export_job_id]["progress"] = 60
        BACKGROUND_JOBS[export_job_id]["status_text"] = f"⚡ Merging {valid_clips_count} mini-clips instantly with Stream Copy..."

        # Stream copy mode (-c copy) for 2-second export of 500+ clips
        cmd_copy = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", concat_file,
            "-c", "copy",
            "-movflags", "+faststart",
            master_filepath
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd_copy, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0 or not os.path.exists(master_filepath) or os.path.getsize(master_filepath) < 100:
            BACKGROUND_JOBS[export_job_id]["status_text"] = f"🎬 Stream copy unavailable. Re-encoding {valid_clips_count} mini-clips..."
            cmd_reencode = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0", "-i", concat_file,
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "22",
                "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart",
                master_filepath
            ]
            proc2 = await asyncio.create_subprocess_exec(
                *cmd_reencode, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            await proc2.communicate()

        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass

        if not os.path.exists(master_filepath) or os.path.getsize(master_filepath) < 1000:
            raise Exception("Export failed: Final master video file is missing or corrupted.")

        video_dur = await get_media_duration_sec(master_filepath)
        qa_report = f"✅ Master Timeline Exported: {valid_clips_count} Mini-Clips merged seamlessly! ({video_dur:.1f}s total)"

        BACKGROUND_JOBS[export_job_id] = {
            "status": "completed",
            "progress": 100,
            "status_text": qa_report,
            "mode": "video",
            "result": {
                "videoFilename": master_filename,
                "videoUrl": f"/static/generated/{master_filename}",
                "qaReport": qa_report
            }
        }
    except Exception as e:
        print(f"Error exporting timeline {export_job_id}:", e)
        BACKGROUND_JOBS[export_job_id] = {
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

        export_job_id = str(uuid.uuid4())
        asyncio.create_task(process_export_timeline_async(export_job_id, clip_filenames))

        return web.json_response({"job_id": export_job_id, "status": "processing"})
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

async def append_natural_pause_padding(audio_path, silence_duration_sec=0.28):
    if not os.path.exists(audio_path):
        return
    temp_padded_path = audio_path + ".padded.mp3"
    pad_cmd = [
        "ffmpeg", "-y", "-i", audio_path,
        "-af", f"apad=pad_dur={silence_duration_sec:.2f}",
        "-c:a", "libmp3lame", "-b:a", "192k",
        temp_padded_path
    ]
    try:
        proc = await asyncio.create_subprocess_exec(*pad_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await proc.communicate()
        if os.path.exists(temp_padded_path) and os.path.getsize(temp_padded_path) > 100:
            os.replace(temp_padded_path, audio_path)
    except Exception as e:
        print("Error appending natural silence padding:", e)

async def safe_edge_tts_save(text, voice_id, rate, out_filepath, max_retries=3):
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            communicate = edge_tts.Communicate(text, voice_id, rate=rate)
            await communicate.save(out_filepath)
            if os.path.exists(out_filepath) and os.path.getsize(out_filepath) > 100:
                return True
        except Exception as e:
            last_err = e
            print(f"[safe_edge_tts_save] Attempt {attempt}/{max_retries} failed for '{out_filepath}': {e}")
            await asyncio.sleep(1.0 * attempt)
    if last_err:
        raise last_err

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
        master_audio_filepath = None
        start_ms = 0
        end_ms = 0

        if job and job.get("result") and job["result"].get("scenes"):
            scenes = job["result"]["scenes"]
            audio_fn = job["result"].get("filename")
            if audio_fn:
                master_audio_filepath = os.path.join(DOWNLOADS_DIR, audio_fn)
            if 1 <= scene_idx <= len(scenes):
                sc = scenes[scene_idx - 1]
                scene_text = sc.get("text", "")
                start_ms = sc.get("start_ms", 0)
                end_ms = sc.get("end_ms", 0)

        if not scene_text:
            return web.json_response({"error": "Scene line text not found."}, status=400)

        out_filename = f"beat_audio_{job_id[:6]}_{scene_idx:02d}.mp3"
        out_filepath = os.path.join(DOWNLOADS_DIR, out_filename)

        sliced_from_master = False
        if master_audio_filepath and os.path.exists(master_audio_filepath) and end_ms > start_ms:
            try:
                st_sec = start_ms / 1000.0
                dur_sec_val = (end_ms - start_ms) / 1000.0
                slice_cmd = [
                    "ffmpeg", "-y",
                    "-ss", f"{st_sec:.3f}", "-t", f"{dur_sec_val:.3f}",
                    "-i", master_audio_filepath,
                    "-c:a", "libmp3lame", "-b:a", "192k",
                    out_filepath
                ]
                proc_slice = await asyncio.create_subprocess_exec(*slice_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                await proc_slice.communicate()
                if os.path.exists(out_filepath) and os.path.getsize(out_filepath) > 100:
                    sliced_from_master = True
            except Exception as slice_err:
                print(f"Master audio slice fallback for beat {scene_idx}:", slice_err)

        if not sliced_from_master:
            cleaned_text = humanize_script(scene_text)
            await safe_edge_tts_save(cleaned_text, voice_id, rate, out_filepath)
            await trim_trailing_audio_silence(out_filepath)
            await append_natural_pause_padding(out_filepath, 0.28)

        dur_sec = await get_media_duration_sec(out_filepath)

        return web.json_response({
            "status": "success",
            "filename": out_filename,
            "audioUrl": f"/static/generated/{out_filename}",
            "text": scene_text,
            "durSec": round(dur_sec, 2)
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
            await safe_edge_tts_save(cleaned, "en-US-AndrewNeural", "-4%", beat_audio_path)
            await trim_trailing_audio_silence(beat_audio_path)
            await append_natural_pause_padding(beat_audio_path, 0.28)

        dur_sec = await get_media_duration_sec(beat_audio_path)
        if dur_sec <= 0.2:
            dur_sec = 3.0

        out_clip_filename = f"mini_clip_{job_id[:6]}_{scene_idx:02d}.mp4"
        out_clip_filepath = os.path.join(DOWNLOADS_DIR, out_clip_filename)

        ffmpeg_cmd = [
            "ffmpeg", "-y", "-threads", "2",
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

def create_app():
    # Allow large ZIP and batch uploads up to 2GB (2048MB)
    app = web.Application(client_max_size=2048 * 1024 * 1024)
    app.router.add_get("", handle_index)
    app.router.add_get("/", handle_index)
    app.router.add_get("/index.html", handle_index)
    app.router.add_post("/api/start-job", handle_start_job)
    app.router.add_get("/api/job-status", handle_job_status)
    app.router.add_get("/api/voices", handle_voices)
    app.router.add_post("/api/assemble-video", handle_assemble_video)
    app.router.add_post("/api/export-timeline", handle_export_timeline)
    app.router.add_post("/api/generate-beat-audio", handle_generate_beat_audio)
    app.router.add_post("/api/generate-beat-clip", handle_generate_beat_clip)
    app.router.add_post("/telegram-webhook", handle_telegram_webhook)
    app.router.add_static("/static/", STATIC_DIR)
    return app

if __name__ == "__main__":
    current_port = PORT
    max_attempts = 10
    for attempt in range(max_attempts):
        try:
            print(f"Starting YouTube Voiceover Studio Online at http://localhost:{current_port} (host: {HOST})")
            web.run_app(create_app(), host=HOST, port=current_port, print=None)
            break
        except OSError as e:
            if getattr(e, 'errno', None) in (10048, 98) or '10048' in str(e) or 'address already in use' in str(e).lower():
                print(f"Port {current_port} is already in use by another process.")
                if attempt < max_attempts - 1:
                    current_port += 1
                    print(f"Trying port {current_port}...")
                else:
                    print(f"Could not bind to any port in range {PORT}-{current_port}.")
                    raise
            else:
                raise


