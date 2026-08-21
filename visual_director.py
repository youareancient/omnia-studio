import asyncio
import json
import os
import re
import aiohttp

STUDIO_DIR = os.path.dirname(os.path.abspath(__file__))
PROMPT_FILE = os.path.join(STUDIO_DIR, "prompts", "master_visual_director.txt")

# Load .env file automatically
env_file = os.path.join(STUDIO_DIR, ".env")
if os.path.exists(env_file):
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                if k.strip() not in os.environ:
                    os.environ[k.strip()] = v.strip().strip('"\'')

PROMPT_STORYWORLD_FILE = os.path.join(STUDIO_DIR, "prompts", "cinematic_economic_storyworld.txt")
PROMPT_MASTER_FILE = os.path.join(STUDIO_DIR, "prompts", "master_visual_director.txt")
PROMPT_VIKAS_FILE = os.path.join(STUDIO_DIR, "prompts", "vikas_visual_director.txt")

def get_system_prompt(style: str = "vikas"):
    style_key = (style or "vikas").lower()
    
    if style_key == "vikas" and os.path.exists(PROMPT_VIKAS_FILE):
        with open(PROMPT_VIKAS_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()

    if style_key == "adaptive_diorama" and os.path.exists(PROMPT_MASTER_FILE):
        with open(PROMPT_MASTER_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
            
    if os.path.exists(PROMPT_STORYWORLD_FILE):
        with open(PROMPT_STORYWORLD_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()

    if os.path.exists(PROMPT_MASTER_FILE):
        with open(PROMPT_MASTER_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
            
    return """You are an expert AI Image Prompt Engineer and Visual Storyboard Director. Output 2D educational vector cartoon image prompts as valid JSON."""

async def analyze_script_with_groq(script_text: str, manual_style: str = "vikas", target_generator: str = "flux", api_key: str = None):
    groq_key = api_key or os.environ.get("GROQ_API_KEY", "").strip()
    if not groq_key:
        raise ValueError("GROQ_API_KEY is not configured in environment or .env file.")

    effective_style = manual_style if (manual_style and manual_style.lower() != "auto") else "vikas"
    system_prompt = get_system_prompt(effective_style)
    
    user_prompt = f"Script to Analyze and Turn into Image Prompts:\n\n{script_text}"
    if effective_style:
        user_prompt += f"\n\n[USER MANDATE]: Force the Primary Visual Style to be: '{effective_style}'"

    user_prompt += "\n\nFormat your final response strictly as a JSON object adhering to the schema."

    candidate_models = ["groq/compound", "openai/gpt-oss-120b", "qwen/qwen3.6-27b", "groq/compound-mini"]
    headers = {
        "Authorization": f"Bearer {groq_key}",
        "Content-Type": "application/json"
    }

    last_error = None
    async with aiohttp.ClientSession() as session:
        for model_name in candidate_models:
            try:
                payload = {
                    "model": model_name,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 4096,
                    "response_format": {"type": "json_object"}
                }

                async with session.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=90)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        raw_content = data["choices"][0]["message"]["content"]
                        
                        # Parse JSON
                        parsed = json.loads(raw_content)
                        
                        # Post-process prompts for specific target generators if requested
                        if "scene_prompts" in parsed and isinstance(parsed["scene_prompts"], list):
                            for scene in parsed["scene_prompts"]:
                                base_prompt = scene.get("image_prompt", "")
                                if target_generator == "midjourney":
                                    if "--ar" not in base_prompt:
                                        scene["image_prompt"] = f"{base_prompt} --ar 16:9 --v 6.0 --style raw"
                                elif target_generator == "flux":
                                    if "cinematic 3d miniature" not in base_prompt.lower():
                                        scene["image_prompt"] = f"Cinematic 3D miniature diorama, {base_prompt}, 8k, highly detailed"
                                scene["target_generator"] = target_generator

                        return parsed
                    else:
                        err_body = await resp.text()
                        last_error = f"Model '{model_name}' Error ({resp.status}): {err_body}"
                        print(f"[VisualDirector Warning]: {last_error}")
            except Exception as e:
                last_error = str(e)
                print(f"[VisualDirector Warning]: Exception on {model_name}: {e}")

    raise RuntimeError(f"All candidate models failed. Last error: {last_error}")
