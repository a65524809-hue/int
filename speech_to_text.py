"""Speech-to-text: Gemini 2.5 Flash (audio → transcript). Auto-switches API key on quota/rate limit. Optional Vosk for offline."""
import os
import sys

from api_key_manager import init_keys, get_current_key, get_keys, switch_to_next_key, is_quota_error


def transcribe_gemini(wav_path: str, config: dict) -> str:
    """Transcribe WAV file using Gemini API; auto-switch key on quota/rate-limit."""
    init_keys(config)
    model = config.get("llm_model") or "gemini-2.5-flash"
    api_key = get_current_key()
    if not api_key:
        print("[STT] No Gemini API key(s) set.", file=sys.stderr)
        return ""
    key_list = get_keys()
    keys_available = len(key_list)
    keys_tried = 0
    while keys_tried < keys_available:
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            f = genai.upload_file(wav_path, mime_type="audio/wav")
            model_obj = genai.GenerativeModel(model)
            response = model_obj.generate_content(
                ["Transcribe the speech in this audio. Output only the transcribed text, nothing else.", f],
            )
            if not response or not response.text:
                return ""
            return response.text.strip()
        except Exception as e:
            if is_quota_error(e) and keys_available > 1:
                next_key = switch_to_next_key()
                if next_key:
                    api_key = next_key
                    keys_tried += 1
                    continue
                print(f"[STT] All {keys_available} keys hit quota.", file=sys.stderr)
            else:
                print(f"[STT] Gemini transcription error: {e}", file=sys.stderr)
            return ""
    return ""


def transcribe_vosk(wav_path: str, model_path: str = None) -> str:
    """Transcribe using local Vosk (offline). Requires vosk + model."""
    try:
        import json
        import wave
        import vosk
        if not model_path or not os.path.isdir(model_path):
            print("[STT] Vosk model path not set or invalid.", file=sys.stderr)
            return ""
        model = vosk.Model(model_path)
        wf = wave.open(wav_path, "rb")
        rec = vosk.KaldiRecognizer(model, wf.getframerate())
        result = []
        while True:
            data = wf.readframes(4000)
            if not data:
                break
            if rec.AcceptWaveform(data):
                part = json.loads(rec.Result())
                if part.get("text"):
                    result.append(part["text"])
        part = json.loads(rec.FinalResult())
        if part.get("text"):
            result.append(part["text"])
        wf.close()
        return " ".join(result).strip()
    except ImportError:
        print("[STT] Vosk not installed. pip install vosk", file=sys.stderr)
        return ""
    except Exception as e:
        print(f"[STT] Vosk error: {e}", file=sys.stderr)
        return ""


def transcribe(wav_path: str, config: dict) -> str:
    """Dispatch: Gemini (default, with multi-key support) or Vosk."""
    provider = (config.get("stt_provider") or "gemini").lower()
    if provider == "vosk":
        return transcribe_vosk(wav_path, config.get("vosk_model_path"))
    return transcribe_gemini(wav_path, config)
