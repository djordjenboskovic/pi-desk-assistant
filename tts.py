"""
Unified speak() for the assistant. Tries ElevenLabs (better quality) when
you're online and ELEVENLABS_API_KEY is set; otherwise, or if the API call
fails for any reason, falls back to Piper (local, always works, no
internet needed) -- matching the hybrid online/offline design.
"""

import os
import socket

from tts_elevenlabs import speak_elevenlabs
from tts_piper import speak as speak_piper

ELEVENLABS_CONFIGURED = bool(os.environ.get("ELEVENLABS_API_KEY"))


def has_internet(timeout=1.5) -> bool:
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
        return True
    except OSError:
        return False


def speak(text: str):
    if not text:
        return

    # This speaker's hardware clips the very start of any sound, confirmed
    # even with a bare system sound file completely outside our code -- a
    # software-level fix isn't possible. Prefixing a disposable word means
    # whatever gets clipped is never the actual content of the reply.
    text = "E, " + text

    if ELEVENLABS_CONFIGURED and has_internet():
        try:
            speak_elevenlabs(text)
            return
        except Exception as e:
            print(f"(ElevenLabs failed, falling back to local voice -- {e})")

    speak_piper(text)
