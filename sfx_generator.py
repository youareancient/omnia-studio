import os
import math
import struct
import wave
import random

SFX_DIR = os.path.join(os.path.dirname(__file__), "static", "sfx")
os.makedirs(SFX_DIR, exist_ok=True)

SAMPLE_RATE = 44100

def create_sub_bass_boom():
    filename = os.path.join(SFX_DIR, "boom.wav")
    duration = 1.0 # 1 sec
    num_samples = int(SAMPLE_RATE * duration)
    
    with wave.open(filename, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2) # 16-bit
        wf.setframerate(SAMPLE_RATE)
        
        frames = bytearray()
        for i in range(num_samples):
            t = i / SAMPLE_RATE
            # Frequency sweeps from 80Hz down to 35Hz
            freq = 80 - 45 * (t / duration)
            # Exponential decay envelope
            envelope = math.exp(-3.5 * t)
            
            # Fundamental + 2nd harmonic
            val = 0.7 * math.sin(2 * math.pi * freq * t) + 0.3 * math.sin(2 * math.pi * (freq * 0.5) * t)
            sample = int(val * envelope * 24000)
            sample = max(-32768, min(32767, sample))
            frames.extend(struct.pack("<h", sample))
            
        wf.writeframes(frames)
    return filename

def create_whoosh():
    filename = os.path.join(SFX_DIR, "whoosh.wav")
    duration = 0.4 # 400ms
    num_samples = int(SAMPLE_RATE * duration)
    
    with wave.open(filename, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        
        frames = bytearray()
        for i in range(num_samples):
            t = i / SAMPLE_RATE
            # Bell envelope (peaks at t = 0.2s)
            envelope = math.sin(math.pi * (t / duration))
            # Filtered noise
            noise = (random.random() * 2 - 1)
            # Lowpass resonance simulation
            smooth_freq = 400 + 1200 * envelope
            val = noise * 0.5 + 0.5 * math.sin(2 * math.pi * smooth_freq * t)
            
            sample = int(val * envelope * 18000)
            sample = max(-32768, min(32767, sample))
            frames.extend(struct.pack("<h", sample))
            
        wf.writeframes(frames)
    return filename

def create_glitch():
    filename = os.path.join(SFX_DIR, "glitch.wav")
    duration = 0.25 # 250ms
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
    duration = 0.08 # 80ms
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
    print("Generated HD SFX library files:", b, w, g, c)
