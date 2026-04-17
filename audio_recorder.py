"""Record audio from microphone while hotkey is held. Export to WAV for STT."""
import io
import os
import sys
import tempfile
import threading
import wave

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = np.int16


def record_until_stopped(stop_event: threading.Event) -> str | None:
    """
    Record from default input until stop_event is set.
    Returns path to a temporary WAV file, or None if recording was empty/short.
    """
    chunks = []
    err_msg = [None]  # mutable to capture in callback

    def callback(indata, frames, time_info, status):
        if status:
            err_msg[0] = str(status)
        chunks.append(indata.copy())

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype=DTYPE,
        callback=callback,
        blocksize=1024,
    )
    stream.start()
    if err_msg[0]:
        print(f"[Audio] {err_msg[0]}", file=sys.stderr)
    stop_event.wait()
    stream.stop()
    stream.close()

    if not chunks:
        return None
    audio = np.concatenate(chunks, axis=0)
    return _write_wav(audio, SAMPLE_RATE)


def _write_wav(samples: np.ndarray, sample_rate: int) -> str:
    """Write numpy int16 mono to a temp WAV file. Returns path."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(CHANNELS)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(samples.tobytes())
    buf.seek(0)
    fd, path = tempfile.mkstemp(suffix=".wav")
    try:
        os.write(fd, buf.read())
    finally:
        os.close(fd)
    return path
