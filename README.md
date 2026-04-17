# InterviewWhisper (Python)

Cross-platform desktop app: hold a hotkey to record an interview question from your mic, then see a concise AI answer in a floating overlay. Uses **Gemini 2.5 Flash** for both speech-to-text (audio transcription) and answer generation.

## Features

- **Hold-to-record**: Press and hold **Alt+R** (configurable) to record; release to transcribe and get an answer.
- **Speech-to-text**: Gemini 2.5 Flash (audio → text).
- **AI answers**: Gemini 2.5 Flash with a technical-interview prompt (~300 words).
- **Floating overlay**: Semi-transparent, always-on-top, draggable, resizable window.
- **Clear**: **Alt+C** or the **Clear** button in the overlay; no auto-clear.
- **Config**: `config.json` for API keys, hotkeys, model, transparency.

## Requirements

- Python 3.10+
- Microphone
- Windows, macOS, or Linux

## Setup

1. **Clone or copy** the project and go to its folder:
   ```bash
   cd inter
   ```

2. **Create a virtual environment** (recommended):
   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure** `config.json`:
   - **Single key:** `gemini_api_key`: Your [Google AI Studio](https://aistudio.google.com/apikey) API key.
   - **Multiple keys (auto-switch on quota):** `gemini_api_keys`: Array of API keys; when one hits rate limit (429), the app switches to the next automatically.
   - Optionally change `hotkey_record`, `hotkey_clear`, `llm_model`, `transparency`.

   Copy from example if needed:
   ```bash
   copy config.json.example config.json
   ```
   Then edit `config.json` and add your keys.

## Run

**Background (no console window, recommended on Windows):**
- Double-click **`run_interview_whisper.vbs`** in the project folder, or
- Run: `pythonw main.py`

**With console (for debugging):**
```bash
python main.py
```
On Windows, if you start with `python main.py`, the app will re-launch itself with `pythonw` so the console closes and only the overlay remains.

- **Record**: Hold **Alt+R**, speak the question, release. The app transcribes with Gemini and generates the answer with Gemini 2.5 Flash; the answer appears in the overlay.
- **Clear**: Press **Alt+C** or click **Clear** in the overlay (no auto-clear).

**Note:** The process still appears in Task Manager (e.g. as `pythonw.exe`). Hiding it from Task Manager would require kernel-level techniques and is not supported.

## Configuration (`config.json`)

| Key | Description |
|-----|-------------|
| `gemini_api_key` | Single Gemini API key (used if `gemini_api_keys` is not set) |
| `gemini_api_keys` | List of Gemini API keys; auto-switches to next on quota/429 errors |
| `hotkey_record` | e.g. `["alt", "r"]` – hold to record |
| `hotkey_clear` | e.g. `["alt", "c"]` – clear overlay |
| `llm_model` | e.g. `gemini-2.5-flash` (default) |
| `transparency` | 0.0–1.0 (default 0.8) |
| `exclude_from_capture` | If true (default), overlay is hidden from screen share on Windows; window is opaque. |
| `stt_provider` | `gemini` (default) or `vosk` for offline |

## Offline STT (Vosk)

For local speech-to-text without any API:

1. Install: `pip install vosk`
2. Download a [Vosk model](https://alphacephei.com/vosk/models) and set its path in config, e.g. `"vosk_model_path": "C:/path/to/vosk-model"`.
3. Set `"stt_provider": "vosk"` in `config.json`. Answer generation still uses Gemini.

## Stealth / screen sharing

**Windows 10 (May 2020 update) and later:** With `exclude_from_capture: true` in config (default), the overlay is **excluded from screen capture**. When you share your full screen in Meet, Teams, Zoom, etc., the overlay is not visible to others. **Important:** The Windows API that does this does **not** work on transparent (layered) windows, so when stealth is on the overlay is **opaque** (no transparency). You still see it on your monitor; it just does not appear in the shared stream. Set `exclude_from_capture: false` if you prefer a semi-transparent overlay that may be visible in screen shares.

**macOS / Linux:** No OS-level “exclude from capture” API is used. Use low opacity and share only a specific window when possible.

## Errors

Errors are logged to the console (stderr), not shown as popups. Run from a terminal to see messages:

```bash
python main.py
```

## Resume-based answers

Place your resume or a short bio in **`resume_context.txt`** in the project folder. When the interviewer asks about your projects, experience, skills, or education, the app uses this file so answers match your background (e.g. NotesX, SignifyX, ConnectX, CSI, certifications). Edit `resume_context.txt` anytime to update the context.

## Project layout

```
inter/
  main.py            # Entry point, hotkeys, orchestration
  config_loader.py   # Load config.json
  config.json        # Your keys and settings (create from config.json.example)
  config.json.example
  resume_context.txt # Your resume / bio (used for interview answers)
  overlay_window.py  # Floating tkinter window
  audio_recorder.py  # Microphone recording → WAV
  speech_to_text.py  # Gemini (or Vosk) transcription
  llm_client.py      # Gemini API (answers grounded in resume_context.txt)
  api_key_manager.py  # Multi-key support; auto-switch on quota/429
  requirements.txt
  README.md
```

## License

Use for educational purposes. Respect your platform’s terms of service (Google) and employer policies when using during interviews.
