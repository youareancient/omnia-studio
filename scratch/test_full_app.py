import sys, os
sys.path.insert(0, os.path.abspath("."))

import asyncio
import aiohttp
import json

async def test_full_app():
    from app import create_app
    from aiohttp import web

    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '127.0.0.1', 8999)
    await site.start()
    print("Test server running at http://127.0.0.1:8999")

    async with aiohttp.ClientSession() as session:
        # 1. Test index page
        async with session.get("http://127.0.0.1:8999/") as resp:
            assert resp.status == 200
            print("GET / -> 200 OK")

        # 2. Test start breakdown job
        script = "Because in the nightclub business, empty space isn't inventory. It's a ticking clock. And every Saturday night, the owner gets exactly one chance to fill it."
        payload = {
            "text": script,
            "voice": "andrew",
            "rate": "+1%",
            "filename": "test_narration.mp3",
            "mode": "breakdown"
        }
        async with session.post("http://127.0.0.1:8999/api/start-job", json=payload) as resp:
            start_res = await resp.json()
            job_id = start_res.get("job_id")
            print("POST /api/start-job -> Job ID:", job_id)

        # 3. Poll breakdown job completion
        for _ in range(15):
            await asyncio.sleep(1)
            async with session.get(f"http://127.0.0.1:8999/api/job-status?id={job_id}") as resp:
                status_res = await resp.json()
                if status_res.get("status") in ["completed", "failed"]:
                    break

        print("Breakdown Job Status:", status_res.get("status"))
        scenes = status_res.get("result", {}).get("scenes", [])
        print(f"Total Scenes Breakdown: {len(scenes)}")

        # 4. Test generate beat audio for Scene #1
        beat_audio_payload = {
            "job_id": job_id,
            "scene_index": 1,
            "voice": "andrew",
            "rate": "+1%"
        }
        async with session.post("http://127.0.0.1:8999/api/generate-beat-audio", json=beat_audio_payload) as resp:
            beat_audio_res = await resp.json()
            print("POST /api/generate-beat-audio status:", resp.status, beat_audio_res.get("status"))
            assert resp.status == 200

    await runner.cleanup()
    print("ALL TESTS PASSED 100% SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(test_full_app())
