"""
Fully hands-free conversation loop.

    listen for wake word -> record until you stop talking -> GPT -> speak
        -> listen for a follow-up (timeout) -> keep going, or give up and
           go back to listening for the wake word

Now with real function calling: it can look up the current time anywhere
in the world (see functions.py). Weather/alarms come later, same pattern.

Setup (one-time):
    pip install openwakeword scipy
    (openai, sounddevice, numpy should already be installed from talk_test.py)

Run:
    python wake_loop.py
"""

import io
import json
import os
import queue
import subprocess
import time
import wave
from collections import deque

import numpy as np
import sounddevice as sd
from openai import OpenAI
from openwakeword.model import Model as WakeWordModel
from scipy.signal import resample_poly

from functions import (
    FUNCTION_SCHEMAS, call_function, pop_due_alarm, snooze, SPEAKER_SINK,
)
from tts import speak

# ---------------------------------------------------------------- config ---
CAPTURE_RATE = 44100          # your mic's native rate
WAKE_RATE = 16000             # what openWakeWord needs
FRAME_MS = 80
CAPTURE_FRAME = int(CAPTURE_RATE * FRAME_MS / 1000)   # samples per chunk we read

WAKE_WORD = "hey_jarvis"      # ships with openWakeWord; swap for a custom
                               # one later if you want your own phrase

SILENCE_THRESHOLD = 400       # measured: quiet room tops out ~330-355,
                               # talking peaks 700-1100 with dips to 300-600
SILENCE_HANG_MS = 1100        # pause length that means "done talking"
FOLLOWUP_TIMEOUT_MS = 5000    # how long to wait for a follow-up before
                               # giving up and going back to the wake word
MIN_SPEECH_FRAMES = 4         # need at least ~320ms of real above-threshold
                               # audio before bothering to transcribe --
                               # protects against sending near-silence to
                               # Whisper, which then hallucinates captions
                               # like "Thank you for watching" instead of
                               # failing outright
WAKE_CONSECUTIVE_FRAMES = 2   # require the wake word score to stay high for
                               # 2 frames in a row, not just 1 -- the reset()
                               # calls below handle the false-positive cases,
                               # so this can stay lenient enough to catch real attempts
MAX_RECORDING_MS = 15000      # hard ceiling -- guarantees we never hang
                               # forever even if noise never fully drops
                               # below the silence threshold
WAKE_RESPONSE_TIMEOUT_MS = 10000  # how long to wait for you to start talking
                               # right after the wake word, before giving up
QUEUE_GET_TIMEOUT_S = 0.5     # how often we check elapsed time, instead of
                               # assuming audio chunks always keep arriving
PRE_BUFFER_FRAMES = 3          # ~240ms of lead-in audio kept at all times, so a
                               # soft word onset (before it's loud enough to
                               # cross the threshold) doesn't get lost
COOLDOWN_FRAMES = 10           # ~800ms grace period after resetting the wake
                               # model -- its freshly-cleared internal buffer
                               # needs a moment to refill with real context
                               # before its scores can be trusted again
ALARM_MUSIC_PATH = os.path.expanduser("~/alarm_music.wav")  # put your alarm sound here
ALARM_PLAY_SECONDS = 12        # how long to play before pausing to listen for you
VOICE_STATE_PATH = "/tmp/assistant_state.txt"

client = OpenAI()
oww = WakeWordModel()  # loads all bundled pretrained models; we just read
                        # the one score we care about (WAKE_WORD) from the
                        # dict predict() returns. Avoids a parameter-name
                        # mismatch between openwakeword versions.


def set_conversation_state(state: str):
    """Lets the touchscreen know whether we're in a conversation right now.
    Written to a plain shared file since wake_loop.py and the touchscreen
    app are two separate processes with no other connection between them --
    the touchscreen just polls this file a few times a second."""
    try:
        with open(VOICE_STATE_PATH, "w") as f:
            f.write(state)
    except Exception:
        pass  # touchscreen app might not be running -- not a real problem

conversation = [
    {"role": "system", "content": (
        "You are a helpful desk assistant running on a Raspberry Pi. You "
        "have real tools available (like checking the current time anywhere "
        "in the world) -- when a tool can answer the question, use it "
        "instead of saying you don't have real-time access. Keep replies "
        "short and conversational."
    )},
]

audio_q = queue.Queue()


def _callback(indata, frames, time_info, status):
    audio_q.put(indata.copy())


def to_wake_rate(chunk: np.ndarray) -> np.ndarray:
    """Downsamples a 44100Hz chunk to 16000Hz for the wake-word model."""
    resampled = resample_poly(chunk.flatten(), WAKE_RATE, CAPTURE_RATE)
    return resampled.astype(np.int16)


def drain_queue():
    """Throws away whatever audio piled up while Amy was talking -- a rough
    fix for the mic possibly picking up her own voice through the speaker."""
    while not audio_q.empty():
        try:
            audio_q.get_nowait()
        except queue.Empty:
            break


def record_until_silence(max_initial_wait_ms=None):
    """Collects audio until a pause is detected. If max_initial_wait_ms is
    set and nobody starts talking in time, returns None (used for the
    follow-up step, so we know when to give up and stop listening).

    Uses wall-clock time and a timed queue read (not just "count how many
    chunks arrived") so this can never hang forever, even if the mic stream
    itself stalls and stops delivering audio."""
    frames = []
    pre_buffer = deque(maxlen=PRE_BUFFER_FRAMES)
    speech_frames = 0
    started_talking = False
    last_speech_at = None
    start_time = time.monotonic()

    while True:
        try:
            chunk = audio_q.get(timeout=QUEUE_GET_TIMEOUT_S)
        except queue.Empty:
            chunk = None

        now = time.monotonic()

        if chunk is not None:
            level = np.abs(chunk).mean()

            if not started_talking:
                pre_buffer.append(chunk)

            if level > SILENCE_THRESHOLD:
                if not started_talking:
                    # just crossed the threshold -- pull in the recent lead-in
                    # audio too, so a soft onset isn't lost (drop the last
                    # entry since that's this same chunk, added again below)
                    frames.extend(list(pre_buffer)[:-1])
                started_talking = True
                speech_frames += 1
                last_speech_at = now

            if started_talking:
                frames.append(chunk)

        if started_talking:
            silence_ms = (now - last_speech_at) * 1000
            recording_ms = (now - start_time) * 1000
            if (silence_ms >= SILENCE_HANG_MS and len(frames) > 5) or recording_ms >= MAX_RECORDING_MS:
                if speech_frames < MIN_SPEECH_FRAMES:
                    return None  # too short/quiet to be real speech -- treat as nothing said
                return np.concatenate(frames, axis=0)
        else:
            waited_ms = (now - start_time) * 1000
            effective_timeout = max_initial_wait_ms if max_initial_wait_ms is not None else WAKE_RESPONSE_TIMEOUT_MS
            if waited_ms >= effective_timeout:
                return None


def transcribe(audio: np.ndarray) -> str:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(CAPTURE_RATE)
        wf.writeframes(audio.tobytes())
    buf.seek(0)
    buf.name = "utterance.wav"
    return client.audio.transcriptions.create(model="whisper-1", file=buf).text


def ask_gpt(user_text: str) -> str:
    conversation.append({"role": "user", "content": user_text})

    for _ in range(5):  # safety cap -- normal cases resolve in 1-2 rounds
        response = client.chat.completions.create(
            model="gpt-4o", messages=conversation, tools=FUNCTION_SCHEMAS,
        )
        msg = response.choices[0].message

        if not msg.tool_calls:
            reply = msg.content
            conversation.append({"role": "assistant", "content": reply})
            return reply

        conversation.append(msg)
        for call in msg.tool_calls:
            args = json.loads(call.function.arguments)
            result = call_function(call.function.name, args)
            conversation.append({
                "role": "tool", "tool_call_id": call.id, "content": str(result),
            })
        # loop again -- GPT may want another tool call (e.g. get_volume then
        # set_volume) before it's ready to actually reply in text

    reply = "Sorry, I'm having trouble with that request."
    conversation.append({"role": "assistant", "content": reply})
    return reply


def speak_and_resume(stream, text):
    """Pauses mic capture while speaking, then resumes it -- avoids Amy's
    own voice being picked up as an accidental interruption or wake trigger."""
    stream.stop()
    speak(text)
    stream.start()


def play_alarm_music(stream):
    """Loops the alarm sound for a capped duration, mic paused during
    playback -- same reasoning as speak_and_resume, just for a sound clip
    instead of speech. Looping (rather than playing once) matters here
    since a short sound effect would otherwise leave most of the window silent."""
    stream.stop()
    subprocess.run([
        "timeout", str(ALARM_PLAY_SECONDS),
        "bash", "-c",
        f'while true; do paplay --device={SPEAKER_SINK} {ALARM_MUSIC_PATH}; done',
    ])
    stream.start()


def handle_ringing_alarm(stream):
    """Called when an alarm is due. Each cycle: play the alarm sound, then
    speak the voice prompt, then listen for 'stop' or 'snooze' --
    deliberately no wake word needed here, since you shouldn't have to say
    'hey jarvis' half-asleep just to silence an alarm."""
    while True:
        play_alarm_music(stream)
        drain_queue()

        speak_and_resume(stream, "Time to wake up. Say stop to turn off the alarm, or snooze to snooze it.")
        drain_queue()

        response = record_until_silence(max_initial_wait_ms=6000)
        if response is None:
            continue  # heard nothing -- keep going

        text = transcribe(response).lower()
        print(f"(alarm) heard: {text}")

        if "snooze" in text:
            print(snooze())
            return
        if any(word in text for word in ("stop", "turn off", "cancel", "off")):
            print("Alarm turned off.")
            return
        # heard something else -- keep going and try again


MIC_NAME_HINT = "USB PnP"  # matches the actual dedicated microphone specifically --
                           # without this, plugging in any new USB audio device
                           # (like a speaker with a built-in mic) can silently
                           # become the new "default" input and hijack capture


def find_mic_device():
    for idx, dev in enumerate(sd.query_devices()):
        if MIC_NAME_HINT in dev["name"] and dev["max_input_channels"] > 0:
            print(f"Using mic: {dev['name']} (device {idx})")
            return idx
    print(f"No device matching '{MIC_NAME_HINT}' found -- falling back to system default input.")
    return None


def main_loop():
    print("Listening for the wake word... (Ctrl+C to stop)")
    set_conversation_state("IDLE")
    consecutive_wake_frames = 0
    cooldown_remaining = 0

    mic_device = find_mic_device()
    stream = sd.InputStream(samplerate=CAPTURE_RATE, channels=1, dtype="int16",
                             blocksize=CAPTURE_FRAME, callback=_callback,
                             device=mic_device)
    stream.start()

    try:
        while True:
            try:
                chunk = audio_q.get(timeout=QUEUE_GET_TIMEOUT_S)
            except queue.Empty:
                chunk = None

            # If wake-word processing has fallen behind real-time audio
            # arrival, skip ahead to the most recent chunk instead of slowly
            # grinding through a growing backlog -- keeps both wake-word
            # detection and the alarm check tied to the actual current time.
            if audio_q.qsize() > 5:
                while audio_q.qsize() > 1:
                    try:
                        chunk = audio_q.get_nowait()
                    except queue.Empty:
                        break

            if pop_due_alarm() is not None:
                handle_ringing_alarm(stream)
                oww.reset()  # clear internal state -- all that ringing/response
                             # audio could otherwise confuse the next wake-word check
                cooldown_remaining = COOLDOWN_FRAMES
                continue

            if chunk is None:
                continue

            prediction = oww.predict(to_wake_rate(chunk))
            if prediction[WAKE_WORD] > 0.1:
                print(f"[debug] wake score: {prediction[WAKE_WORD]:.3f}")

            if cooldown_remaining > 0:
                cooldown_remaining -= 1
                continue  # let the model's buffer refill before trusting its score

            if prediction[WAKE_WORD] > 0.5:
                consecutive_wake_frames += 1
            else:
                consecutive_wake_frames = 0

            if consecutive_wake_frames >= WAKE_CONSECUTIVE_FRAMES:
                consecutive_wake_frames = 0
                oww.reset()  # clear the model's internal audio memory so the
                             # phrase we just heard can't immediately re-trigger it
                cooldown_remaining = COOLDOWN_FRAMES
                set_conversation_state("CONVERSING")
                drain_queue()  # ignore any audio queued up right at trigger time
                speak_and_resume(stream, "Yeah?")
                drain_queue()  # ignore Amy's own "Yeah?" coming back through the mic

                audio = record_until_silence()
                if audio is None:
                    print("Didn't catch real speech -- listening for wake word again.\n")
                    set_conversation_state("IDLE")
                    continue

                text = transcribe(audio)
                print(f"You said: {text}")
                reply = ask_gpt(text)
                print(f"Assistant: {reply}")
                speak_and_resume(stream, reply)
                drain_queue()

                # Keep the conversation going without needing the wake word again
                while True:
                    if pop_due_alarm() is not None:
                        handle_ringing_alarm(stream)
                        oww.reset()  # clear internal state before continuing the conversation
                        continue

                    followup = record_until_silence(max_initial_wait_ms=FOLLOWUP_TIMEOUT_MS)
                    if followup is None:
                        print("No response -- conversation ended, listening for wake word again.\n")
                        oww.reset()  # clear internal state before resuming idle listening
                        cooldown_remaining = COOLDOWN_FRAMES
                        set_conversation_state("IDLE")
                        break

                    text = transcribe(followup)
                    print(f"You said: {text}")
                    reply = ask_gpt(text)
                    print(f"Assistant: {reply}")
                    speak_and_resume(stream, reply)
                    drain_queue()
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        stream.abort()  # stop immediately, don't wait for buffers to drain
        stream.close()


if __name__ == "__main__":
    main_loop()
