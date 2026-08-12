import asyncio
import os
import edge_tts

SAMPLES_DIRS = ["public/static/samples", "public/samples"]
for d in SAMPLES_DIRS:
    os.makedirs(d, exist_ok=True)

SAMPLES = {
    "andrew": ("en-US-AndrewNeural", "Welcome to YouTube Voiceover Studio. Ready to create your next viral video essay?"),
    "christopher": ("en-US-ChristopherNeural", "In the deep shadows of global finance, some stories stay hidden until now."),
    "ava": ("en-US-AvaNeural", "Artificial intelligence is revolutionizing the way we build data centers."),
    "guy": ("en-US-GuyNeural", "This is the daily tech and business report, broadcasting live from Silicon Valley."),
    "brian": ("en-US-BrianNeural", "Success isn't given. It is earned every single day in the quiet hours."),
    "emma": ("en-US-EmmaNeural", "It was 3 AM when the strange radio frequency started transmitting again.")
}

async def generate():
    for name, (voice, text) in SAMPLES.items():
        communicate = edge_tts.Communicate(text, voice, rate="+1%")
        # Save to first dir
        primary_path = os.path.join(SAMPLES_DIRS[0], f"{name}_sample.mp3")
        print(f"Generating {name} sample...")
        await communicate.save(primary_path)
        # Copy to other dirs
        for d in SAMPLES_DIRS[1:]:
            target_path = os.path.join(d, f"{name}_sample.mp3")
            with open(primary_path, "rb") as f_in, open(target_path, "wb") as f_out:
                f_out.write(f_in.read())
        print(f"Saved {name}_sample.mp3 ({os.path.getsize(primary_path)} bytes)")

if __name__ == "__main__":
    asyncio.run(generate())
