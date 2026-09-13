"""
ElevenLabs text-to-speech -- noticeably higher quality than Piper, but
needs internet and an API key. Not meant to be used directly; tts.py picks
between this and Piper automatically.
"""

import os
import subprocess

import requests

API_KEY = os.environ.get("ELEVENLABS_API_KEY")
VOICE_ID = "EXAVITQu4vr4xnSDxMaL"   # "Sarah" -- premade voice, confirmed
                                     # free-tier eligible on your account.
                                     # Other premade options (also free):
                                     # Roger, Laura, Charlie, George, River,
                                     # Alice, Matilda, Jessica, Brian, Adam
MODEL_ID = "eleven_flash_v2_5"       # optimized for low latency, which matters
                                      # for a live conversation. Swap for
                                      # "eleven_multilingual_v2" instead if you
                                      # want the highest quality and don't mind
                                      # a slightly slower reply
OUTPUT_FORMAT = "pcm_22050"          # raw PCM so this can pipe straight to
                                      # paplay, same as the Piper path -- no
                                      # mp3 decoding needed
from functions import SPEAKER_SINK


def speak_elevenlabs(text: str):
    if not API_KEY:
        raise RuntimeError("ELEVENLABS_API_KEY not set")

    response = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}",
        params={"output_format": OUTPUT_FORMAT},
        headers={"xi-api-key": API_KEY, "Content-Type": "application/json"},
        json={"text": text, "model_id": MODEL_ID},
        timeout=15,
    )
    if response.status_code != 200:
        raise RuntimeError(f"ElevenLabs {response.status_code}: {response.text}")

    subprocess.run(
        ["paplay", f"--device={SPEAKER_SINK}", "--raw",
         "--rate=22050", "--format=s16le", "--channels=1"],
        input=response.content,
    )
