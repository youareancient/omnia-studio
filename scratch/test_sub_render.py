import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import subprocess
from app import generate_animated_ass_subtitle

def test_render():
    os.makedirs("scratch/temp_test", exist_ok=True)
    ass_file = "scratch/temp_test/test.ass"
    out_mp4 = "scratch/temp_test/test_out.mp4"
    
    # Generate test ASS
    generate_animated_ass_subtitle("Testing kinetic animated subtitles with Hormozi yellow highlighting", 3.0, ass_file, style_name="hormozi")
    print("Generated ASS file:", ass_file)
    
    escaped_ass = ass_file.replace("\\", "/").replace(":", "\\:")
    
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "color=c=blue:s=1280x720:d=3",
        "-vf", f"vignette=PI/4,subtitles='{escaped_ass}'",
        "-c:v", "libx264", "-preset", "ultrafast",
        out_mp4
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0 and os.path.exists(out_mp4):
        print(f"SUCCESS: Rendered video clip with animated subtitles! Size: {os.path.getsize(out_mp4)} bytes")
    else:
        print("FFmpeg error:", res.stderr)

if __name__ == "__main__":
    test_render()
