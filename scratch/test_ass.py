import os
import subprocess

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
    position: str = "bottom"
):
    words = script_text.strip().split()
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
        primary_color = "&H00FFFFFF"     # White (base)
        secondary_color = "&H0000FFFF"   # Yellow (highlight)
        outline_color = "&H00000000"     # Black outline
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
    else:  # 'cinematic'
        primary_color = "&H00FFFFFF"     # White
        secondary_color = "&H002997FF"   # Blue highlight
        outline_color = "&H00000000"
        fontsize = 38
        outline = 2
        shadow = 1

    header = f"""[Script Info]
Title: Studio Animated Subtitles
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: None

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{fontsize},{primary_color},{secondary_color},{outline_color},&H80000000,-1,0,0,0,100,100,0,0,1,{outline},{shadow},{alignment},20,20,40,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events = []
    chunk_size = 4
    chunks = [words[i:i + chunk_size] for i in range(0, len(words), chunk_size)]
    
    current_time = 0.0
    for chunk in chunks:
        chunk_dur = len(chunk) * time_per_word
        start_ts = format_ass_timestamp(current_time)
        end_ts = format_ass_timestamp(current_time + chunk_dur)
        
        # Word-by-word animated karaoke sequence
        karaoke_text = ""
        for word in chunk:
            karaoke_text += f"{{\\kf{dur_cs_per_word}}}{word} "
        
        events.append(f"Dialogue: 0,{start_ts},{end_ts},Default,,0,0,0,,{karaoke_text.strip()}")
        current_time += chunk_dur

    with open(out_ass_path, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(events))

if __name__ == "__main__":
    test_ass = "scratch/test_sub.ass"
    generate_animated_ass_subtitle("Okay so you want to own a data center for artificial intelligence", 4.0, test_ass, style_name="hormozi")
    print(f"Generated test ASS subtitle file: {test_ass}")
    if os.path.exists(test_ass):
        with open(test_ass, "r") as f:
            print(f.read())
