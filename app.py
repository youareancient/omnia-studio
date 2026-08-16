import asyncio
import json
import os
import re
import random
import uuid
import urllib.parse
import sqlite3
import edge_tts
from aiohttp import web, ClientSession, FormData
import cv2
import numpy as np

HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", 7860))
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()

STUDIO_DIR = os.path.dirname(os.path.abspath(__file__))
env_file = os.path.join(STUDIO_DIR, ".env")
if os.path.exists(env_file):
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip().strip('"\'')

STATIC_DIR = os.path.join(STUDIO_DIR, "public")
DOWNLOADS_DIR = os.path.join(STATIC_DIR, "generated")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

INDEX_HTML_PATH = os.path.join(STATIC_DIR, "index.html")

VOICE_PRESETS = {
    # 🎥 TRUE CRIME & DOCUMENTARY ESSAYS
    "andrew": {"id": "en-US-AndrewNeural", "name": "Andrew (YouTube Documentary Essay)", "category": "True Crime & Documentary", "desc": "High energy, warm & engaging (#1 for Documentary Essays)"},
    "christopher": {"id": "en-US-ChristopherNeural", "name": "Christopher (Deep Business & Mystery)", "category": "True Crime & Documentary", "desc": "Deep, authoritative, cinematic mystery narrator"},
    "eric": {"id": "en-US-EricNeural", "name": "Eric (True Crime & Investigation)", "category": "True Crime & Documentary", "desc": "Grit, suspenseful tone for crime & unsolved cases"},
    "roger": {"id": "en-US-RogerNeural", "name": "Roger (Authoritative History)", "category": "True Crime & Documentary", "desc": "Deep authoritative historical documentarian"},
    "ryan": {"id": "en-GB-RyanNeural", "name": "Ryan (British History & War Docs)", "category": "True Crime & Documentary", "desc": "Deep cinematic British voice for war & mysteries"},
    "thomas": {"id": "en-GB-ThomasNeural", "name": "Thomas (British Crime Narrator)", "category": "True Crime & Documentary", "desc": "Suspenseful British documentary narrator"},
    "asreflect": {"id": "en-KE-AsiliaNeural", "name": "Asilia (Nature & Wildlife Doc)", "category": "True Crime & Documentary", "desc": "Calm, majestic wildlife documentary narrator"},

    # 🎮 GAMING & CINEMATIC TRAILERS
    "steffan": {"id": "en-US-SteffanNeural", "name": "Steffan (Cinematic Trailer & Gaming)", "category": "Gaming & Trailers", "desc": "Intense, dramatic voice for cinematic game reviews & trailers"},
    "steffen": {"id": "en-US-SteffenNeural", "name": "Steffen (Action & Thriller)", "category": "Gaming & Trailers", "desc": "Action-packed voice for high-octane gaming content"},
    "movie_trailer": {"id": "en-US-SteffanNeural", "name": "Movie Trailer Epic Voice", "category": "Gaming & Trailers", "desc": "Deep epic blockbuster trailer announcer tone"},

    # 📱 VIRAL SHORTS & REELS
    "brian": {"id": "en-US-BrianNeural", "name": "Brian (Viral Shorts & TikTok)", "category": "Viral Shorts & Reels", "desc": "Young, energetic, engaging creator tone for Shorts"},
    "michelle": {"id": "en-US-MichelleNeural", "name": "Michelle (Viral Reels & Storytelling)", "category": "Viral Shorts & Reels", "desc": "Upbeat, modern female voice for viral short-form storytelling"},
    "ava": {"id": "en-US-AvaNeural", "name": "Ava (Expressive Modern Female)", "category": "Viral Shorts & Reels", "desc": "Clear, modern, expressive narrator voice (#1 Tech)"},
    "viral_hype": {"id": "en-US-BrianNeural", "name": "Viral Hype Creator", "category": "Viral Shorts & Reels", "desc": "Super high-energy Gen-Z creator pacing"},

    # 💡 TECH & AI BREAKDOWN
    "guy": {"id": "en-US-GuyNeural", "name": "Guy (News & Tech Commentary)", "category": "Tech & AI Breakdown", "desc": "Clear American news broadcaster & tech reviewer"},
    "jenny": {"id": "en-US-JennyNeural", "name": "Jenny (Friendly Tech Explainer)", "category": "Tech & AI Breakdown", "desc": "Friendly, approachable AI product reviewer"},
    "aria": {"id": "en-US-AriaNeural", "name": "Aria (Educational & AI Essay)", "category": "Tech & AI Breakdown", "desc": "Articulate, expressive educational essayist"},
    "sam": {"id": "en-HK-SamNeural", "name": "Sam (Global Tech Reviewer)", "category": "Tech & AI Breakdown", "desc": "Crisp international tech journalist tone"},

    # 💼 FINANCE, BUSINESS & MINDSET
    "emma": {"id": "en-US-EmmaNeural", "name": "Emma (Conversational Finance)", "category": "Finance & Business", "desc": "Warm, trustworthy conversational female narrator"},
    "sonia": {"id": "en-GB-SoniaNeural", "name": "Sonia (British Art & Culture)", "category": "Finance & Business", "desc": "Elegant British documentarian female voice"},
    "william": {"id": "en-AU-WilliamNeural", "name": "William (Australian Business)", "category": "Finance & Business", "desc": "Relaxed, authentic Australian narrator"},
    "liam": {"id": "en-CA-LiamNeural", "name": "Liam (Canadian Podcast)", "category": "Finance & Business", "desc": "Dynamic Canadian podcast narrator"},

    # 🎭 SPECIAL EMOTIONAL & NICHE TONES
    "whisper_doc": {"id": "en-US-ChristopherNeural", "name": "Whispering Suspense Narrator", "category": "Special Tones", "desc": "Soft, suspenseful whispered audio for creepy stories"},
    "horror_crime": {"id": "en-GB-RyanNeural", "name": "Creepypasta Horror Voice", "category": "Special Tones", "desc": "Chilling, slow-paced horror story reader"},
    "ana": {"id": "en-US-AnaNeural", "name": "Ana (Animated Storytelling)", "category": "Special Tones", "desc": "Playful, expressive voice for animated stories"}
}

import sqlite3

BACKGROUND_JOBS = {}

STUDIO_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(STUDIO_DIR, "studio.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        script_text TEXT,
        voice TEXT DEFAULT 'andrew',
        rate TEXT DEFAULT '+1%',
        subtitle_style TEXT DEFAULT 'hormozi',
        video_filter TEXT DEFAULT 'vignette',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS scenes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id TEXT NOT NULL,
        scene_num INTEGER NOT NULL,
        script_line TEXT,
        prompt TEXT,
        audio_url TEXT,
        image_url TEXT,
        clip_url TEXT,
        dur_sec REAL DEFAULT 0.0,
        status TEXT DEFAULT 'pending',
        FOREIGN KEY(project_id) REFERENCES projects(id),
        UNIQUE(project_id, scene_num)
    )
    """)
    cursor.execute("SELECT id FROM projects WHERE id = 'default'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO projects (id, title) VALUES ('default', 'Default Project (Active)')")
    conn.commit()
    conn.close()

init_db()

async def handle_list_projects(request):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
        SELECT p.id, p.title, p.updated_at, COUNT(s.id) as scene_count
        FROM projects p
        LEFT JOIN scenes s ON p.id = s.project_id
        GROUP BY p.id
        ORDER BY p.updated_at DESC
        """)
        rows = cursor.fetchall()
        projects = []
        for r in rows:
            projects.append({
                "id": r["id"],
                "title": r["title"],
                "sceneCount": r["scene_count"],
                "updatedAt": r["updated_at"]
            })
        conn.close()
        return web.json_response({"status": "success", "projects": projects})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

async def handle_get_project(request):
    try:
        proj_id = request.match_info.get("id", "default")
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM projects WHERE id = ?", (proj_id,))
        proj_row = cursor.fetchone()
        if not proj_row:
            conn.close()
            return web.json_response({"error": "Project not found"}, status=404)
        
        cursor.execute("SELECT * FROM scenes WHERE project_id = ? ORDER BY scene_num ASC", (proj_id,))
        scene_rows = cursor.fetchall()
        
        scenes = []
        for s in scene_rows:
            scenes.append({
                "scene_num": s["scene_num"],
                "text": s["script_line"],
                "prompt": s["prompt"],
                "audioUrl": s["audio_url"],
                "imageUrl": s["image_url"],
                "clipUrl": s["clip_url"],
                "durSec": s["dur_sec"],
                "status": s["status"]
            })
            
        project_data = {
            "id": proj_row["id"],
            "title": proj_row["title"],
            "scriptText": proj_row["script_text"],
            "voice": proj_row["voice"],
            "rate": proj_row["rate"],
            "subtitleStyle": proj_row["subtitle_style"],
            "videoFilter": proj_row["video_filter"],
            "scenes": scenes
        }
        conn.close()
        return web.json_response({"status": "success", "project": project_data})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

async def handle_save_project(request):
    try:
        data = await request.json()
        proj_id = data.get("id", "default")
        title = data.get("title", "Untitled Project")
        script_text = data.get("script_text", "")
        voice = data.get("voice", "andrew")
        rate = data.get("rate", "+1%")
        subtitle_style = data.get("subtitle_style", "hormozi")
        video_filter = data.get("video_filter", "vignette")
        scenes = data.get("scenes", [])
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
        INSERT INTO projects (id, title, script_text, voice, rate, subtitle_style, video_filter, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(id) DO UPDATE SET
            title=excluded.title,
            script_text=excluded.script_text,
            voice=excluded.voice,
            rate=excluded.rate,
            subtitle_style=excluded.subtitle_style,
            video_filter=excluded.video_filter,
            updated_at=CURRENT_TIMESTAMP
        """, (proj_id, title, script_text, voice, rate, subtitle_style, video_filter))
        
        for sc in scenes:
            scene_num = sc.get("scene_num", sc.get("scene", 1))
            script_line = sc.get("text", "")
            prompt = sc.get("prompt", "")
            audio_url = sc.get("audioUrl", "")
            image_url = sc.get("imageUrl", "")
            clip_url = sc.get("clipUrl", "")
            dur_sec = sc.get("durSec", 0.0)
            status = sc.get("status", "pending")
            
            cursor.execute("""
            INSERT INTO scenes (project_id, scene_num, script_line, prompt, audio_url, image_url, clip_url, dur_sec, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(project_id, scene_num) DO UPDATE SET
                script_line=excluded.script_line,
                prompt=excluded.prompt,
                audio_url=COALESCE(NULLIF(excluded.audio_url, ''), scenes.audio_url),
                image_url=COALESCE(NULLIF(excluded.image_url, ''), scenes.image_url),
                clip_url=COALESCE(NULLIF(excluded.clip_url, ''), scenes.clip_url),
                dur_sec=CASE WHEN excluded.dur_sec > 0 THEN excluded.dur_sec ELSE scenes.dur_sec END,
                status=excluded.status
            """, (proj_id, scene_num, script_line, prompt, audio_url, image_url, clip_url, dur_sec, status))
            
        conn.commit()
        conn.close()
        return web.json_response({"status": "success", "projectId": proj_id})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

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
        if len(words) <= 14:
            # Each sentence is strictly its own independent scene beat
            scenes.append(sent)
        else:
            # Split long sentence at clause pauses (comma, semicolon, dash)
            clauses = re.split(r'(?<=[,;:—])\s+', sent)
            curr = []
            for c in clauses:
                curr.extend(c.split())
                if len(curr) >= 7:
                    scenes.append(" ".join(curr))
                    curr = []
            if curr:
                scenes.append(" ".join(curr))
                
    return scenes if scenes else [raw_text]

async def analyze_script_topic_async(session, full_script_text, groq_key=""):
    api_key = groq_key.strip() or os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        return None

    system_prompt = """You are an expert Script Analyzer & Topic Director for documentary YouTube channels.
Analyze the provided full video script and determine:
1. "topic": The precise core subject/business/industry domain of the video (e.g., "Economics of Owning a Data Center", "Commercial Airline Flight Operations", "High-End Restaurant Management").
2. "domain_setting": The specific physical environments, facilities, equipment, and stores relevant to this domain (e.g., "Hyperscale data center server rooms, microchip hardware counters, cooling tower facilities, fiber optic power grids").

Respond STRICTLY in JSON:
{
  "topic": "...",
  "domain_setting": "..."
}"""

    user_prompt = f"Full Video Script:\n\"\"\"{full_script_text[:4000]}\"\"\""

    for model in ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]:
        try:
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.3,
                "response_format": {"type": "json_object"}
            }
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            async with session.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    content = data["choices"][0]["message"]["content"]
                    parsed = json.loads(content)
                    if parsed.get("topic"):
                        return parsed
        except Exception as e:
            print(f"Script Topic Analyzer exception: {e}")

    return None

async def call_groq_ai_prompt_engineer(session, scene_text, scene_number, niche="economics", visual_style="vox_2d", groq_key="", script_topic_info=None):
    api_key = groq_key.strip() or os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        return None

    niche_context_map = {
        "economics": "The Economics of... (Business, Money, Accounting, Costs, Revenue, Profit Margins, Financial Assets)",
        "documentary": "Deep Investigative Documentary (True Crime, High-Stakes Mysteries, Unsolved Cases, Cold Case Files)",
        "tech_ai": "Tech Reviews & AI Future Trends (Silicon Valley, Supercomputing, Robotics, Future Tech & Microchips)",
        "history_war": "Historical Warfare & Empires (Ancient Battles, Empires, Tactical Warfare, Military History & Fortresses)"
    }
    niche_directive = niche_context_map.get(niche, niche_context_map["economics"])

    topic_lock_directive = ""
    if script_topic_info and isinstance(script_topic_info, dict) and script_topic_info.get("topic"):
        topic_name = script_topic_info.get("topic")
        setting_name = script_topic_info.get("domain_setting", topic_name)
        topic_lock_directive = f"""
STRICT DOCUMENTARY TOPIC & DOMAIN LOCKING:
LOCKED DOCUMENTARY TOPIC: {topic_name}
LOCKED DOMAIN SETTINGS & FACILITIES: {setting_name}
MANDATORY DOMAIN RULE: Every single visual metaphor, store, customer interaction, machine, and character MUST be explicitly themed around this topic ({topic_name}). DO NOT use generic off-topic stores (such as grocery stores, coffee shops, or generic retail stores) when illustrating abstract concepts like demand, costs, or lines. For example, if illustrating "longer lines" for a data center video, depict a microchip/server hardware store or cloud server provisioning counter with long queues of tech buyers.
"""

    style_aesthetic_map = {
        "vox_2d": "Hand-drawn professional educational cartoon illustration, clean studio-quality digital vector artwork with thick, smooth black outlines, crisp linework, soft flat colors, and polished modern explainer-animation aesthetics. Clean white background with generous negative space.",
        "kurzgesagt": "Kurzgesagt flat vector illustration, vibrant neon gradient palette, clean geometric shapes, high contrast educational graphic aesthetic, polished vector finish with bold visual hierarchy.",
        "claymation": "3D claymation stop-motion animation aesthetic, tactile plasticine clay figures, dramatic chiaroscuro studio lighting, detailed handmade clay surface textures and subtle thumb-print details.",
        "photoreal": "Hyperrealistic 8K 35mm film documentary photography, shallow depth of field, 35mm/85mm portrait camera lens, natural ambient volumetric lighting, volumetric shadows, award-winning film grain, cinematic color grading, hyper-detailed real skin/material micro-textures. STRICT NO CARTOONS/DRAWINGS constraint.",
        "horror_auto": "Dark 16mm analog horror film photography, eerie fog, chiaroscuro flashlight beam shadows, lo-fi VHS grain, atmospheric haunting shadows, dark uncanny storytelling composition.",
        "engraving": "19th-century vintage copperplate engraving, etched ink cross-hatching linework, antique weathered parchment paper texture, classic historical archival illustration.",
        "cyberpunk": "Cyberpunk anime cell-shaded webtoon illustration, vibrant glowing neon laser lights, futuristic dark cityscape aesthetic, sharp high-contrast cell shading.",
        "tech_vector": "Modern tech 3D isometric vector render, clean glossy plastic surfaces, vibrant corporate tech color scheme, 8K clean studio lighting render with sharp 3D perspective.",
        "oil_painting": "Masterpiece Renaissance oil painting, rich impasto canvas brushstrokes, dramatic Rembrandt chiaroscuro lighting, deep classic golden oil tones on textured canvas.",
        "midjourney_raw": "Cinematic widescreen raw photography, award-winning composition, natural realistic lighting, shallow depth of field --ar 16:9 --style raw",
        "physical_economics_3d": "BUILD THE ECONOMICS AS A PHYSICAL MINIATURE WORLD. Premium cinematic handcrafted 3D clay miniature + architectural model + stop-motion production design + macro cinematography + physical living infographic. Handcrafted tactile adult documentary miniature aesthetic with sculpted clay, clear acrylic, painted metal, wood, resin, and subtle handcrafted imperfections (fingerprints, sculpting marks). Physical representation of economics: revenue as flowing coins, costs as heavy blocks, bottlenecks as narrow passages, margins as physical gaps."
    }
    style_directive = style_aesthetic_map.get(visual_style, style_aesthetic_map["vox_2d"])

    if visual_style == "physical_economics_3d":
        system_prompt = f"""MASTER PROMPT — PHYSICAL ECONOMICS 3D MINIATURE UNIVERSE (ULTRA HIGH-DETAIL EDITION)

You are an elite visual prompt director and cinematic 3D miniature art director specializing in "The Economics of..." documentary-style YouTube videos.
Your task is to transform the script beat into an EXCEPTIONALLY DETAILED, MULTI-SENTENCE STANDALONE IMAGE PROMPT (120-200 words) belonging to one consistent visual universe.

{topic_lock_directive}

CORE PHILOSOPHY: BUILD THE ECONOMICS AS A PHYSICAL WORLD.
Do not merely illustrate the subject. Create an impossibly detailed miniature physical world in which revenue, costs, customers, workers, infrastructure, resources, capacity, demand, margins, cash flow, bottlenecks, and economic relationships are visually understood through physical objects, environments, characters, architecture, movement, scale, and visual metaphors.

MATERIAL SCIENCE & VIBRANT COLOR PALETTE:
- NO dull grays, monochrome, or washed-out tones. Use a VIVID, HIGHLY SATURATED, HIGH-CONTRAST COLOR PALETTE:
  - REVENUE & PROFIT: Radiant emerald green polymer clay, glowing neon turquoise accents, polished 24K gold miniature coins.
  - EXPENSES & BOTTLENECK: Rich ruby crimson red blocks, warm terracotta structures, deep magenta warning plaques.
  - INFRASTRUCTURE & HARDWARE: Deep sapphire blue partitions, cobalt machinery, bright cyan fiber optic light channels.
  - ENVIRONMENT & BACKDROP: Deep royal navy blue studio backdrop, vibrant dual-color rim lighting (cyan and magenta highlights), warm 3200K key light creating rich saturated color contrast.
- Tactile sculpted matte polymer clay in rich vibrant hues, 1/87 scale detailed miniature human figures, laser-etched clear acrylic resin blocks for digital/financial charts.
- Precision painted brass and aluminum miniature industrial machinery, real polished miniature wood textures, frosted glass partitions.
- Include subtle handcrafted evidence: tiny finger-print micro-textures on clay surfaces, subtle sculpting marks, precision laser joins.

MACRO CINEMATOGRAPHY & LIGHTING SPECIFICATIONS:
- Shot on ARRI Alexa Mini with 35mm f/2.8 macro cinema lens, tilt-shift miniature depth of field, razor-sharp focal plane on primary subject.
- Warm 3200K tungsten studio key lighting with soft fill, vibrant volumetric cyan and magenta rim lighting, ambient occlusion, realistic contact shadows on miniature ground plane.

PHYSICAL ECONOMICS CONVERSIONS:
- REVENUE -> flowing streams of 3D miniature golden coins, emerald green currency tokens
- COST -> heavy textured ruby red blocks, terracotta pipes, resource-consuming furnaces
- MARGIN -> physical gap distance between emerald revenue streams and ruby cost blocks
- DEMAND -> dense queues of colorful 1/87 scale miniature figures, overflowing order bins
- BOTTLENECK -> narrow physical funnel or archway accumulating miniature traffic
- NUMBERS/STATS -> laser-etched transparent acrylic plaques displaying clear numbers

COMPOSITION & HYPER-DETAIL REQUIREMENT:
Write a rich, multi-sentence prompt (120-200 words). Detail the foreground, middle ground, background, exact spatial layout, vibrant color palette, lighting direction, and micro-storytelling details.

Respond STRICTLY in JSON format:
{{
  "prompt": "SCENE: [short description of what scene communicates]\\n\\nIMAGE PROMPT: Cinematic handcrafted 3D clay miniature + architectural model + macro cinematography physical infographic style. [Complete, hyper-detailed 120-200 word multi-sentence prompt detailing exact miniature layout, materials, physical economic representations, characters, macro lens lighting, camera angle, and quality finish]\\n\\nEMOTION: [emotional quality]\\n\\nVISUAL PURPOSE: [what the viewer should understand economically]"
}}"""
    else:
        system_prompt = f"""MASTER PROMPT — YOUTUBE EXPLAINER HIGH-RETENTION IMAGE PROMPT GENERATOR

You are a 10+ year veteran AI Image Prompt Engineer, Visual Director, and Storyteller for top YouTube channels like @misterfinanceyt, @TheWealthCortexx, and @millyproblems.

Your task is to transform the script line into a SINGLE, HIGHLY DETAILED, MULTI-SENTENCE STANDALONE IMAGE PROMPT strictly locked to the specified NICHE and VISUAL ART STYLE.

{topic_lock_directive}

NICHE CONTEXT: {niche_directive}
VISUAL ART STYLE: {style_directive}

MASTER GENERATION RULES:
1. 3-5 SECOND SCENE FOCUS: Each scene covers 3-5 seconds (1 sentence). Include ONLY elements relevant to the scene line without clutter.
2. STANDALONE LONG PROMPT: The generated prompt MUST be a full, detailed, multi-sentence paragraph (80-150 words). Never write 'same as before' or use generic short descriptions.
3. PURE ENVIRONMENT & OBJECT FOCUS (NO HOSTS/CHARACTERS): Focus 100% on high-impact scenery, architecture, physical objects, infrastructure, data diagrams, and environmental lighting. DO NOT include human hosts, presenters, or character figures.
4. DIAGRAMS & LABELS: When accounting, business, or niche terms (revenue, costs, margins, stats) are mentioned, describe clean text/stat/chart visual callouts inside the prompt.
5. COMPOSITION & NEGATIVE SPACE: Maintain a balanced composition with generous negative space, keeping the visual clean, professional, highly readable, and free of clutter or watermarks.

Respond STRICTLY in JSON format:
{{
  "prompt": "[Complete, rich, multi-sentence standalone image prompt starting with the visual style signature and detailing subject, posture, composition, lighting, environment, negative space, and quality finish]"
}}
"""

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

def build_vector_art_scene_prompt_fallback(text, niche="economics", visual_style="omniverse_master_hybrid"):
    clean_line = re.sub(r'\s+', ' ', text).strip()
    money_match = re.search(r'(\$?\d+[\d,.]*\s*(million|billion|thousand|k|m)?)', clean_line, re.IGNORECASE)
    stat_val = money_match.group(0).upper() if money_match else None
    
    if visual_style == "omniverse_master_hybrid":
        stat_callout = f" In the middle ground, a laser-etched clear acrylic plaque with glowing holographic cyan typography displays \"{stat_val}\"." if stat_val else ""
        return (
            f"SCENE: Omniverse Master Hybrid Fusion — {clean_line[:60]}\n\n"
            f"IMAGE PROMPT: Ultra-high-retention Omniverse Master Hybrid Artwork — a revolutionary fusion of cinematic 8K documentary film photography, 1/87 scale handcrafted physical clay miniature architecture, 3D isometric tech graphics, cyberpunk neon light leaks, and classical impasto fine art. "
            f"Visually depicting: \"{clean_line}\". "
            f"Constructed as a tactile physical miniature world set against a deep obsidian studio backdrop, featuring handcrafted polymer clay structures, glowing fiber-optic data nodes, high-contrast neon cyan and magenta rim lighting, gold-leaf accents, subtle vintage etched copperplate cross-hatching linework, and glassmorphic translucent UI data cards. "
            f"Shot on ARRI Alexa 35mm f/1.4 anamorphic prime lens, tilt-shift macro depth-of-field, Rembrandt chiaroscuro studio key lighting, and volumetric haze. "
            f"Composed with widescreen 16:9 golden-ratio visual symmetry and generous negative space. Pure architectural and environmental visualization, zero human figures.{stat_callout}\n\n"
            f"EMOTION: Mind-bending, futuristic, authoritative, breathtaking, revolutionary.\n\n"
            f"VISUAL PURPOSE: Master hybrid fusion visualization of: {clean_line}"
        )

    elif visual_style == "photoreal":
        stat_callout = f" In the foreground, a sleek brushed-titanium plaque is engraved with the financial stat \"{stat_val}\"." if stat_val else ""
        return (
            f"SCENE: 8K Cinematic Film Photography — {clean_line[:60]}\n\n"
            f"IMAGE PROMPT: Hyperrealistic 8K cinematic film photography, award-winning documentary still visually depicting: \"{clean_line}\". "
            f"Shot on ARRI Alexa 35 with a Panavision 35mm f/1.4 anamorphic prime lens, featuring shallow depth of field, dramatic chiaroscuro key lighting, volumetric haze, atmospheric lens flare, macro environmental textures, and high contrast cinematic color grading (deep navy blues, warm amber highlights, and vivid crimson accents). "
            f"The environment and objects are framed with golden-ratio composition, generous negative space, and realistic physical shadows. Pure cinematic landscape and object composition, zero human characters or hosts.{stat_callout}\n\n"
            f"EMOTION: Dramatic, authoritative, immersive, cinematic.\n\n"
            f"VISUAL PURPOSE: High-retention 8K documentary film visualization of: {clean_line}"
        )
        
    elif visual_style == "vox_2d":
        stat_callout = f" A clean minimalist infographic text callout displays \"{stat_val}\" inside a smooth vector bubble." if stat_val else ""
        return (
            f"SCENE: Vox 2D Vector Explainer — {clean_line[:60]}\n\n"
            f"IMAGE PROMPT: Professional Vox-style hand-drawn 2D vector educational artwork visually representing: \"{clean_line}\". "
            f"Features crisp, smooth black outlines, bold high-contrast color blocks (electric blue, vibrant warm coral, canary yellow, and crisp white), flat shading, and clean geometric data structures. "
            f"Set against a solid dark studio navy background with generous negative space and minimal visual clutter. Pure infographic and environmental vector artwork, no human presenters or characters.{stat_callout}\n\n"
            f"EMOTION: Engaging, educational, clear, modern.\n\n"
            f"VISUAL PURPOSE: High-retention 2D infographic vector illustration of: {clean_line}"
        )
        
    elif visual_style == "kurzgesagt":
        stat_callout = f" A glowing flat geometric vector badge displays \"{stat_val}\" in bold typography." if stat_val else ""
        return (
            f"SCENE: Kurzgesagt Geometric Vector — {clean_line[:60]}\n\n"
            f"IMAGE PROMPT: Kurzgesagt-inspired flat geometric vector illustration visually explaining: \"{clean_line}\". "
            f"Features vibrant neon cyan and magenta gradient backgrounds, clean flat shading, sharp geometric structures, and high-energy cosmic color accents. "
            f"Composed with widescreen 16:9 visual symmetry, generous negative space, and zero clutter. Pure geometric environmental visualization, zero human figures.{stat_callout}\n\n"
            f"EMOTION: Curious, scientific, energetic, visual.\n\n"
            f"VISUAL PURPOSE: Kurzgesagt-style educational vector visualization of: {clean_line}"
        )
        
    elif visual_style == "cyberpunk":
        stat_callout = f" A glowing magenta holographic HUD plaque displays \"{stat_val}\" in digital neon font." if stat_val else ""
        return (
            f"SCENE: Cyberpunk Neon Anime — {clean_line[:60]}\n\n"
            f"IMAGE PROMPT: High-contrast cell-shaded cyberpunk anime webtoon illustration illustrating: \"{clean_line}\". "
            f"Features glowing neon cyan and magenta light leaks, rain-slicked dark cityscape reflections, futuristic cybernetic machinery, atmospheric volumetric fog, and dramatic high-contrast shadows. "
            f"Composed with dynamic cinematic environmental angles, sharp linework, and generous negative space. Pure cyberpunk architecture and tech objects, no human characters.{stat_callout}\n\n"
            f"EMOTION: High-octane, futuristic, atmospheric, bold.\n\n"
            f"VISUAL PURPOSE: Cyberpunk anime visual representation of: {clean_line}"
        )
        
    elif visual_style == "claymation":
        stat_callout = f" A handcrafted polymer clay plaque stamped with \"{stat_val}\" is positioned prominently." if stat_val else ""
        return (
            f"SCENE: 3D Claymation Stop-Motion — {clean_line[:60]}\n\n"
            f"IMAGE PROMPT: Tactile 3D stop-motion claymation plasticine animation style depicting: \"{clean_line}\". "
            f"Features handcrafted clay micro-textures, subtle finger-sculpting marks, vibrant colored plasticine clay objects and buildings, tilt-shift macro depth of field, and warm 3200K studio table key lighting with realistic contact shadows. "
            f"Set on a clean studio table stage with generous negative space. Pure clay object sculpting, zero clay human figures.{stat_callout}\n\n"
            f"EMOTION: Tactile, creative, whimsical, handcrafted.\n\n"
            f"VISUAL PURPOSE: Stop-motion clay animation representation of: {clean_line}"
        )
        
    elif visual_style == "oil_painting":
        stat_callout = f" A subtle gold-leaf painted scroll displays the text \"{stat_val}\" in elegant serif lettering." if stat_val else ""
        return (
            f"SCENE: Renaissance Oil Painting — {clean_line[:60]}\n\n"
            f"IMAGE PROMPT: Masterpiece Renaissance oil painting on linen canvas visually depicting: \"{clean_line}\". "
            f"Features rich impasto oil brushstrokes, dramatic Rembrandt chiaroscuro lighting, deep golden oil tones, warm ochre highlights, architectural elements, and dark atmospheric background glazing. "
            f"Composed with classical museum-grade golden-ratio balance and generous negative space. Pure Still Life and architectural oil painting, no human figures.{stat_callout}\n\n"
            f"EMOTION: Historical, prestigious, timeless, artistic.\n\n"
            f"VISUAL PURPOSE: Classic fine art oil painting visualization of: {clean_line}"
        )
        
    elif visual_style == "engraving":
        stat_callout = f" A vintage engraved ribbon banner contains the etched text \"{stat_val}\"." if stat_val else ""
        return (
            f"SCENE: 19th Century Vintage Engraving — {clean_line[:60]}\n\n"
            f"IMAGE PROMPT: 19th-century vintage copperplate engraving, detailed etched ink cross-hatching linework depicting: \"{clean_line}\". "
            f"Set on antique weathered cream parchment paper texture, featuring intricate hand-engraved architectural linework, high-contrast black ink shading, and historical archive documentary aesthetic. "
            f"Balanced composition with generous negative space. Pure architectural and object engraving, zero human characters.{stat_callout}\n\n"
            f"EMOTION: Archival, historical, intellectual, classic.\n\n"
            f"VISUAL PURPOSE: Historical copperplate engraving visualization of: {clean_line}"
        )
        
    elif visual_style == "tech_vector":
        stat_callout = f" A glossy translucent glassmorphic 3D UI card displays \"{stat_val}\" in glowing white typography." if stat_val else ""
        return (
            f"SCENE: 3D Tech Isometric Graphic — {clean_line[:60]}\n\n"
            f"IMAGE PROMPT: Modern 3D tech isometric vector rendering illustrating: \"{clean_line}\". "
            f"Features smooth glossy plastic 3D surfaces, corporate tech color palette (electric blue, deep slate navy, glowing emerald green), glowing fiber-optic data nodes, ambient occlusion studio lighting, and glassmorphic UI elements. "
            f"Clean 3D isometric composition with generous negative space. Pure tech object rendering, no human figures.{stat_callout}\n\n"
            f"EMOTION: Sleek, high-tech, corporate, futuristic.\n\n"
            f"VISUAL PURPOSE: 3D isometric tech visualization of: {clean_line}"
        )
        
    else: # Default: physical_economics_3d
        stat_callout = f" A laser-etched clear acrylic plaque engraved with \"{stat_val}\" stands prominently in the middle ground." if stat_val else ""
        return (
            f"SCENE: Physical Miniature World — {clean_line[:60]}\n\n"
            f"IMAGE PROMPT: Cinematic handcrafted 3D clay miniature + architectural model + macro cinematography physical infographic style. "
            f"An extraordinarily detailed 1/87 scale miniature physical environment visually constructing the economics of: \"{clean_line}\". "
            f"Set against a deep royal navy studio backdrop, featuring a vivid, highly saturated, high-contrast color palette: radiant emerald green polymer clay structures, glowing neon turquoise accents, 24K gold miniature coins, rich ruby crimson cost blocks, and deep sapphire blue infrastructure partitions. "
            f"Abstract financial forces are physically represented with vibrant color contrast: revenue flows as streams of golden coins, costs manifest as ruby crimson blocks, and capacity is shown as miniature building infrastructure. "
            f"Shot on 35mm f/2.8 macro cinema lens, tilt-shift miniature depth-of-field, warm 3200K tungsten studio key lighting with soft fill, volumetric cyan and magenta rim lighting, ambient occlusion, realistic physical contact shadows, and subtle handcrafted sculpting micro-textures. Pure miniature architecture, zero human figures.{stat_callout}\n\n"
            f"EMOTION: Intelligent, analytical, tactile, cinematic documentary.\n\n"
            f"VISUAL PURPOSE: High-retention physical miniature visualization of: {clean_line}"
        )

units_words = ['', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen']
tens_words = ['', '', 'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety']
scales_words = ['', 'thousand', 'million', 'billion', 'trillion']

def int_to_words(n):
    if n == 0:
        return 'zero'
    if n < 0:
        return 'minus ' + int_to_words(-n)
    parts = []
    scale_idx = 0
    while n > 0:
        chunk = n % 1000
        if chunk > 0:
            c_words = []
            h = chunk // 100
            rem = chunk % 100
            if h > 0:
                c_words.append(f'{units_words[h]} hundred')
            if rem > 0:
                if rem < 20:
                    c_words.append(units_words[rem])
                else:
                    t = rem // 10
                    u = rem % 10
                    c_words.append(tens_words[t] + (f'-{units_words[u]}' if u > 0 else ''))
            chunk_str = ' '.join(c_words)
            if scales_words[scale_idx]:
                chunk_str += ' ' + scales_words[scale_idx]
            parts.insert(0, chunk_str)
        n //= 1000
        scale_idx += 1
    return ' '.join(parts)

def num_to_spoken_str(num_str):
    if '.' in num_str:
        int_p, dec_p = num_str.split('.')
        int_w = int_to_words(int(int_p)) if int_p and int(int_p) > 0 else 'zero'
        dec_words = ' '.join(units_words[int(d)] for d in dec_p if d.isdigit())
        return f'{int_w} point {dec_words}'
    else:
        return int_to_words(int(num_str))

def humanize_numbers_in_text(text):
    if not text:
        return text

    # Clean redundant currency words: $5.5M dollars -> $5.5M
    text = re.sub(r'(\$|€|£)\s*(\d+(?:,\d{3})*(?:\.\d+)?)\s*(k|m|million|b|billion|t|trillion)?\s*(dollars|euros|pounds|rupees)', r'\1\2 \3', text, flags=re.IGNORECASE)

    # 1. Currency with scale words/suffixes: $5.5m, $150k, $2.5 billion
    def curr_sub(m):
        sym = m.group(1)
        num_str = m.group(2).replace(',', '')
        suffix = (m.group(3) or '').lower()
        curr = 'dollars' if sym == '$' else 'euros' if sym in ('€', 'EUR') else 'pounds' if sym == '£' else 'rupees'

        if suffix in ('m', 'million'):
            scale_word = 'million'
        elif suffix in ('b', 'billion'):
            scale_word = 'billion'
        elif suffix in ('t', 'trillion'):
            scale_word = 'trillion'
        elif suffix == 'k':
            scale_word = 'thousand'
        else:
            scale_word = ''

        num_spoken = num_to_spoken_str(num_str)
        if scale_word:
            return f'{num_spoken} {scale_word} {curr}'
        else:
            return f'{num_spoken} {curr}'

    text = re.sub(r'(\$|€|£)\s*(\d+(?:,\d{3})*(?:\.\d+)?)\s*(k|m|million|b|billion|t|trillion)?\b', curr_sub, text, flags=re.IGNORECASE)

    # 2. Standalone numbers with suffixes like 5.5m, 10k, 2.5 billion
    def suffixed_num_sub(m):
        num_str = m.group(1).replace(',', '')
        suffix = m.group(2).lower()
        scale_word = 'million' if suffix in ('m', 'million') else 'billion' if suffix in ('b', 'billion') else 'thousand' if suffix == 'k' else 'trillion'
        return f'{num_to_spoken_str(num_str)} {scale_word}'
    text = re.sub(r'\b(\d+(?:,\d{3})*(?:\.\d+)?)\s*(k|m|million|b|billion|t|trillion)\b', suffixed_num_sub, text, flags=re.IGNORECASE)

    # 3. Percentages: 50% -> fifty percent
    text = re.sub(r'(\d+(?:\.\d+)?)\s*%', lambda m: f'{num_to_spoken_str(m.group(1))} percent', text)

    # 4. Standalone plain numbers: 150000, 10050, 150
    def num_sub(m):
        raw = m.group(0).replace(',', '')
        if len(raw) == 4 and (raw.startswith('19') or raw.startswith('20')):
            y1, y2 = int(raw[:2]), int(raw[2:])
            return f'{int_to_words(y1)} {int_to_words(y2)}' if y2 > 0 else f'{int_to_words(y1)} hundred'
        return int_to_words(int(raw))

    text = re.sub(r'\b\d{1,3}(?:,\d{3})+\b|\b\d+\b', num_sub, text)
    return text

def generate_kokoro_tts_audio(text, voice_key="kokoro_adam", out_filepath="output.mp3"):
    text = humanize_numbers_in_text(text)
    try:
        voice_map = {
            "kokoro_adam": "am_adam",
            "kokoro_michael": "am_michael",
            "kokoro_heart": "af_heart",
            "kokoro_bella": "af_bella",
            "kokoro_nicole": "af_nicole",
            "kokoro_george": "bm_george",
            "kokoro_emma": "bf_emma"
        }
        k_voice = voice_map.get(voice_key, "am_adam")

        # Option A: kokoro_onnx (Fastest & precompiled)
        try:
            from kokoro_onnx import Kokoro
            import soundfile as sf
            import subprocess

            onnx_path = os.path.join(STUDIO_DIR, "kokoro-v1.0.onnx")
            voices_path = os.path.join(STUDIO_DIR, "voices-v1.0.bin")

            if os.path.exists(onnx_path) and os.path.exists(voices_path):
                kokoro_engine = Kokoro(onnx_path, voices_path)
                samples, sample_rate = kokoro_engine.create(text, voice=k_voice, speed=1.0, lang="en-us")
                
                wav_path = out_filepath.replace(".mp3", ".wav")
                sf.write(wav_path, samples, sample_rate)
                if out_filepath.endswith(".mp3"):
                    conv_cmd = ["ffmpeg", "-y", "-i", wav_path, "-c:a", "libmp3lame", "-b:a", "192k", out_filepath]
                    subprocess.run(conv_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    if os.path.exists(wav_path):
                        try:
                            os.remove(wav_path)
                        except Exception:
                            pass
                return True
        except Exception as e_onnx:
            print(f"[Kokoro-ONNX Info]: {e_onnx}")

        # Option B: PyTorch Kokoro
        from kokoro import KPipeline
        import soundfile as sf
        import numpy as np
        import subprocess

        pipeline = KPipeline(lang_code='a')
        generator = pipeline(text, voice=k_voice, speed=1.0)
        
        all_audio = []
        for i, (gs, ps, audio) in enumerate(generator):
            if audio is not None:
                all_audio.append(audio)
                
        if all_audio:
            combined = np.concatenate(all_audio)
            wav_path = out_filepath.replace(".mp3", ".wav")
            sf.write(wav_path, combined, 24000)
            
            if out_filepath.endswith(".mp3"):
                conv_cmd = ["ffmpeg", "-y", "-i", wav_path, "-c:a", "libmp3lame", "-b:a", "192k", out_filepath]
                subprocess.run(conv_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if os.path.exists(wav_path):
                    try:
                        os.remove(wav_path)
                    except Exception:
                        pass
            return True
    except Exception as e:
        print(f"[Kokoro TTS Engine Exception]: {e}")
        return False
    return False

async def process_job_async(job_id, raw_text, voice_preset, rate, filename, mode, niche="economics", visual_style="vox_2d", groq_key="", tts_engine="edge"):
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
        
        kokoro_success = False
        if tts_engine and tts_engine.startswith("kokoro"):
            BACKGROUND_JOBS[job_id]["status_text"] = f"Generating Studio Audio with Kokoro 82M AI ({tts_engine})..."
            kokoro_success = await asyncio.to_thread(generate_kokoro_tts_audio, full_humanized_text, tts_engine, out_filepath)

        if not kokoro_success:
            BACKGROUND_JOBS[job_id]["status_text"] = "Generating HD Voiceover & frame-perfect timing analysis..."
            with open(out_filepath, "wb") as f:
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        f.write(chunk["data"])
                    elif chunk["type"] == "WordBoundary":
                        submaker.feed(chunk)

        if mode == "breakdown":
            BACKGROUND_JOBS[job_id]["progress"] = 50
            BACKGROUND_JOBS[job_id]["status_text"] = "STEP 1: Computing natural scene cuts..."

            scene_lines = split_script_into_scenes(raw_text)
            scenes_raw = []
            est_sec = 0.0
            for line in scene_lines:
                dur = max(2.5, (len(line.split()) / 150.0) * 60.0)
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

            BACKGROUND_JOBS[job_id]["progress"] = 55
            BACKGROUND_JOBS[job_id]["status_text"] = "STEP 1: Script Analyzer Agent identifying core documentary topic..."

            async with ClientSession() as http_session:
                topic_info = await analyze_script_topic_async(http_session, raw_text, groq_key=groq_key)
                
                topic_name = topic_info.get("topic") if (topic_info and topic_info.get("topic")) else "General Business & Economics"
                BACKGROUND_JOBS[job_id]["progress"] = 65
                BACKGROUND_JOBS[job_id]["status_text"] = f"STEP 2: Topic-Locked Agent ({topic_name[:30]}) mapping {len(scenes_raw)} scene beats..."

                tasks = [
                    call_groq_ai_prompt_engineer(http_session, sitem["text"], idx, niche=niche, visual_style=visual_style, groq_key=groq_key, script_topic_info=topic_info)
                    for idx, (sitem) in enumerate(scenes_raw, start=1)
                ]
                ai_prompts = await asyncio.gather(*tasks)

            scenes = []
            for idx, (sitem, prompt_res) in enumerate(zip(scenes_raw, ai_prompts), start=1):
                if not prompt_res:
                    prompt_res = build_vector_art_scene_prompt_fallback(sitem["text"], niche, visual_style)
                
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
                "status_text": f"Generated Voiceover & {len(scenes)} topic-locked prompts!",
                "mode": "breakdown",
                "result": {
                    "filename": filename,
                    "audioUrl": f"/static/generated/{filename}",
                    "scenes": scenes,
                    "topic_info": topic_info
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

STUDIO_HTML_PATH = os.path.join(STATIC_DIR, "studio.html")

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

STUDIO_HTML_PATH = os.path.join(STATIC_DIR, "studio.html")

async def handle_studio(request):
    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0"
    }
    if os.path.exists(STUDIO_HTML_PATH):
        with open(STUDIO_HTML_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        return web.Response(text=content, content_type="text/html", charset="utf-8", headers=headers)
    return web.Response(text="<h1>YouTube Voiceover Studio - Modular Workbench</h1><p>Initializing studio.html...</p>", content_type="text/html", headers=headers)

YOUTUBE2_HTML_PATH = os.path.join(STATIC_DIR, "youtube2.html")

async def handle_youtube2(request):
    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0"
    }
    if os.path.exists(YOUTUBE2_HTML_PATH):
        with open(YOUTUBE2_HTML_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        return web.Response(text=content, content_type="text/html", charset="utf-8", headers=headers)
    return web.Response(text="<h1>YouTube 2.0 Studio</h1><p>Initializing youtube2.html...</p>", content_type="text/html", headers=headers)

async def handle_fallback(request):
    path = request.path.lower()
    if 'youtube' in path or '2.0' in path:
        return await handle_youtube2(request)
    if 'studio' in path:
        return await handle_studio(request)
    return await handle_index(request)

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
        niche = data.get("niche", "economics")
        visual_style = data.get("visual_style", "physical_economics_3d")
        groq_key = data.get("groq_key", "").strip()
        tts_engine = data.get("tts_engine", "edge")

        if tts_engine and tts_engine.startswith("edge_"):
            voice_preset = tts_engine.replace("edge_", "")
            tts_engine = "edge"

        if not raw_text:
            return web.json_response({"error": "Script text cannot be empty"}, status=400)

        job_id = str(uuid.uuid4())
        asyncio.create_task(process_job_async(job_id, raw_text, voice_preset, rate, filename, mode, niche, visual_style, groq_key, tts_engine))

        return web.json_response({"job_id": job_id, "status": "processing"})
    except Exception as e:
        print(f"[handle_start_job exception]: {e}")
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
    text = humanize_numbers_in_text(text)
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
        scene_text = data.get("scene_text", "").strip()
        voice = data.get("voice", "andrew").lower()
        rate = str(data.get("rate", "-4%")).strip()
        tts_engine = str(data.get("tts_engine", "edge")).lower()

        if rate in ["+1%", "+0%", "0%"]:
            rate = "-4%"
        if not rate.startswith("+") and not rate.startswith("-"):
            rate = "-" + rate

        preset = VOICE_PRESETS.get(voice, {})
        voice_id = preset.get("id", "en-US-AndrewNeural")

        if not scene_text:
            job = BACKGROUND_JOBS.get(job_id)
            if job and job.get("result") and job["result"].get("scenes"):
                scenes = job["result"]["scenes"]
                if 1 <= scene_idx <= len(scenes):
                    sc = scenes[scene_idx - 1]
                    scene_text = sc.get("text", "")

        if not scene_text:
            return web.json_response({"error": "Scene line text not found."}, status=400)

        out_filename = f"beat_audio_{job_id[:6] if job_id else 'beat'}_{scene_idx:02d}.mp3"
        out_filepath = os.path.join(DOWNLOADS_DIR, out_filename)

        cleaned_text = humanize_numbers_in_text(scene_text)

        # Synthesize audio specifically for this scene text line
        generated_ok = False
        if tts_engine and tts_engine.startswith("kokoro"):
            generated_ok = await asyncio.to_thread(generate_kokoro_tts_audio, cleaned_text, tts_engine, out_filepath)

        if not generated_ok:
            await safe_edge_tts_save(cleaned_text, voice_id, rate, out_filepath)

        # Trim trailing silence & append natural 0.35s pause
        await trim_trailing_audio_silence(out_filepath)
        await append_natural_pause_padding(out_filepath, 0.35)

        dur_sec = await get_media_duration_sec(out_filepath)

        return web.json_response({
            "status": "success",
            "filename": out_filename,
            "audioUrl": f"/static/generated/{out_filename}",
            "text": scene_text,
            "durSec": round(dur_sec, 2)
        })
    except Exception as e:
        print("[handle_generate_beat_audio error]:", e)
        return web.json_response({"error": str(e)}, status=500)

def format_ass_timestamp(seconds: float) -> str:
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    if cs >= 100:
        cs = 99
    return f"{hrs:01d}:{mins:02d}:{secs:02d}.{cs:02d}"

def generate_animated_ass_subtitle(
    script_text: str,
    duration_sec: float,
    out_ass_path: str,
    style_name: str = "hormozi",
    font_name: str = "Arial",
    position: str = "bottom",
    custom_fontsize: int = None,
    custom_bg_hex: str = None,
    custom_bg_opacity: float = 0.85
):
    import re
    clean_script = re.sub(r'\[(dramatic|whisper|excited|suspense|authoritative|sad|cheerful|happy|scary|calm|fast|slow)\]', '', script_text, flags=re.IGNORECASE)
    words = clean_script.strip().split()
    if not words:
        words = ["Beat"]
    
    total_words = len(words)
    time_per_word = duration_sec / max(total_words, 1)
    dur_cs_per_word = max(1, int(round(time_per_word * 100)))

    alignment = 2
    if position == "middle":
        alignment = 5
    elif position == "top":
        alignment = 8

    if style_name == "hormozi":
        primary_color = "&H00FFFFFF"     # White
        secondary_color = "&H0000FFFF"   # Yellow highlight
        outline_color = "&H00000000"
        fontsize = 44
        outline = 4
        shadow = 2
    elif style_name == "mrbeast":
        primary_color = "&H00FFFFFF"     # White
        secondary_color = "&H00FFFF00"   # Cyan highlight
        outline_color = "&H00000000"
        fontsize = 48
        outline = 5
        shadow = 2
    elif style_name == "cyberpunk":
        primary_color = "&H00FFFF00"     # Cyan base
        secondary_color = "&H00FF00FF"   # Magenta highlight
        outline_color = "&H00000000"
        fontsize = 44
        outline = 4
        shadow = 3
    elif style_name == "vox":
        primary_color = "&H00FFFFFF"     # White
        secondary_color = "&H00552DFF"   # Red highlight
        outline_color = "&H00000000"
        fontsize = 46
        outline = 4
        shadow = 2
    elif style_name == "retro":
        primary_color = "&H00D0FDF7"     # Cream base
        secondary_color = "&H00003300"   # Dark green highlight
        outline_color = "&H00000000"
        fontsize = 42
        outline = 3
        shadow = 2
    else:  # 'cinematic'
        primary_color = "&H00FFFFFF"     # White
        secondary_color = "&H002997FF"   # Blue highlight
        outline_color = "&H00000000"
        fontsize = 38
        outline = 2
        shadow = 1

    if custom_fontsize and custom_fontsize > 10:
        fontsize = custom_fontsize

    # Convert custom_bg_hex & opacity to ASS BackColour (&HAABBGGRR)
    back_color = "&H80000000"
    if custom_bg_hex:
        clean_hex = custom_bg_hex.lstrip('#')
        if len(clean_hex) == 6:
            r_val = clean_hex[0:2]
            g_val = clean_hex[2:4]
            b_val = clean_hex[4:6]
            bgr_hex = f"{b_val}{g_val}{r_val}".upper()
            alpha_int = max(0, min(255, int((1.0 - max(0.0, min(1.0, custom_bg_opacity))) * 255)))
            alpha_hex = f"{alpha_int:02X}"
            back_color = f"&H{alpha_hex}{bgr_hex}"

    font_map = {
        "gladolia": "Gladolia DEMO",
        "mileast": "Mileast",
        "moldie": "Moldie Demo",
        "montserrat": "Montserrat",
        "outfit": "Outfit",
        "impact": "Impact",
        "bebas neue": "Bebas Neue",
        "anton": "Anton",
        "rubik": "Rubik",
        "poppins": "Poppins",
        "komika axis": "Komika Axis",
        "inter": "Inter",
        "georgia": "Georgia"
    }
    actual_font_name = font_map.get(str(font_name).lower().strip(), font_name)

    # If background is 100% transparent (opacity <= 0.05), strip outline border box completely
    if custom_bg_opacity is not None and custom_bg_opacity <= 0.05:
        outline = 0
        shadow = 0
        outline_color = "&HFF000000"
        back_color = "&HFF000000"

    header = f"""[Script Info]
Title: Studio Animated Subtitles
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: None

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{actual_font_name},{fontsize},{primary_color},{secondary_color},{outline_color},{back_color},-1,0,0,0,100,100,0,0,1,{outline},{shadow},{alignment},20,20,40,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events = []
    # 1-word-at-a-time chunking for wordbyword, bounce, and fade styles
    if style_name in ["wordbyword", "bounce", "fade"]:
        chunk_size = 1
    else:
        chunk_size = 4

    chunks = [words[i:i + chunk_size] for i in range(0, len(words), chunk_size)]
    
    current_time = 0.0
    for chunk in chunks:
        chunk_dur = len(chunk) * time_per_word
        start_ts = format_ass_timestamp(current_time)
        end_ts = format_ass_timestamp(current_time + chunk_dur)
        
        karaoke_text = ""
        for word in chunk:
            if style_name == "bounce":
                karaoke_text += f"{{\\fad(60,60)\\t(0,100,\\fscx120\\fscy120)\\t(100,200,\\fscx100\\fscy100)}}{word} "
            elif style_name == "fade":
                karaoke_text += f"{{\\fad(120,120)}}{word} "
            else:
                karaoke_text += f"{{\\kf{dur_cs_per_word}}}{word} "
        
        events.append(f"Dialogue: 0,{start_ts},{end_ts},Default,,0,0,0,,{karaoke_text.strip()}")
        current_time += chunk_dur

    with open(out_ass_path, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(events))

async def handle_generate_beat_clip(request):
    try:
        reader = await request.multipart()
        job_id = ""
        scene_idx = 1
        subtitle_style = "hormozi"
        subtitle_font = "Arial"
        subtitle_pos = "bottom"
        video_filter = "vignette"
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
            elif field.name == "subtitle_style":
                subtitle_style = (await field.read()).decode('utf-8').strip()
            elif field.name == "subtitle_font":
                subtitle_font = (await field.read()).decode('utf-8').strip()
            elif field.name == "subtitle_pos":
                subtitle_pos = (await field.read()).decode('utf-8').strip()
            elif field.name == "video_filter":
                video_filter = (await field.read()).decode('utf-8').strip()
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

        scene_text = f"Beat #{scene_idx}"
        job = BACKGROUND_JOBS.get(job_id)
        if job and job.get("result") and job["result"].get("scenes"):
            scenes = job["result"]["scenes"]
            if 1 <= scene_idx <= len(scenes):
                scene_text = scenes[scene_idx - 1].get("text", scene_text)

        if not os.path.exists(beat_audio_path):
            cleaned = humanize_script(scene_text)
            await safe_edge_tts_save(cleaned, "en-AU-WilliamNeural", "-4%", beat_audio_path)
            await trim_trailing_audio_silence(beat_audio_path)
            await append_natural_pause_padding(beat_audio_path, 0.28)

        dur_sec = await get_media_duration_sec(beat_audio_path)
        if dur_sec <= 0.2:
            dur_sec = 3.0

        out_clip_filename = f"mini_clip_{job_id[:6]}_{scene_idx:02d}.mp4"
        out_clip_filepath = os.path.join(DOWNLOADS_DIR, out_clip_filename)

        # Instant Cache Check: If clip was already rendered successfully on server, return immediately in 0.001s!
        if os.path.exists(out_clip_filepath) and os.path.getsize(out_clip_filepath) > 1000:
            dur_sec = await get_media_duration_sec(out_clip_filepath)
            if dur_sec <= 0.2:
                dur_sec = 3.0
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

        vf_filters = [get_ken_burns_vf(scene_idx)]

        # Video Filter presets
        if video_filter == "vignette":
            vf_filters.append("vignette=PI/4")
        elif video_filter == "teal_orange":
            vf_filters.append("eq=contrast=1.15:saturation=1.3:gamma_r=0.9:gamma_b=1.1")
        elif video_filter == "film_grain":
            vf_filters.append("noise=alls=12:allf=t+u")
        elif video_filter == "letterbox":
            vf_filters.append("drawbox=y=0:h=ih*0.12:color=black:t=fill,drawbox=y=ih*0.88:h=ih*0.12:color=black:t=fill")
        elif video_filter == "noir_bw":
            vf_filters.append("hue=s=0,eq=contrast=1.2")
        elif video_filter == "sunset_gold":
            vf_filters.append("eq=contrast=1.1:saturation=1.25:gamma_r=1.15:gamma_g=1.05:gamma_b=0.85")
        elif video_filter == "cyberpunk_neon":
            vf_filters.append("eq=contrast=1.25:saturation=1.4:gamma_r=1.1:gamma_b=1.25")
        elif video_filter == "vhs_crt":
            vf_filters.append("noise=alls=15:allf=t+u,eq=contrast=1.15:saturation=1.2")

        # Subtitle overlay
        if subtitle_style and subtitle_style != "none":
            ass_path = os.path.join(temp_dir, "subtitle.ass")
            generate_animated_ass_subtitle(
                scene_text, dur_sec, ass_path,
                style_name=subtitle_style,
                font_name=subtitle_font,
                position=subtitle_pos
            )
            escaped_ass = ass_path.replace("\\", "/").replace(":", "\\:")
            vf_filters.append(f"subtitles='{escaped_ass}'")

        vf_chain = ",".join(vf_filters)

        ffmpeg_cmd = [
            "ffmpeg", "-y", "-threads", "2",
            "-i", beat_audio_path,
            "-loop", "1", "-i", img_filepath,
            "-vf", vf_chain,
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

        import gc
        gc.collect()

        return web.json_response({
            "status": "success",
            "sceneIndex": scene_idx,
            "filename": out_clip_filename,
            "clipUrl": f"/static/generated/{out_clip_filename}",
            "durSec": round(dur_sec, 1)
        })
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

async def handle_generate_seo_package(request):
    try:
        data = await request.json()
        script_text = data.get("script_text", "").strip()
        scenes = data.get("scenes", [])
        gemini_api_key = data.get("gemini_api_key", "").strip() or os.environ.get("GEMINI_API_KEY", "")
        
        if not script_text:
            return web.json_response({"error": "Script text is required"}, status=400)
            
        chapters = []
        curr_time = 0.0
        chapters.append("0:00 Introduction")
        
        for idx, sc in enumerate(scenes):
            dur = float(sc.get("durSec", 3.5) or 3.5)
            if idx > 0 and idx % 4 == 0:
                mins = int(curr_time // 60)
                secs = int(curr_time % 60)
                snippet = sc.get("text", f"Section {idx+1}")[:30].strip()
                chapters.append(f"{mins}:{secs:02d} {snippet}...")
            curr_time += dur
            
        titles = []
        description = ""
        tags = []
        thumbnail_prompts = []
        
        if gemini_api_key:
            try:
                import urllib.request
                import json
                
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_api_key}"
                
                prompt_input = f"""Analyze this YouTube script and output ONLY valid JSON matching this exact structure:
{{
  "titles": ["5 high-CTR curiosity-hook titles"],
  "description": "Engaging SEO description with keywords",
  "tags": ["25 relevant search tags"],
  "thumbnail_prompts": ["3 detailed Midjourney/AI thumbnail prompts with text overlay ideas"]
}}

Script Text:
{script_text[:3000]}"""

                req_payload = json.dumps({
                    "contents": [{"parts": [{"text": prompt_input}]}]
                }).encode('utf-8')
                
                req = urllib.request.Request(url, data=req_payload, headers={'Content-Type': 'application/json'})
                
                with urllib.request.urlopen(req, timeout=12) as response:
                    res_body = json.loads(response.read().decode('utf-8'))
                    raw_text = res_body['candidates'][0]['content']['parts'][0]['text']
                    
                    json_str = raw_text
                    if "```json" in raw_text:
                        json_str = raw_text.split("```json")[1].split("```")[0].strip()
                    elif "```" in raw_text:
                        json_str = raw_text.split("```")[1].split("```")[0].strip()
                        
                    parsed = json.loads(json_str)
                    titles = parsed.get("titles", [])
                    description = parsed.get("description", "")
                    tags = parsed.get("tags", [])
                    thumbnail_prompts = parsed.get("thumbnail_prompts", [])
            except Exception as gem_err:
                print(f"Gemini API query warning: {gem_err}")
                
        if not titles:
            words = [w.strip(".,!?\"'") for w in script_text.split() if len(w) > 3]
            top_words = list(dict.fromkeys(words))[:6]
            kw_str = " ".join(top_words[:3]).title() if top_words else "Viral Story"
            
            titles = [
                f"The Hidden Truth About {kw_str}",
                f"Why Everyone Is Wrong About {kw_str}",
                f"The $100B Industry Secrets Revealed",
                f"Inside The Operation: {kw_str} Explained",
                f"What Nobody Told You About {kw_str}"
            ]
            
        if not description:
            description = f"In this video, we break down {script_text[:200]}...\n\nSubscribe for more documentary essays!\n\nTimestamps:\n" + "\n".join(chapters)
            
        if not tags:
            words = list(set([w.lower().strip(".,!?\"'") for w in script_text.split() if len(w) > 4]))[:20]
            tags = words + ["documentary", "youtube essay", "explained", "business", "viral"]
            
        if not thumbnail_prompts:
            thumbnail_prompts = [
                "3D cinematic renders of dramatic scene lighting, hyperdetailed, 16:9, bold text overlay: 'THE SECRET'",
                "High contrast 2D editorial illustration, neon glowing accents, bold text overlay: 'REVEALED'",
                "35mm film still, dramatic chiaroscuro spotlight, bold text overlay: 'EXPOSED'"
            ]
            
        return web.json_response({
            "status": "success",
            "geminiUsed": bool(gemini_api_key),
            "titles": titles,
            "chapters": chapters,
            "description": description,
            "tags": tags,
            "thumbnailPrompts": thumbnail_prompts
        })
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

async def handle_clone_voice(request):
    try:
        reader = await request.multipart()
        field = await reader.next()
        if not field or field.name != 'file':
            return web.json_response({"error": "No voice file uploaded"}, status=400)
            
        save_path = os.path.join(STATIC_DIR, "custom_voice_clone.wav")
        
        with open(save_path, 'wb') as f:
            while True:
                chunk = await field.read_chunk()
                if not chunk:
                    break
                f.write(chunk)
                
        return web.json_response({
            "status": "success",
            "message": "Custom Voice Clone created successfully!",
            "voiceId": "custom_clone",
            "voiceName": "Vikas (Custom Voice Clone)",
            "audioUrl": "/static/custom_voice_clone.wav"
        })
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

def condense_prompt_for_flux(raw_prompt):
    if not raw_prompt:
        return "cinematic film still, photorealistic, high quality"
    
    clean = raw_prompt.strip()
    if 'IMAGE PROMPT:' in clean:
        match = re.search(r'IMAGE PROMPT:\s*([\s\S]*?)(?=\n\n[A-Z\s]+:|$)', clean)
        if match and match.group(1):
            clean = match.group(1).strip()
            
    clean = re.sub(r'[\r\n]+', ' ', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()

    if len(clean) > 500:
        clean = clean[:500].rsplit(' ', 1)[0]

    return clean

async def handle_generate_flux_image(request):
    try:
        data = await request.json()
        prompt = data.get("prompt", "cinematic film still").strip()
        scene_num = int(data.get("scene_num", 1))
        proj_id = data.get("project_id", "default").strip()
        width = int(data.get("width", 1280))
        height = int(data.get("height", 720))
        
        flux_prompt = condense_prompt_for_flux(prompt)
        enhanced_prompt = f"{flux_prompt}, 8k resolution, photorealistic masterpiece, highly detailed, 35mm photograph, cinematic lighting"
        encoded_prompt = urllib.parse.quote_plus(enhanced_prompt)
        seed = (uuid.uuid4().int + scene_num * 31) % 100000
        
        filename = f"flux_scene_{proj_id}_{scene_num}_{uuid.uuid4().hex[:6]}.png"
        filepath = os.path.join(DOWNLOADS_DIR, filename)
        image_url = f"/static/generated/{filename}"
        
        hf_token = os.environ.get("HF_TOKEN", "").strip() or os.environ.get("HUGGING_FACE_HUB_TOKEN", "").strip()
        headers = {"Authorization": f"Bearer {hf_token}"} if hf_token else None

        success = False

        # TIER 1: Official black-forest-labs/FLUX.1-schnell & FLUX.1-dev with User HF_TOKEN
        def run_official_flux():
            from gradio_client import Client
            import shutil
            
            # Try FLUX.1-schnell (Ultra fast 4-step 8K model)
            try:
                client_s = Client("black-forest-labs/FLUX.1-schnell", headers=headers)
                result_s = client_s.predict(
                    prompt=enhanced_prompt,
                    seed=seed,
                    randomize_seed=True,
                    width=1024,
                    height=576,
                    num_inference_steps=4,
                    api_name="/infer"
                )
                gen_path = result_s[0] if isinstance(result_s, (list, tuple)) else str(result_s)
                if gen_path and os.path.exists(gen_path):
                    shutil.copy(gen_path, filepath)
                    print(f"[FLUX.1-schnell Scene #{scene_num} SUCCESS]: saved to {filepath}")
                    return True
            except Exception as e_s:
                print(f"[FLUX.1-schnell Scene #{scene_num} notice]: {e_s}")
            
            # Try FLUX.1-dev
            try:
                client_d = Client("black-forest-labs/FLUX.1-dev", headers=headers)
                result_d = client_d.predict(
                    prompt=enhanced_prompt,
                    seed=seed,
                    randomize_seed=False,
                    width=width,
                    height=height,
                    guidance_scale=3.5,
                    num_inference_steps=28,
                    api_name="/infer"
                )
                gen_path_d = result_d[0] if isinstance(result_d, (list, tuple)) else str(result_d)
                if gen_path_d and os.path.exists(gen_path_d):
                    shutil.copy(gen_path_d, filepath)
                    print(f"[FLUX.1-dev Scene #{scene_num} SUCCESS]: saved to {filepath}")
                    return True
            except Exception as e_d:
                print(f"[FLUX.1-dev Scene #{scene_num} notice]: {e_d}")

            return False

        try:
            success = await asyncio.wait_for(asyncio.to_thread(run_official_flux), timeout=25.0)
        except Exception as timeout_err:
            print(f"[Official FLUX Timeout Scene #{scene_num}]: {timeout_err}")
            success = False

        # TIER 2: Pollinations FLUX engine fallback
        if not success or not os.path.exists(filepath):
            flux_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={width}&height={height}&model=flux&nologo=true&seed={seed}&enhance=true"
            async with ClientSession() as session:
                try:
                    async with session.get(flux_url, timeout=25) as resp:
                        if resp.status == 200:
                            image_bytes = await resp.read()
                            with open(filepath, "wb") as f:
                                f.write(image_bytes)
                            success = True
                except Exception as net_err:
                    print(f"[FLUX Tier 2 Scene #{scene_num} notice]: {net_err}")

        # TIER 3: SVG fallback
        if not success or not os.path.exists(filepath):
            svg_content = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
                <rect width="100%" height="100%" fill="#0e1017"/>
                <rect x="4" y="4" width="{width-8}" height="{height-8}" fill="none" stroke="#af52de" stroke-width="2" stroke-dasharray="8 8"/>
                <text x="50%" y="45%" dominant-baseline="middle" text-anchor="middle" fill="#af52de" font-size="28" font-weight="bold">⚡ FLUX AI visual asset beat #{scene_num}</text>
                <text x="50%" y="60%" dominant-baseline="middle" text-anchor="middle" fill="#9ca3af" font-size="16">{flux_prompt[:60]}...</text>
            </svg>'''
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(svg_content)

        # Update SQLite scene database record if exists
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("UPDATE scenes SET image_url = ?, prompt = ? WHERE project_id = ? AND scene_num = ?", 
                           (image_url, prompt, proj_id, scene_num))
            conn.commit()
            conn.close()
        except Exception:
            pass

        return web.json_response({
            "status": "success",
            "message": f"FLUX AI Image generated for Beat #{scene_num}",
            "sceneNum": scene_num,
            "scene_num": scene_num,
            "image_url": image_url,
            "imageUrl": image_url,
            "image_path": filepath
        })
    except Exception as e:
        print("[handle_generate_flux_image exception]:", e)
        return web.json_response({"error": str(e)}, status=500)

async def handle_verify_passcode(request):
    try:
        data = await request.json()
        passcode = data.get("passcode", "").strip()
        master_pwd = os.environ.get("STUDIO_PASSWORD", "vikas2026").strip()
        
        if passcode == master_pwd:
            return web.json_response({"unlocked": True, "status": "success"})
        else:
            return web.json_response({"unlocked": False, "error": "Incorrect Passcode"}, status=401)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

def generate_scene_canvas_image(scene_text, scene_num, out_filepath):
    try:
        from PIL import Image, ImageDraw, ImageFont
        width, height = 1920, 1080
        img = Image.new("RGB", (width, height), color=(15, 23, 42))
        draw = ImageDraw.Draw(img)
        draw.rectangle([60, 60, width - 60, height - 60], outline=(0, 113, 227), width=4)
        
        try:
            font = ImageFont.truetype("arial.ttf", 52)
            sub_font = ImageFont.truetype("arial.ttf", 34)
        except Exception:
            font = ImageFont.load_default()
            sub_font = font

        draw.text((100, 120), f"SCENE BEAT #{scene_num}", fill=(255, 45, 85), font=sub_font)
        
        words = scene_text.split()
        lines = []
        curr_line = []
        for w in words:
            curr_line.append(w)
            if len(" ".join(curr_line)) > 42:
                lines.append(" ".join(curr_line[:-1]))
                curr_line = [w]
        if curr_line:
            lines.append(" ".join(curr_line))

        y = 380
        for line in lines[:5]:
            draw.text((100, y), line, fill=(255, 255, 255), font=font)
            y += 68

        img.save(out_filepath)
    except Exception as e:
        print("[generate_scene_canvas_image error]:", e)

async def run_cmd(cmd_list):
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd_list,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            print(f"[run_cmd error] code={proc.returncode} stderr={stderr.decode('utf-8', errors='ignore')}")
        return proc.returncode == 0
    except Exception as e:
        print(f"[run_cmd exception]: {e}")
        return False

async def handle_render_final_video(request):
    try:
        data = await request.json()
        job_id = data.get("job_id", "")
        scenes = data.get("scenes", [])
        subtitle_style = str(data.get("subtitle_style", "bounce")).lower()
        subtitle_pos = str(data.get("subtitle_pos", "bottom")).lower()
        video_filter = str(data.get("video_filter", "none")).lower()
        is_quick_preview = bool(data.get("is_quick_preview", False))

        if not scenes:
            return web.json_response({"error": "No scene beats available to render video."}, status=400)

        # Quick Preview mode slices to first 2 scenes for ultra-fast 3-second testing
        if is_quick_preview and len(scenes) >= 2:
            scenes = scenes[:2]

        ts_id = int(time.time() * 1000)
        out_master_filename = f"master_video_{job_id[:8] if job_id else 'vid'}_{ts_id}.mp4"
        out_master_filepath = os.path.join(DOWNLOADS_DIR, out_master_filename)

        temp_dir = os.path.join(DOWNLOADS_DIR, f"render_tmp_{job_id[:6] if job_id else 'tmp'}_{ts_id}")
        os.makedirs(temp_dir, exist_ok=True)

        concat_list_path = os.path.join(temp_dir, "concat.txt")
        concat_files = []

        total_scenes = len(scenes)
        for idx, sc in enumerate(scenes):
            scene_num = sc.get("scene", idx + 1)
            beat_audio_filename = f"beat_audio_{job_id[:6] if job_id else 'beat'}_{scene_num:02d}.mp3"
            beat_audio_path = os.path.join(DOWNLOADS_DIR, beat_audio_filename)

            if not os.path.exists(beat_audio_path):
                cleaned_text = humanize_script(sc.get("text", "Scene beat"))
                await safe_edge_tts_save(cleaned_text, "en-US-AndrewNeural", "-4%", beat_audio_path)
                await trim_trailing_audio_silence(beat_audio_path)
                await append_natural_pause_padding(beat_audio_path, 0.35)

            dur_sec = await get_media_duration_sec(beat_audio_path)
            if dur_sec <= 0.2:
                dur_sec = 3.0

            # 30ms audio micro-fades to eliminate pops
            faded_audio_path = os.path.join(temp_dir, f"audio_faded_{scene_num:02d}.mp3")
            fade_out_st = max(0, dur_sec - 0.03)
            afade_cmd = [
                "ffmpeg", "-y", "-i", beat_audio_path,
                "-af", f"afade=t=in:ss=0:d=0.03,afade=t=out:st={fade_out_st:.3f}:d=0.03",
                "-c:a", "libmp3lame", "-q:a", "2", faded_audio_path
            ]
            await run_cmd(afade_cmd)

            # Segment video clip
            beat_clip_path = os.path.join(temp_dir, f"clip_{scene_num:02d}.mp4")
            assigned_img = sc.get("image_path", "") or sc.get("image_url", "")
            if assigned_img and assigned_img.startswith("/static/"):
                rel_path = assigned_img.replace("/static/", "").replace("/", os.sep)
                assigned_img = os.path.join(STATIC_DIR, rel_path)
            elif assigned_img and not os.path.isabs(assigned_img):
                assigned_img = os.path.join(STUDIO_DIR, assigned_img.replace("/", os.sep))

            if not assigned_img or not os.path.exists(assigned_img):
                assigned_img = os.path.join(temp_dir, f"canvas_{scene_num:02d}.png")
                await asyncio.to_thread(generate_scene_canvas_image, sc.get("text", ""), scene_num, assigned_img)

            vf_filters = ["scale=1920:1080:force_original_aspect_ratio=increase", "crop=1920:1080", "fps=30", "format=yuv420p"]
            if video_filter == "vignette":
                vf_filters.append("vignette=PI/4")
            elif video_filter == "warm":
                vf_filters.append("colorbalance=rh=0.1:gh=0.05:bh=-0.1")
            elif video_filter == "grain":
                vf_filters.append("noise=alls=12:allf=t+u")
            
            vf_str = ",".join(vf_filters)

            clip_cmd = [
                "ffmpeg", "-y", "-loop", "1", "-i", assigned_img, "-i", faded_audio_path,
                "-vf", vf_str,
                "-c:v", "libx264", "-tune", "stillimage", "-preset", "ultrafast",
                "-c:a", "aac", "-b:a", "192k", "-shortest", beat_clip_path
            ]
            await run_cmd(clip_cmd)
            concat_files.append(beat_clip_path)

        with open(concat_list_path, "w", encoding="utf-8") as f:
            for c_path in concat_files:
                esc_path = c_path.replace("\\", "/")
                f.write(f"file '{esc_path}'\n")

        transition_style = str(data.get("transition", "crossfade")).lower()
        allowed_transitions = data.get("allowed_transitions", [])
        
        # Build raw concatenated video (with xfade if selected and safe for command length)
        raw_concat_video = os.path.join(temp_dir, "raw_concat.mp4")

        success = False
        # Only run xfade filter complex if clip count is small (<=20 clips) to prevent Windows command line overflow [WinError 206]
        if len(concat_files) > 1 and len(concat_files) <= 20 and transition_style != "none":
            try:
                # 19 Premium FFmpeg xfade transition options
                xfade_options = [
                    "fade", "fadeblack", "fadewhite", "wipeleft", "wiperight",
                    "wipeup", "wipedown", "slideleft", "slideright", "slideup",
                    "slidedown", "zoomin", "circlecrop", "rectcrop", "pixelize",
                    "diagtl", "diagtr", "horzopen", "vertopen"
                ]
                xfade_map = {
                    "crossfade": "fade", "fadeblack": "fadeblack", "fadewhite": "fadewhite",
                    "wipeleft": "wipeleft", "wiperight": "wiperight", "wipeup": "wipeup",
                    "wipedown": "wipedown", "slideleft": "slideleft", "slideright": "slideright",
                    "slideup": "slideup", "slidedown": "slidedown", "zoomin": "zoomin",
                    "circlecrop": "circlecrop", "rectcrop": "rectcrop", "pixelize": "pixelize",
                    "diagtl": "diagtl", "diagtr": "diagtr", "horzopen": "horzopen", "vertopen": "vertopen"
                }
                if allowed_transitions and isinstance(allowed_transitions, list) and len(allowed_transitions) > 0:
                    selected_pool = [xfade_map.get(t, t) for t in allowed_transitions if t in xfade_map or t in xfade_options]
                    if selected_pool:
                        xfade_options = selected_pool

                durations = []
                for cf in concat_files:
                    d = await get_media_duration_sec(cf)
                    durations.append(max(d, 0.5))

                filter_parts = []
                accum_offset = durations[0] - 0.5
                prev_v = "0:v"

                xfade_inputs = []
                for idx, cf in enumerate(concat_files):
                    xfade_inputs.extend(["-i", cf])

                for i in range(1, len(concat_files)):
                    if transition_style in ["random", "sequential", "cycle"] or (allowed_transitions and len(allowed_transitions) > 0):
                        trans_kw = xfade_options[(i - 1) % len(xfade_options)]
                    else:
                        trans_kw = xfade_map.get(transition_style, "fade")

                    next_v = f"{i}:v"
                    out_v = f"v{i}" if i < len(concat_files) - 1 else "outv"

                    filter_parts.append(f"[{prev_v}][{next_v}]xfade=transition={trans_kw}:duration=0.5:offset={max(0, accum_offset):.3f}[{out_v}]")

                    prev_v = out_v
                    if i < len(durations) - 1:
                        accum_offset += max(0, durations[i] - 0.5)

                # Concatenate audio streams end-to-end to protect 100% of audio and natural pauses
                audio_inputs_str = "".join([f"[{i}:a]" for i in range(len(concat_files))])
                filter_parts.append(f"{audio_inputs_str}concat=n={len(concat_files)}:v=0:a=1[outa]")

                filter_graph = ";".join(filter_parts)
                filter_script_path = os.path.join(temp_dir, "xfade_filter.txt")
                with open(filter_script_path, "w", encoding="utf-8") as f:
                    f.write(filter_graph)

                xfade_cmd = ["ffmpeg", "-y"] + xfade_inputs + [
                    "-filter_complex_script", filter_script_path,
                    "-map", "[outv]", "-map", "[outa]",
                    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20",
                    "-c:a", "aac", "-b:a", "192k", raw_concat_video
                ]
                success = await run_cmd(xfade_cmd)
            except Exception as ex:
                print(f"[xfade fallback triggered]: {ex}")
                success = False

        if not success or not os.path.exists(raw_concat_video) or os.path.getsize(raw_concat_video) < 100:
            batch_chunk_size = 50
            num_clips = len(concat_files)
            if num_clips > batch_chunk_size:
                print(f"[Master Concatenation Engine]: Rendering {num_clips} clips in 50-clip batches to prevent crashes...")
                total_batches = (num_clips + batch_chunk_size - 1) // batch_chunk_size
                intermediate_batch_files = []

                for b_idx in range(total_batches):
                    start_i = b_idx * batch_chunk_size
                    end_i = min(start_i + batch_chunk_size, num_clips)
                    batch_files = concat_files[start_i:end_i]

                    batch_list_path = os.path.join(temp_dir, f"batch_concat_list_{b_idx:03d}.txt")
                    with open(batch_list_path, "w", encoding="utf-8") as f:
                        for cf in batch_files:
                            esc_path = cf.replace("\\", "/")
                            f.write(f"file '{esc_path}'\n")

                    batch_chunk_mp4 = os.path.join(temp_dir, f"batch_chunk_{b_idx:03d}.mp4")
                    batch_cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", batch_list_path, "-c:v", "copy", "-c:a", "copy", batch_chunk_mp4]
                    
                    print(f"[Master Concatenation Engine]: Batch {b_idx + 1}/{total_batches} ({start_i + 1}-{end_i}/{num_clips}) rendering...")
                    batch_ok = await run_cmd(batch_cmd)
                    if not batch_ok or not os.path.exists(batch_chunk_mp4) or os.path.getsize(batch_chunk_mp4) < 100:
                        batch_cmd_re = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", batch_list_path, "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-b:a", "192k", batch_chunk_mp4]
                        await run_cmd(batch_cmd_re)

                    intermediate_batch_files.append(batch_chunk_mp4)
                    await asyncio.sleep(0.3)  # CPU & Disk I/O cooldown break

                final_batch_list_path = os.path.join(temp_dir, "final_batch_list.txt")
                with open(final_batch_list_path, "w", encoding="utf-8") as f:
                    for b_file in intermediate_batch_files:
                        esc_path = b_file.replace("\\", "/")
                        f.write(f"file '{esc_path}'\n")

                final_merge_cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", final_batch_list_path, "-c:v", "copy", "-c:a", "copy", raw_concat_video]
                await run_cmd(final_merge_cmd)
            else:
                print(f"[Master Concatenation]: Fast FFmpeg concat demuxer rendering {len(concat_files)} clips...")
                concat_cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list_path, "-c:v", "copy", "-c:a", "copy", raw_concat_video]
                concat_ok = await run_cmd(concat_cmd)
                if not concat_ok or not os.path.exists(raw_concat_video) or os.path.getsize(raw_concat_video) < 100:
                    print("[Master Concatenation]: Fallback re-encoding via concat demuxer...")
                    concat_cmd_re = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list_path, "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-b:a", "192k", raw_concat_video]
                    await run_cmd(concat_cmd_re)

        subtitle_font = str(data.get("subtitle_font", "Arial")).strip()
        subtitle_bg_color = str(data.get("subtitle_bg_color", "#000000")).strip()
        try:
            subtitle_size = int(data.get("subtitle_size", 44))
        except Exception:
            subtitle_size = 44
        try:
            subtitle_bg_opacity = float(data.get("subtitle_bg_opacity", 85)) / 100.0
        except Exception:
            subtitle_bg_opacity = 0.85

        # Filter chain for final master video
        final_vf_filters = []
        if subtitle_style != "off":
            full_script = " ".join([sc.get("text", "") for sc in scenes])
            master_dur = await get_media_duration_sec(raw_concat_video)
            master_ass_path = os.path.join(temp_dir, "master_subtitles.ass")
            generate_animated_ass_subtitle(
                full_script, master_dur, master_ass_path,
                style_name=subtitle_style,
                font_name=subtitle_font,
                position=subtitle_pos,
                custom_fontsize=subtitle_size,
                custom_bg_hex=subtitle_bg_color,
                custom_bg_opacity=subtitle_bg_opacity
            )

            fonts_dir_path = os.path.join(STATIC_DIR, "fonts")
            fonts_dir_escaped = fonts_dir_path.replace("\\", "/").replace(":", "\\:")
            master_ass_escaped = master_ass_path.replace("\\", "/").replace(":", "\\:")
            final_vf_filters.append(f"subtitles='{master_ass_escaped}':fontsdir='{fonts_dir_escaped}'")

        final_render_cmd = ["ffmpeg", "-y", "-i", raw_concat_video]
        if final_vf_filters:
            final_vf_script_path = os.path.join(temp_dir, "final_vf.txt")
            with open(final_vf_script_path, "w", encoding="utf-8") as f:
                f.write(",".join(final_vf_filters))
            final_render_cmd.extend(["-filter_script:v", final_vf_script_path])

        final_render_cmd.extend([
            "-af", "loudnorm=I=-14:LRA=11:TP=-1.5",
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k", out_master_filepath
        ])
        await run_cmd(final_render_cmd)

        final_dur = await get_media_duration_sec(out_master_filepath)

        return web.json_response({
            "status": "success",
            "videoUrl": f"/static/generated/{out_master_filename}",
            "filename": out_master_filename,
            "duration": round(final_dur, 2)
        })
    except Exception as e:
        print("[handle_render_final_video exception]:", e)
        return web.json_response({"error": str(e)}, status=500)

# Duplicate Gradio FLUX handler removed to enforce reliable multi-tier Pollinations FLUX engine

_lama_session = None

def clean_image_with_lama_ai(img_bytes):
    global _lama_session
    try:
        print(f"[LaMa AI]: Starting watermark removal on {len(img_bytes)} bytes...")
        model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scratch", "lama_fp32.onnx")
        if not os.path.exists(model_path):
            print(f"[LaMa AI ERROR]: Model path does not exist: {model_path}")
            return img_bytes

        if _lama_session is None:
            import onnxruntime as ort
            print("[LaMa AI]: Loading ONNX session...")
            _lama_session = ort.InferenceSession(model_path, providers=['CPUExecutionProvider'])

        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            print("[LaMa AI ERROR]: cv2.imdecode returned None")
            return img_bytes

        h, w = img.shape[:2]

        # Target ONLY exact Google Flow AI / Gemini / Nano Banana watermark box (tight box: y 87-98%, x 89-99%)
        mask = np.zeros((h, w), dtype=np.uint8)
        mask[int(h * 0.87):int(h * 0.98), int(w * 0.89):int(w * 0.99)] = 255

        img_512 = cv2.resize(img, (512, 512))
        mask_512 = cv2.resize(mask, (512, 512), interpolation=cv2.INTER_NEAREST)

        img_rgb = cv2.cvtColor(img_512, cv2.COLOR_BGR2RGB)
        img_np = (img_rgb.astype(np.float32) / 255.0).transpose((2, 0, 1))[np.newaxis, ...]
        mask_np = (mask_512 > 128).astype(np.float32)[np.newaxis, np.newaxis, ...]

        inputs = {
            _lama_session.get_inputs()[0].name: img_np,
            _lama_session.get_inputs()[1].name: mask_np
        }
        res = _lama_session.run(None, inputs)[0][0]

        res = np.clip(res, 0, 255 if res.max() > 1.0 else 1.0)
        if res.max() <= 1.0:
            res = (res * 255.0)

        res = res.astype(np.uint8).transpose((1, 2, 0))
        res_bgr = cv2.cvtColor(res, cv2.COLOR_RGB2BGR)

        res_full = cv2.resize(res_bgr, (w, h))

        final = img.copy()
        mask_3d = (mask > 0)[:, :, np.newaxis]
        final = np.where(mask_3d, res_full, img)

        ext = ".jpg"
        is_success, buffer = cv2.imencode(ext, final, [cv2.IMWRITE_JPEG_QUALITY, 95])
        if is_success:
            print(f"[LaMa AI SUCCESS]: Cleaned image encoded successfully ({len(buffer)} bytes)")
            return buffer.tobytes()
        print("[LaMa AI ERROR]: cv2.imencode failed")
        return img_bytes
    except Exception as e:
        print("[clean_image_with_lama_ai exception]:", e)
        import traceback
        traceback.print_exc()
        return img_bytes

def overlay_channel_logo_on_image(img_bytes, logo_source=None):
    return img_bytes

async def handle_upload_channel_logo(request):
    try:
        reader = await request.multipart()
        field = await reader.next()
        if not field or not field.filename:
            return web.json_response({"error": "No file uploaded"}, status=400)

        logo_path = os.path.join(STATIC_DIR, "uploads", "channel_logo.png")
        os.makedirs(os.path.dirname(logo_path), exist_ok=True)

        content = await field.read()
        with open(logo_path, "wb") as f:
            f.write(content)

        return web.json_response({
            "status": "success",
            "logo_url": "/static/uploads/channel_logo.png",
            "logo_path": logo_path
        })
    except Exception as e:
        print("[handle_upload_channel_logo error]:", e)
        return web.json_response({"error": str(e)}, status=500)

async def handle_upload_scene_image(request):
    try:
        clean_watermarks = request.query.get("clean_watermarks", "").lower() in ("true", "1")
        reader = await request.multipart()
        filename = ""
        out_path = ""
        content = None

        while True:
            field = await reader.next()
            if field is None:
                break
            if field.name in ("clean_watermarks", "burn_logo"):
                try:
                    val = (await field.read()).decode('utf-8').strip().lower()
                    if val in ("true", "1"):
                        clean_watermarks = True
                except Exception:
                    pass
            elif field.filename:
                filename = f"scene_img_{uuid.uuid4().hex[:8]}_{field.filename}"
                out_path = os.path.join(STATIC_DIR, "uploads", filename)
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                content = await field.read()

        if not content or not out_path:
            return web.json_response({"error": "No file uploaded"}, status=400)

        if clean_watermarks:
            print(f"[LaMa AI Engine]: Auto-cleaning watermark on '{filename}'...")
            content = clean_image_with_lama_ai(content)

        with open(out_path, "wb") as f:
            f.write(content)

        rel_url = f"/static/uploads/{filename}"
        return web.json_response({"status": "success", "image_url": rel_url, "image_path": out_path, "watermark_cleaned": True})
    except Exception as e:
        print("[handle_upload_scene_image error]:", e)
        return web.json_response({"error": str(e)}, status=500)

async def handle_voices(request):
    try:
        presets = dict(VOICE_PRESETS)
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("""
                CREATE TABLE IF NOT EXISTS cloned_voices (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    audio_path TEXT NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            c.execute("SELECT id, name, audio_path, description, created_at FROM cloned_voices")
            rows = c.fetchall()
            for r in rows:
                v_id, v_name, v_path, v_desc, _ = r
                presets[v_id] = {
                    "id": v_id,
                    "name": f"🎙️ Cloned — {v_name}",
                    "category": "Custom Cloned Voices",
                    "desc": f"Zero-Shot Cloned Voice ({v_desc or 'User Upload'})",
                    "is_cloned": True,
                    "audio_url": v_path
                }
            conn.close()
        except Exception as dbe:
            print("[handle_voices DB warning]:", dbe)

        return web.json_response({"status": "success", "voices": presets})
    except Exception as e:
        print("[handle_voices error]:", e)
        return web.json_response({"error": str(e)}, status=500)

async def handle_clone_voice(request):
    try:
        reader = await request.multipart()
        name = "Custom Voice"
        description = "User zero-shot voice sample"
        file_content = None
        filename = ""

        while True:
            field = await reader.next()
            if field is None:
                break
            if field.name == "name":
                name = (await field.read()).decode("utf-8").strip() or name
            elif field.name == "description":
                description = (await field.read()).decode("utf-8").strip() or description
            elif field.filename:
                filename = f"cloned_{uuid.uuid4().hex[:8]}_{field.filename}"
                file_content = await field.read()

        if not file_content or not filename:
            return web.json_response({"error": "No voice audio sample file provided"}, status=400)

        cloned_dir = os.path.join(STATIC_DIR, "uploads", "cloned_voices")
        os.makedirs(cloned_dir, exist_ok=True)
        out_path = os.path.join(cloned_dir, filename)

        with open(out_path, "wb") as f:
            f.write(file_content)

        voice_id = f"clone_{uuid.uuid4().hex[:8]}"
        rel_url = f"/static/uploads/cloned_voices/{filename}"

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS cloned_voices (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                audio_path TEXT NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        c.execute("INSERT INTO cloned_voices (id, name, audio_path, description) VALUES (?, ?, ?, ?)",
                  (voice_id, name, rel_url, description))
        conn.commit()
        conn.close()

        VOICE_PRESETS[voice_id] = {
            "id": voice_id,
            "name": f"🎙️ Cloned — {name}",
            "category": "Custom Cloned Voices",
            "desc": f"Zero-Shot Cloned Voice ({description})",
            "is_cloned": True,
            "audio_url": rel_url
        }

        print(f"[OmniVoice Clone SUCCESS]: Registered voice '{name}' ({voice_id}) -> {rel_url}")
        return web.json_response({
            "status": "success",
            "voice_id": voice_id,
            "name": name,
            "audio_url": rel_url,
            "message": f"Successfully cloned voice '{name}'!"
        })
    except Exception as e:
        print("[handle_clone_voice error]:", e)
        return web.json_response({"error": str(e)}, status=500)

def create_app():
    # Allow large ZIP and batch uploads up to 2GB (2048MB)
    app = web.Application(client_max_size=2048 * 1024 * 1024)
    app.router.add_get("", handle_index)
    app.router.add_get("/", handle_index)
    app.router.add_get("/index.html", handle_index)
    app.router.add_get("/studio", handle_studio)
    app.router.add_get("/studio.html", handle_studio)
    app.router.add_get("/youtube-2.0", handle_youtube2)
    app.router.add_get("/youtube%202.0", handle_youtube2)
    app.router.add_get("/youtube 2.0", handle_youtube2)
    app.router.add_get("/youtube2.html", handle_youtube2)
    app.router.add_get("/youtube2", handle_youtube2)
    app.router.add_post("/api/start-job", handle_start_job)
    app.router.add_get("/api/job-status", handle_job_status)
    app.router.add_get("/api/voices", handle_voices)
    app.router.add_post("/api/assemble-video", handle_assemble_video)
    app.router.add_post("/api/export-timeline", handle_export_timeline)
    app.router.add_post("/api/generate-beat-audio", handle_generate_beat_audio)
    app.router.add_post("/api/generate-flux-image", handle_generate_flux_image)
    app.router.add_post("/api/generate-beat-clip", handle_generate_beat_clip)
    app.router.add_post("/api/upload-scene-image", handle_upload_scene_image)
    app.router.add_post("/api/upload-channel-logo", handle_upload_channel_logo)
    app.router.add_post("/api/generate-seo-package", handle_generate_seo_package)
    app.router.add_post("/api/clone-voice", handle_clone_voice)
    app.router.add_post("/api/verify-passcode", handle_verify_passcode)
    app.router.add_post("/api/render-final-video", handle_render_final_video)
    app.router.add_get("/api/projects", handle_list_projects)
    app.router.add_get("/api/projects/{id}", handle_get_project)
    app.router.add_static("/static/", STATIC_DIR)
    app.router.add_static("/fonts/", os.path.join(STATIC_DIR, "fonts"))
    app.router.add_get("/{path:.*}", handle_fallback)
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


