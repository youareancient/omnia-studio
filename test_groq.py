import asyncio
import json
import os
import aiohttp

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()

async def test_groq():
    print(f"Testing Groq API. Key present: {bool(GROQ_API_KEY)}")
    if not GROQ_API_KEY:
        print("Please set GROQ_API_KEY environment variable to test locally.")
        return

    system_prompt = (
        "You are a Senior Prompt Engineer for YouTube channels like @misterfinanceyt and @TheWealthCortexx.\n"
        "Your task is to take a 3-5 second script line and write a standalone, detailed image prompt for 2D vector art.\n\n"
        "MASTER PROMPT STYLE:\n"
        "Hand-drawn professional educational cartoon illustration, clean studio-quality digital vector artwork with thick, smooth black outlines, crisp linework, soft flat colors, and polished modern explainer-animation aesthetics. [Describe character pose, facial expression, props, visual humor matching the concept]. Above or beside the character, [describe a thought bubble or graphic overlay with bold black outlines visualizing the concept]. Background is pure white with generous negative space, keeping the composition simple, clutter-free, and high contrast.\n\n"
        "EXAMPLE INPUT: 'Okay, so you want to own a ranch.'\n"
        "EXAMPLE OUTPUT PROMPT: 'Hand-drawn professional educational cartoon illustration, clean studio-quality digital vector artwork with thick, smooth black outlines, crisp linework, soft flat colors, and polished modern explainer-animation aesthetics. A relaxed young boy with slightly messy medium-brown hair sits comfortably on a simple white chair in a clean front three-quarter view. He wears a plain long-sleeve muted blue sweatshirt and light beige trousers, cheek resting gently against his hand with a content smile. Above his head, a large white thought bubble with bold black outlines contains a simple black silhouette of a countryside farm with a farmhouse, barn, silo, and short wooden fence. Pure white background with generous negative space, clutter-free composition.'\n\n"
        "Respond strictly in JSON format: {\"prompt\": \"Hand-drawn...\"}"
    )

    user_line = "Okay, so you want to own a ranch."

    async with aiohttp.ClientSession() as session:
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Script Line: \"{user_line}\""}
            ],
            "temperature": 0.7,
            "response_format": {"type": "json_object"}
        }
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        async with session.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers) as resp:
            print("HTTP Status:", resp.status)
            res_text = await resp.text()
            print("Response:", res_text)

if __name__ == "__main__":
    asyncio.run(test_groq())
