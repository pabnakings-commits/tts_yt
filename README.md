# AI Voice Studio

A local, CPU-only AI text-to-speech app for creating narration for YouTube
documentaries, faceless videos, news/commentary, storytelling and explainer
content. No GPU required, no cloud API, no subscription — everything runs
on your machine after the one-time setup.

- **Engine:** [Kokoro-82M](https://github.com/thewh1teagle/kokoro-onnx) (ONNX, CPU inference via onnxruntime)
- **Backend:** Python + FastAPI
- **Frontend:** React + Vite + TypeScript
- **Voices:** 9 curated English voices (5 male, 4 female) organized by style
- **Output:** WAV (lossless) and MP3 (via FFmpeg)

---

## 1. Requirements

| Requirement | Notes |
|---|---|
| Windows 10/11 (or Linux/macOS) | Tested with `start.bat` on Windows |
| Python 3.10 – 3.12 | Must be on your PATH (`python --version`) |
| Node.js 18+ (LTS) | Only needed the first time, to build the web UI |
| ~1 GB free disk space | For the Kokoro model files (~350 MB) + app |
| FFmpeg (optional) | Only required for MP3 export — WAV works without it |
| **No GPU required** | The app never uses CUDA; it always runs on CPU |

---

## 2. Installation & First Run

1. Download/clone this project onto your Windows PC.
2. Double-click **`start.bat`** (or run it from a terminal: `start.bat`).

On the first run, the script will automatically:

1. Create a Python virtual environment (`.venv/`).
2. Install all Python dependencies from `requirements.txt`.
3. Check whether FFmpeg is installed (warns if missing — MP3 export needs it).
4. Install frontend dependencies and build the web UI (`frontend/dist/`).
5. Start the FastAPI server and open your browser to **http://localhost:8000**.

The Kokoro voice model (~350 MB total) is downloaded automatically the
first time you click **Generate Voice** (or on first backend startup) and
is cached in `models/`. It is **never downloaded again** on subsequent
runs — the app checks `models/` first and reuses the cached files.

### Exact command to start the app

```
start.bat
```

This is the only command you need. It is idempotent — running it again
skips steps that are already done (venv, pip installs, npm installs,
frontend build) and just starts the server.

If you ever want to run it manually instead of via the script:

```
.venv\Scripts\activate
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

then open http://localhost:8000 in your browser.

---

## 3. Using the app

1. **Studio tab** — pick a voice, paste your script, adjust speed
   (0.75x–1.25x), click **Generate Voice**.
2. A progress bar shows live status: *Preparing model → Generating voice →
   Combining segments → Processing audio → Finalizing → Done*. The UI
   stays responsive the whole time — generation runs as a background job.
3. Once done, play the audio directly in the browser, or download it as
   **WAV** or **MP3**.
4. **Projects tab** — save scripts/voices/audio as named projects
   (e.g. "Fishing News", "BMW Documentary") that persist across restarts.
5. **Settings tab** — see engine/device/FFmpeg status, change the output
   format (WAV / MP3 / both), and change the output folder.

Long scripts (multi-paragraph YouTube scripts) are handled automatically:
the app cleans up whitespace/line breaks, splits the script into
sentence-safe chunks, generates each chunk, and stitches the audio back
together in the correct order with natural pauses between chunks — so you
can paste an entire video script in one go.

---

## 4. Where files are stored

```
output/
    project_001/
        voice.wav
        voice.mp3
        metadata.json      # voice, text, speed, duration, engine, model, timings
    project_002/
        ...

projects/
    fishing-news/
        script.txt
        voice.wav
        voice.mp3
        metadata.json
        project.json        # id, name, voice, speed, timestamps
```

- Every generation (whether or not it's tied to a project) is saved under
  `output/project_NNN/` with an incrementing number.
- If you generate audio while a project name is attached, a copy is also
  saved into `projects/<project-slug>/` so the project keeps its own
  script + audio + metadata.
- `logs/app.log` contains technical logs (rotated automatically) — check
  this if something goes wrong; the UI never shows raw stack traces.

### Changing the output directory

Go to **Settings → Output → Output Folder**, enter a new path, and click
**Save**. New generations will be written there from then on. You can also
edit `backend/config/user_settings.json` directly if you prefer.

---

## 5. Adding or changing voices

Voices are defined in [`voices/voices.json`](voices/voices.json):

```json
{
  "engine": "kokoro",
  "model": "kokoro-v1.0",
  "voices": [
    {
      "id": "am_michael",
      "name": "Documentary Male",
      "gender": "male",
      "style": "documentary",
      "language": "en-us",
      "description": "Grounded, professional American male voice."
    }
  ]
}
```

- `id` must be a real Kokoro voice id (see the full list at
  [hexgrad/Kokoro-82M/VOICES.md](https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md) —
  American English voices start with `af_`/`am_`, British with `bf_`/`bm_`).
- Add a new entry with any of those ids to make it selectable in the UI —
  no code changes needed. Restart the server to pick up changes.
- The 9 voices shipped by default were chosen for narration quality and
  organized into style categories (Documentary, Deep, Natural, Energetic,
  Calm) rather than exposing all ~50 raw Kokoro voice names.

---

## 6. Troubleshooting

**FFmpeg: Not Found (Settings page)**
MP3 export needs FFmpeg on your PATH. WAV export still works fine without
it. To install on Windows:
```
winget install ffmpeg
```
or download a build from https://ffmpeg.org/download.html, add its `bin`
folder to your PATH, and restart `start.bat`.

**Model download failed / stuck**
The app downloads `kokoro-v1.0.onnx` (~326 MB) and `voices-v1.0.bin`
(~28 MB) from GitHub on first use, into `models/`. If the download fails
(network issue), just retry generating — the app resumes by re-downloading
only missing/incomplete files (it never reuses a partial file). You can
also download them manually and place them in `models/`:
- https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/kokoro-v1.0.onnx
- https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/voices-v1.0.bin

**Generation is slow**
This is expected on CPU-only hardware — the app prioritizes voice quality
and stability over speed, as requested. A modern CPU generates roughly
2–3x faster than real-time (e.g. a 5-minute script takes ~2 minutes). Only
one generation runs at a time by design, so the app never overloads your
CPU even if you queue up several scripts.

**Port 8000 already in use**
Edit the port in `start.bat` (the `--port 8000` argument) and re-run.

**"Python was not found" / "npm was not found"**
Install Python 3.10–3.12 from python.org and Node.js LTS from nodejs.org,
making sure both are added to your PATH during installation, then re-run
`start.bat`.

---

## 7. Architecture

```
ai-voice-studio/
├── backend/
│   ├── main.py                # FastAPI app, serves API + built frontend
│   ├── api/routes.py          # All REST endpoints
│   ├── services/
│   │   ├── tts_service.py     # TTSEngine interface + KokoroEngine (CPU)
│   │   ├── model_downloader.py# Downloads & caches Kokoro model files
│   │   ├── voice_registry.py  # Loads voices/voices.json
│   │   ├── text_utils.py      # Script cleanup + sentence-safe chunking
│   │   ├── audio_service.py   # Normalize, trim silence, WAV/MP3 export
│   │   ├── job_manager.py     # Background job queue (1 worker, CPU-safe)
│   │   └── project_service.py # Filesystem-backed project CRUD
│   ├── models/schemas.py      # Pydantic request/response models
│   └── config/settings.py     # Paths, persisted settings, FFmpeg/GPU checks
├── frontend/
│   └── src/
│       ├── pages/              Studio.tsx, Projects.tsx, Settings.tsx
│       ├── components/         AudioPlayer.tsx
│       └── services/api.ts     Typed fetch client
├── models/          # Downloaded Kokoro model files (git-ignored)
├── voices/voices.json
├── projects/        # Saved projects (git-ignored contents)
├── output/          # Every generation, project_001/, project_002/, ...
├── logs/app.log
├── requirements.txt
├── start.bat
└── README.md
```

### Adding another TTS engine later

The app is built around a `TTSEngine` interface
(`backend/services/tts_service.py`). Kokoro is the only implementation
today, but a fallback engine (e.g. Piper, for even lighter-weight CPU
inference) can be added without touching the API, job queue, or frontend:

1. Implement the `TTSEngine` abstract class (`load`, `synthesize`,
   `list_voices`, `model_ready`).
2. Register it in the `_ENGINES` dict at the bottom of `tts_service.py`.
3. Point `Settings.engine` at the new key.

A `PiperEngine` placeholder class already sketches out where this goes.

### Why CPU-only, no CUDA

`requirements.txt` installs plain `onnxruntime` (not `onnxruntime-gpu`), so
the app has no CUDA dependency at all — it will run identically on a
machine with or without an NVIDIA GPU. The Settings page detects an NVIDIA
GPU via `nvidia-smi` purely for information; it never changes how
inference runs.

---

## 8. API reference

| Method | Path | Description |
|---|---|---|
| GET | `/api/voices` | List available voices |
| GET | `/api/system` | Python/device/FFmpeg/model status |
| GET | `/api/settings` | Current settings |
| POST | `/api/settings` | Update output format / output folder |
| POST | `/api/generate` | Start a generation job, returns `job_id` |
| GET | `/api/jobs/{job_id}` | Poll job status/progress |
| GET | `/api/projects` | List projects |
| POST | `/api/projects` | Create a project |
| GET | `/api/projects/{id}` | Get project detail |
| DELETE | `/api/projects/{id}` | Delete a project |
| GET | `/api/audio/{audio_id}/wav` | Download/stream WAV |
| GET | `/api/audio/{audio_id}/mp3` | Download/stream MP3 |
| GET | `/api/audio/{audio_id}/metadata` | Get generation metadata |

All errors return JSON like `{"detail": "..."}` with an appropriate HTTP
status code — the frontend never shows raw Python tracebacks.
