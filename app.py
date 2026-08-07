import asyncio
import json
import os
import re
import uuid
import edge_tts
from aiohttp import web

HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", 7860))

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

async def handle_index(request):
    if os.path.exists(INDEX_HTML_PATH):
        with open(INDEX_HTML_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        return web.Response(text=content, content_type="text/html", charset="utf-8")
    return web.Response(text="<h1>YouTube Voiceover Studio</h1><p>Index file initializing...</p>", content_type="text/html")

async def handle_voices(request):
    return web.json_response(VOICE_PRESETS)

async def handle_generate_stream(request):
    response = web.StreamResponse(
        status=200,
        reason='OK',
        headers={
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*'
        }
    )
    await response.prepare(request)

    try:
        data = await request.json()
        raw_text = data.get("text", "").strip()
        voice_preset = data.get("voice", "andrew")
        rate = data.get("rate", "+1%")
        filename = data.get("filename", "").strip()

        if not raw_text:
            err_msg = json.dumps({"error": "Script text cannot be empty"})
            await response.write(f"data: {err_msg}\n\n".encode("utf-8"))
            return response

        voice_info = VOICE_PRESETS.get(voice_preset, VOICE_PRESETS["andrew"])
        voice_id = voice_info["id"]

        full_humanized_text, paragraphs = humanize_text_for_speech(raw_text)
        total_paras = len(paragraphs)

        if not filename:
            short_id = str(uuid.uuid4())[:6]
            filename = f"voiceover_{voice_preset}_{short_id}.mp3"
        elif not filename.endswith(".mp3"):
            filename += ".mp3"

        out_filepath = os.path.join(DOWNLOADS_DIR, filename)

        init_evt = json.dumps({"progress": 5, "status": f"Humanized text prepared ({total_paras} paragraphs)..."})
        await response.write(f"data: {init_evt}\n\n".encode("utf-8"))
        await asyncio.sleep(0.1)

        temp_chunks = []
        temp_dir = os.path.join(STUDIO_DIR, "temp_chunks")
        os.makedirs(temp_dir, exist_ok=True)

        for i, para in enumerate(paragraphs, start=1):
            if not para.strip():
                continue
            
            chunk_path = os.path.join(temp_dir, f"chunk_{uuid.uuid4().hex}.mp3")
            communicate = edge_tts.Communicate(para, voice_id, rate=rate, pitch="+0Hz")
            await communicate.save(chunk_path)
            temp_chunks.append(chunk_path)

            progress_pct = int((i / total_paras) * 90) + 5
            evt = json.dumps({
                "progress": progress_pct,
                "status": f"Synthesizing paragraph {i} of {total_paras} ({progress_pct}%)..."
            })
            await response.write(f"data: {evt}\n\n".encode("utf-8"))

        merging_evt = json.dumps({"progress": 96, "status": "Merging audio tracks into HD MP3..."})
        await response.write(f"data: {merging_evt}\n\n".encode("utf-8"))

        with open(out_filepath, "wb") as outfile:
            for chunk_file in temp_chunks:
                with open(chunk_file, "rb") as infile:
                    outfile.write(infile.read())

        for chunk_file in temp_chunks:
            try:
                os.remove(chunk_file)
            except Exception:
                pass

        final_evt = json.dumps({
            "success": True,
            "progress": 100,
            "status": "Voiceover completed successfully!",
            "filename": filename,
            "audioUrl": f"/static/generated/{filename}",
            "voice": voice_info["name"],
            "wordCount": len(full_humanized_text.split())
        })
        await response.write(f"data: {final_evt}\n\n".encode("utf-8"))

    except Exception as e:
        print("Error during streaming generation:", e)
        err_evt = json.dumps({"error": str(e)})
        await response.write(f"data: {err_evt}\n\n".encode("utf-8"))

    return response

def create_app():
    app = web.Application()
    app.router.add_get("", handle_index)
    app.router.add_get("/", handle_index)
    app.router.add_get("/index.html", handle_index)
    app.router.add_post("/api/generate-stream", handle_generate_stream)
    app.router.add_get("/api/voices", handle_voices)
    app.router.add_static("/static/", STATIC_DIR)
    return app

if __name__ == "__main__":
    print(f"Starting YouTube Voiceover Studio Online at http://{HOST}:{PORT}")
    web.run_app(create_app(), host=HOST, port=PORT)
