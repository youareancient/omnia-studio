import asyncio
import os
import edge_tts

SAMPLES_DIR = "public/static/samples"
os.makedirs(SAMPLES_DIR, exist_ok=True)

SAMPLES = {
    "andrew": ("en-US-AndrewNeural", "Welcome to YouTube Voiceover Studio. Ready to create your next viral video essay?"),
    "christopher": ("en-US-ChristopherNeural", "In the deep shadows of global finance, some stories stay hidden until now."),
    "ava": ("en-US-AvaNeural", "Artificial intelligence is revolutionizing the way we build data centers."),
    "guy": ("en-US-GuyNeural", "This is the daily tech and business report, broadcasting live from Silicon Valley.")
}

async def generate():
    for name, (voice, text) in SAMPLES.items():
        out_path = os.path.join(SAMPLES_DIR, f"{name}_sample.mp3")
        print(f"Generating {name} sample: {out_path}...")
        communicate = edge_tts.Communicate(text, voice, rate="+1%")
        await communicate.save(out_path)
        print(f"Saved {out_path} ({os.path.getsize(out_path)} bytes)")

if __name__ == "__main__":
    asyncio.run(generate())
