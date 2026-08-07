import os
import math
import struct
import wave
import random

STUDIO_DIR = os.path.dirname(os.path.abspath(__file__))
SFX_DIR = os.path.join(STUDIO_DIR, "public", "sfx")
os.makedirs(SFX_DIR, exist_ok=True)

SAMPLE_RATE = 44100

def create_sub_bass_boom():
    filename = os.path.join(SFX_DIR, "boom.wav")
    duration = 1.2 # 1.2 sec
    num_samples = int(SAMPLE_RATE * duration)
    
    with wave.open(filename, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        
        frames = bytearray()
        for i in range(num_samples):
            t = i / SAMPLE_RATE
            freq = 90 - 55 * (t / duration)
            envelope = math.exp(-3.0 * t)
            
            val = 0.8 * math.sin(2 * math.pi * freq * t) + 0.3 * math.sin(2 * math.pi * (freq * 0.5) * t)
            sample = int(val * envelope * 28000)
            sample = max(-32768, min(32767, sample))
            frames.extend(struct.pack("<h", sample))
            
        wf.writeframes(frames)
    return filename

def create_whoosh():
    filename = os.path.join(SFX_DIR, "whoosh.wav")
    duration = 0.45 # 450ms
    num_samples = int(SAMPLE_RATE * duration)
    
    with wave.open(filename, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        
        frames = bytearray()
        for i in range(num_samples):
            t = i / SAMPLE_RATE
            envelope = math.sin(math.pi * (t / duration))
            noise = (random.random() * 2 - 1)
            smooth_freq = 350 + 1500 * envelope
            val = noise * 0.6 + 0.4 * math.sin(2 * math.pi * smooth_freq * t)
            
            sample = int(val * envelope * 22000)
            sample = max(-32768, min(32767, sample))
            frames.extend(struct.pack("<h", sample))
            
        wf.writeframes(frames)
    return filename

def create_glitch():
    filename = os.path.join(SFX_DIR, "glitch.wav")
    duration = 0.25
    num_samples = int(SAMPLE_RATE * duration)
    
    with wave.open(filename, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        
        frames = bytearray()
        for i in range(num_samples):
            t = i / SAMPLE_RATE
            envelope = math.sin(math.pi * (t / duration))
            freq = 600 + (int(t * 50) % 5) * 400
            val = math.sin(2 * math.pi * freq * t)
            if random.random() < 0.2:
                val = (random.random() * 2 - 1)
                
            sample = int(val * envelope * 20000)
            sample = max(-32768, min(32767, sample))
            frames.extend(struct.pack("<h", sample))
            
        wf.writeframes(frames)
    return filename

def create_click():
    filename = os.path.join(SFX_DIR, "click.wav")
    duration = 0.08
    num_samples = int(SAMPLE_RATE * duration)
    
    with wave.open(filename, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        
        frames = bytearray()
        for i in range(num_samples):
            t = i / SAMPLE_RATE
            envelope = math.exp(-40.0 * t)
            freq = 2400
            val = math.sin(2 * math.pi * freq * t)
            
            sample = int(val * envelope * 22000)
            sample = max(-32768, min(32767, sample))
            frames.extend(struct.pack("<h", sample))
            
        wf.writeframes(frames)
    return filename

if __name__ == "__main__":
    b = create_sub_bass_boom()
    w = create_whoosh()
    g = create_glitch()
    c = create_click()
    print("Generated HD SFX library files in public/sfx:", b, w, g, c)
