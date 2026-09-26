"""Opt-in, local push-to-talk speech. No recording is saved by Bella."""
from __future__ import annotations


def listen(*, model_size="base", input_fn=input, whisper_model=None):
    """Press Enter to start, Enter to stop. Model downloads may occur on first use."""
    try:
        import numpy as np
        import sounddevice as sd
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("Install optional voice dependencies: pip install -r requirements-voice.txt") from exc
    input_fn("Press Enter to start recording (Ctrl+C to cancel). ")
    chunks = []
    def on_audio(indata, frames, time_info, status):
        chunks.append(indata.copy())
    try:
        with sd.InputStream(samplerate=16000, channels=1, dtype="float32", callback=on_audio):
            input_fn("Recording. Press Enter to stop. ")
    except Exception as exc:
        raise RuntimeError("Microphone unavailable; check Windows microphone permission and input device") from exc
    if not chunks:
        raise RuntimeError("No microphone audio captured")
    samples = np.concatenate(chunks, axis=0).reshape(-1)
    if len(samples) < 8000:
        raise RuntimeError("Recording too short; try again")
    if whisper_model is None:
        try:
            whisper_model = WhisperModel(model_size, device="cuda", compute_type="float16")
        except Exception:
            print("GPU speech model unavailable; falling back to CPU.")
            whisper_model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, _ = whisper_model.transcribe(samples, vad_filter=True)
    result = " ".join(segment.text.strip() for segment in segments).strip()
    if not result:
        raise RuntimeError("No speech recognized")
    return result


def say(text):
    try:
        import pyttsx3
    except ImportError as exc:
        raise RuntimeError("Install optional voice dependencies: pip install -r requirements-voice.txt") from exc
    engine = pyttsx3.init()
    engine.say(text[:2000])
    engine.runAndWait()
