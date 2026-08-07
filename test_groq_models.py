import asyncio
import json
import os
import aiohttp

async def test_key(key):
    print(f"Testing Groq key: {key[:8]}...")
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": "You are a prompt engineer. Respond in valid json."},
            {"role": "user", "content": "Generate a test prompt for 'data center'"}
        ],
        "temperature": 0.7,
        "response_format": {"type": "json_object"}
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                print("HTTP Status Code:", resp.status)
                body = await resp.text()
                print("Body:", body[:300])
    except Exception as e:
        print("Exception:", e)

if __name__ == "__main__":
    k = os.environ.get("GROQ_API_KEY", "").strip()
    if k:
        asyncio.run(test_key(k))
    else:
        print("No GROQ_API_KEY found in local environment.")
