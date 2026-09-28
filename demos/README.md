# Civic Path Navigator demo videos

Two narrated cuts show the **real local Civic Path Navigator interface** using only simulator fixtures:

- [`civic-pathfinder-demo.mp4`](./civic-pathfinder-demo.mp4) — 16:9 product overview (1600×900).
- [`civic-pathfinder-social.mp4`](./civic-pathfinder-social.mp4) — 9:16 social cut (1080×1920), with the full landscape interface preserved in a framed viewport rather than cropped.
- [`captions.srt`](./captions.srt) — timed English captions for both cuts.

The walkthrough follows a small-business service request in Hyderabad, signs in to the **synthetic Rani demo account**, opens its sample Udyam pathway, shows its dependency map and saved progress, then visits the documents dashboard and suggested next steps. A warm English (India) voice-over explains the journey.

## Demo-data notice

This is a local sandbox demonstration—not a real application, eligibility decision, or submission to a government portal. The user, document labels, progress, and pathway are fixtures from `backend/sim/run_sim.py`; no real citizen documents or live DigiLocker connection are used. The interface and voice-over remind viewers to check current rules and fees with the linked official services.

## Production notes

[Recordly](https://github.com/webadderallorg/Recordly) (v1.4.0) informed the focused cursor treatment and editorial framing. To keep the walkthrough reproducible and preserve the app's actual interactions, the browser capture is driven by Playwright, then narrated, captioned, and assembled with FFmpeg. The portrait cut retains all of the app screen instead of sacrificing side content to a crop.

The final videos, caption file, and reusable capture/render scripts live in this directory. The raw browser capture and generated portrait background are transient assets and are ignored by Git.

## Recreate locally

1. From the repository root, run the simulator once to populate `backend/t_sim.db`:

   ```bash
   cd backend
   python3 sim/run_sim.py
   cd ..
   python3 demos/prepare_demo_data.py
   ```

2. Start the backend against that **simulator database only**, and start the frontend in another terminal:

   ```bash
   cd backend
   DATABASE_URL=sqlite:///./t_sim.db ALLOW_DEV_SECRET=1 CIVIC_DEV=1 \
     FRONTEND_ORIGINS=http://localhost:5173,http://127.0.0.1:5173 \
     python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

   ```bash
   cd frontend
   npm ci
   npm run dev -- --host 0.0.0.0 --port 5173
   ```

3. In a Linux graphical session with Chromium and ffmpeg available, install Playwright's recorder dependency if needed, capture, then render:

   ```bash
   cd frontend
   npx playwright install ffmpeg
   DISPLAY=:91 node ../demos/capture_walkthrough.mjs
   cd ..
   bash demos/render_videos.sh
   ```

   The WAV narration source is `demos/narration.wav`. The recorder defaults to the local preview URL and the synthetic fixture account; it never submits a live government application.
