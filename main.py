"""
InterviewWhisper - Python

- Normal mode:
  Hold hotkey (default Alt+R) to record; release to transcribe and get Gemini answer.
  Alt+C to clear overlay. Config via config.json.

- Exam mode:
  Use the 'Exam' button on the overlay to make the window extra transparent.
  Press Alt+S to capture the current screen (MCQ question) and send it to Gemini.
  Hold Alt+A to show the full-text correct option the model selected.

Runs in background: console window is hidden on Windows.
"""
import sys
import os
import threading
import time

from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _run_without_console_on_windows():
    """On Windows, re-launch with pythonw so no console window appears; then exit this process."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        # If we have a console (e.g. started as python main.py), re-exec with pythonw for a truly invisible run
        if ctypes.windll.kernel32.GetConsoleWindow():
            pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
            if os.path.isfile(pythonw):
                os.execv(pythonw, [pythonw] + sys.argv)
                return True
        # No console (already pythonw) or pythonw not found: try hiding console
        SW_HIDE = 0
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, SW_HIDE)
    except Exception:
        pass
    return False


# On Windows: re-launch with pythonw so no console window appears (execv replaces process)
_run_without_console_on_windows()

from config_loader import load_config
from overlay_window import OverlayWindow
from audio_recorder import record_until_stopped
from speech_to_text import transcribe
from llm_client import get_answer, get_exam_answer_from_image


def parse_hotkey(keys: list) -> tuple:
    """Parse config list e.g. ['alt','r'] into (modifier, key_char)."""
    if not keys or len(keys) < 2:
        return ("alt", "r")
    mod = (keys[0] or "alt").lower()
    key = (keys[1] or "r").lower()
    return (mod, key)


def main():
    config = load_config()
    overlay = OverlayWindow(config)
    mod_name, key_char = parse_hotkey(config.get("hotkey_record", ["alt", "r"]))
    clear_mod, clear_key_char = parse_hotkey(config.get("hotkey_clear", ["alt", "c"]))

    # Exam mode hotkeys (MCQ screenshot → answer); defaults: Alt+S to scan, Alt+A to show answer.
    exam_scan_mod, exam_scan_key = parse_hotkey(
        config.get("hotkey_exam_scan", ["alt", "s"])
    )
    exam_answer_mod, exam_answer_key = parse_hotkey(
        config.get("hotkey_exam_answer", ["alt", "a"])
    )
    
    # Code mode hotkey (default Alt+Q to scan code question). Alt+A also shows code.
    code_scan_mod, code_scan_key = parse_hotkey(
        config.get("hotkey_code_scan", ["alt", "q"])
    )
    
    # Amp mode hotkey (default Alt+W to scan aptitude question). Alt+A also shows amp answers.
    amp_scan_mod, amp_scan_key = parse_hotkey(
        config.get("hotkey_amp_scan", ["alt", "w"])
    )

    recording_stop = threading.Event()
    recording_thread = None
    wav_path_holder = [None]
    recording_active = [False]

    # Exam mode state
    exam_processing_active = [False]
    exam_answer_holder: list[Optional[str]] = [None]
    exam_showing_active = [False]
    current_scan_mode = ["exam"]

    try:
        from PIL import ImageGrab
    except Exception as e:  # pragma: no cover - only hit if Pillow missing
        ImageGrab = None  # type: ignore[assignment]
        print(f"[Main] Pillow (PIL) not available for exam mode screenshots: {e}", file=sys.stderr)

    def start_recording():
        nonlocal recording_thread
        if recording_thread is not None and recording_thread.is_alive():
            return
        recording_stop.clear()
        wav_path_holder[0] = None

        def run():
            path = record_until_stopped(recording_stop)
            wav_path_holder[0] = path

        recording_thread = threading.Thread(target=run, daemon=True)
        recording_thread.start()

    def schedule_set_text(text):
        if overlay.root:
            overlay.root.after(0, lambda t=text: overlay.set_text(t))

    def capture_screen_for_exam():
        """Capture the current screen as an image, briefly hiding the overlay to avoid capturing it."""
        if ImageGrab is None:
            raise RuntimeError(
                "Pillow (PIL) is not installed. Run 'pip install -r requirements.txt' to enable exam mode."
            )
        # Hide overlay so the screenshot only contains the exam question.
        overlay.hide()
        # Small delay so the window actually disappears before capture.
        time.sleep(0.12)
        try:
            img = ImageGrab.grab()
        finally:
            overlay.show()
        return img

    def stop_recording_and_process():
        nonlocal recording_thread
        recording_stop.set()
        if recording_thread is not None:
            recording_thread.join(timeout=5)
        path = wav_path_holder[0]
        if not path:
            return
        try:
            text = transcribe(path, config)
            if os.path.isfile(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
            if not text or not text.strip():
                schedule_set_text("[No speech detected or transcription failed.]")
                return
            answer = get_answer(text, config)
            schedule_set_text(answer)
        except Exception as e:
            print(f"[Main] Error: {e}", file=sys.stderr)
            schedule_set_text(f"[Error: {e}]")

    def process_exam_screenshot_async():
        """Background worker: capture screen image and ask Gemini for the MCQ answer."""
        try:
            schedule_set_text("[Exam] Capturing screen and sending to Gemini...")
            img = capture_screen_for_exam()
            from llm_client import get_exam_answer_from_image
            answer = get_exam_answer_from_image(img, config)
            exam_answer_holder[0] = answer
            current_scan_mode[0] = "exam"
            schedule_set_text(
                "[Exam] Answer ready. Hold Alt+A to show it.\n"
                "Tip: release Alt+A to hide the answer again."
            )
        except Exception as e:
            print(f"[Main] Exam mode error: {e}", file=sys.stderr)
            schedule_set_text(f"[Exam] Error while processing screenshot: {e}")
        finally:
            exam_processing_active[0] = False

    def process_code_screenshot_async():
        """Background worker: capture screen image and ask Gemini for C++ code answer."""
        try:
            schedule_set_text("[Code] Capturing screen and sending to Gemini...")
            img = capture_screen_for_exam()
            from llm_client import get_code_answer_from_image
            answer = get_code_answer_from_image(img, config)
            exam_answer_holder[0] = answer
            current_scan_mode[0] = "code"
            # Auto-copy to clipboard
            if overlay.root:
                overlay.root.clipboard_clear()
                overlay.root.clipboard_append(answer)
            schedule_set_text(
                "[Code] Code ready and copied to clipboard! Press Alt+A to show it.\n"
                "Tip: press Alt+C to clear the answer."
            )
        except Exception as e:
            print(f"[Main] Code mode error: {e}", file=sys.stderr)
            schedule_set_text(f"[Code] Error while processing screenshot: {e}")
        finally:
            exam_processing_active[0] = False

    def process_amp_screenshot_async():
        """Background worker: capture screen image and ask Gemini for Aptitude answer."""
        try:
            schedule_set_text("[Amp] Capturing screen and sending to Gemini...")
            img = capture_screen_for_exam()
            from llm_client import get_amp_answer_from_image
            answer = get_amp_answer_from_image(img, config)
            exam_answer_holder[0] = answer
            current_scan_mode[0] = "amp"
            schedule_set_text(
                "[Amp] Answer ready. Hold Alt+A to show it.\n"
                "Tip: release Alt+A to hide the answer again."
            )
        except Exception as e:
            print(f"[Main] Amp mode error: {e}", file=sys.stderr)
            schedule_set_text(f"[Amp] Error while processing screenshot: {e}")
        finally:
            exam_processing_active[0] = False

    from pynput import keyboard

    # Normalized key set: (char, name) for hashing. char for KeyCode, name for Key.
    def norm(key):
        c = getattr(key, "char", None)
        n = getattr(key, "name", None)
        return (c, n)

    pressed_keys = set()

    def is_mod_held(name):
        return any(
            n in (name, f"{name}_l", f"{name}_r") for c, n in pressed_keys if n
        )

    def is_char_held(char):
        return any(c == char for c, n in pressed_keys if c)

    def on_press(key):
        pressed_keys.add(norm(key))
        # Normal recording hotkey (hold-to-record)
        if mod_name and key_char:
            mod_ok = is_mod_held(mod_name)
            key_ok = is_char_held(key_char)
            if mod_ok and key_ok and not recording_active[0]:
                recording_active[0] = True
                start_recording()

        # Clear overlay
        if (
            clear_mod
            and clear_key_char
            and is_mod_held(clear_mod)
            and is_char_held(clear_key_char)
        ):
            exam_showing_active[0] = False
            if overlay.root:
                overlay.root.after(0, overlay.clear)

        # Exam mode: Alt+S (by default) to capture MCQ screenshot and ask Gemini
        if exam_scan_mod and exam_scan_key:
            if (
                is_mod_held(exam_scan_mod)
                and is_char_held(exam_scan_key)
                and not exam_processing_active[0]
            ):
                exam_processing_active[0] = True
                exam_answer_holder[0] = None

                t = threading.Thread(target=process_exam_screenshot_async, daemon=True)
                t.start()
                
        # Code mode: Alt+Q (by default) to capture code screenshot
        if code_scan_mod and code_scan_key:
            if (
                is_mod_held(code_scan_mod)
                and is_char_held(code_scan_key)
                and not exam_processing_active[0]
            ):
                exam_processing_active[0] = True
                exam_answer_holder[0] = None

                t = threading.Thread(target=process_code_screenshot_async, daemon=True)
                t.start()
                
        # Amp mode: Alt+W (by default) to capture amplitude screenshot
        if amp_scan_mod and amp_scan_key:
            if (
                is_mod_held(amp_scan_mod)
                and is_char_held(amp_scan_key)
                and not exam_processing_active[0]
            ):
                exam_processing_active[0] = True
                exam_answer_holder[0] = None

                t = threading.Thread(target=process_amp_screenshot_async, daemon=True)
                t.start()

        # Exam mode: hold Alt+A (by default) to show the stored answer text
        if exam_answer_mod and exam_answer_key:
            if (
                is_mod_held(exam_answer_mod)
                and is_char_held(exam_answer_key)
                and not exam_showing_active[0]
            ):
                # Only show if we actually have an answer already.
                if exam_answer_holder[0]:
                    exam_showing_active[0] = True
                    schedule_set_text(exam_answer_holder[0])

    def on_release(key):
        pressed_keys.discard(norm(key))
        if recording_active[0] and mod_name and key_char:
            if not is_mod_held(mod_name) or not is_char_held(key_char):
                recording_active[0] = False
                stop_recording_and_process()

        # When exam answer hotkey is released, hide the answer again
        if exam_showing_active[0] and exam_answer_mod and exam_answer_key:
            if not is_mod_held(exam_answer_mod) or not is_char_held(exam_answer_key):
                if current_scan_mode[0] != "code":
                    exam_showing_active[0] = False
                    if overlay.root:
                        overlay.root.after(0, overlay.clear)

    overlay.show()
    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.daemon = True
    listener.start()

    try:
        overlay.run()
    finally:
        listener.stop()


if __name__ == "__main__":
    main()
