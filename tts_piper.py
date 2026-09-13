"""
Thin wrapper around Piper so the rest of the code doesn't care whether TTS
is a subprocess call, a different binary, or a different engine entirely --
see the README for a note on Piper's maintenance status.

Assumes the `piper` binary and a voice model (.onnx) are already installed;
adjust the two paths below to match your setup.
"""

import os
import shutil
import subprocess
import tempfile

PIPER_BIN = shutil.which("piper") or os.path.expanduser("~/piper/piper")
VOICE_MODEL = os.path.expanduser("~/piper/voices/en_US-amy-medium.onnx")
from functions import SPEAKER_SINK


def speak(text: str):
    if not text:
        return

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav_path = tmp.name

    try:
        subprocess.run(
            [PIPER_BIN, "--model", VOICE_MODEL, "--output_file", wav_path],
            input=text.encode("utf-8"),
        )
        subprocess.run(["paplay", f"--device={SPEAKER_SINK}", wav_path])
    finally:
        os.remove(wav_path)
