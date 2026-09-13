"""
Quick mic calibration -- prints a live noise level so we can pick a real
SILENCE_THRESHOLD for wake_loop.py instead of guessing.

Run this, stay completely quiet for ~5 seconds to see the room's baseline
level, then talk normally for a few seconds to see what your voice looks
like. Ctrl+C to stop. Report back roughly what the "quiet" numbers looked
like vs. the "talking" numbers.
"""

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 44100
FRAME_MS = 80
FRAME_SAMPLES = int(SAMPLE_RATE * FRAME_MS / 1000)


def callback(indata, frames, time_info, status):
    level = int(np.abs(indata).mean())
    print(level)


print("Printing mic level every 80ms.")
print("Stay quiet for ~5 seconds first, then talk normally. Ctrl+C to stop.\n")

with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16",
                     blocksize=FRAME_SAMPLES, callback=callback):
    while True:
        sd.sleep(1000)
