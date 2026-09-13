# AI Desk Assistant — Raspberry Pi 5

A self-contained, always-on AI desk assistant built on a Raspberry Pi 5 — voice interaction, a touchscreen UI, and presence-aware display dimming. Built as a portfolio project combining embedded software, ML pipeline integration, and hardware bring-up.

> Portfolio note: everything below under **Features** is implemented and working. Planned/in-progress work is listed separately under **Roadmap** — nothing there is claimed as finished.

<!-- Add a photo or short demo GIF of the assembled device here -->

## Features

### Voice pipeline
- Wake word detection via **openWakeWord** (`hey_jarvis`)
- Speech-to-text via **Whisper**
- Multi-step function calling via **GPT-4o** for reasoning and tool use
- Text-to-speech via **ElevenLabs** (primary) with **Piper** as an offline fallback
- Calibrated mic silence threshold and a hard 15-second recording ceiling to keep listening reliable
- Audio routed through **PipeWire** (`paplay`) for compatibility with exclusive-access audio devices

### Touchscreen UI
- Built with **PySide6/QML** on a 7" DSI touchscreen (800×480)
- Ambient home screen cycling nature photos with crossfade transitions and a custom-positioned clock
- App grid with tap-to-reveal and automatic idle return
- Functional screens: analog clock, weather, alarm, and settings (volume/brightness)
- Live voice-activity indicator driven by a polled state file

### Presence detection
- **Raspberry Pi AI Camera (IMX500)** running an on-sensor MobileNet SSD model
- Automatically adjusts screen backlight based on whether someone is present, with a timeout on absence

### System architecture
- A single source-of-truth module centralizes all Pi-level hardware control (volume, brightness) so every other module reads from one place instead of duplicating hardware logic
- Hybrid local/cloud design: cloud APIs for STT/reasoning/TTS, on-device inference for wake word and presence detection

## Hardware

| Component | Notes |
|---|---|
| Raspberry Pi 5 | Main compute |
| Official Pi 5 active cooler | Thermal management |
| 7" DSI touchscreen (800×480) | Primary display |
| Raspberry Pi AI Camera (IMX500) | On-sensor person detection |
| USB speaker | Wired audio output (USB chosen over Bluetooth for reliability — see notes below) |
| USB microphone array | Wired audio input |

## Software stack

- Python 3
- PySide6 / QML
- openWakeWord
- OpenAI Whisper + GPT-4o (API)
- ElevenLabs TTS API
- Piper (offline TTS fallback)
- picamera2
- PipeWire / WirePlumber

## Repository structure

```
.
├── functions.py         # single source of truth for Pi-level hardware control
├── wake_loop.py         # voice pipeline entry point
├── tts.py
├── tts_piper.py
├── tts_elevenlabs.py
├── presence_loop.py     # presence detection / backlight control
├── main.qml             # touchscreen UI (QML layout)
├── ui_main.py            # touchscreen UI entry point — loads main.qml, bridges Python↔QML
├── calibrate_mic.py     # run once per microphone to set the silence threshold
├── capture_photos.py    # utility to capture reference photo sets (e.g. for future face/gesture recognition work) — not required for the core assistant to run
├── coco_labels.txt      # COCO class labels used by presence_loop.py's on-sensor detection model to identify "person"
├── requirements.txt
└── .gitignore
```

## Setup

> Built and tested on **Python 3.13**.

### 1. Clone and create a virtual environment

```bash
git clone https://github.com/djordjenboskovic/pi-desk-assistant.git
cd pi-desk-assistant
python3 -m venv venv --system-site-packages   # --system-site-packages needed for picamera2 access
source venv/bin/activate
pip install -r requirements.txt
```

`picamera2` and `PySide6` are installed via `--system-site-packages` from the OS rather than pinned in `requirements.txt` — on a stock Raspberry Pi OS install they should already be present system-wide.

### 2. Configure API keys

This project reads credentials from environment variables — no `.env` file needed. Add these to your `~/.bashrc` (or `~/.profile`) and reload your shell:

```bash
export OPENAI_API_KEY="your-key-here"
export ELEVENLABS_API_KEY="your-key-here"
```

```bash
source ~/.bashrc
```

If you later run this as a systemd service for headless boot, use an `EnvironmentFile=` directive instead of relying on `.bashrc` (systemd services don't source shell profiles).

### 3. Display configuration

Built and tested on Raspberry Pi OS (Debian 13 "trixie"). The 7" DSI display requires the following in `/boot/firmware/config.txt` under `[all]`:

```
dtoverlay=vc4-kms-dsi-7inch
```

This overlay conflicts with `display_auto_detect=1` — use one or the other, not both. Confirm SSH access is working *before* rebooting with a new display config, in case of display issues.

(On Raspberry Pi OS releases older than "Bookworm," this file is at `/boot/config.txt` instead of `/boot/firmware/config.txt`.)

### 4. Audio

All audio output must go through PipeWire (`paplay`), not raw ALSA — PipeWire holds exclusive access to the device and `aplay` calls will fail. If using a USB audio device, place it on a USB 2.0 (black) port rather than USB 3.0 (blue) to reduce interference with the 2.4GHz WiFi/Bluetooth radio.

### 5. Run

This is three separate, always-running processes, not one combined app — open three terminals (e.g. three SSH sessions, or a terminal multiplexer like `tmux`) and run one in each:

```bash
# Terminal 1 — voice pipeline
python wake_loop.py

# Terminal 2 — presence detection / backlight
python presence_loop.py

# Terminal 3 — touchscreen UI
python ui_main.py
```

*(For headless, always-on use, each of these would eventually become its own systemd service rather than a manually-run terminal — not yet set up here.)*

## Hardware-specific settings to check

This project was built and tuned against one specific set of hardware. If you're running it on different components, expect to adjust:

- **Audio sink name** — `SPEAKER_SINK` in `functions.py` is hardcoded to this project's USB speaker. Find your own sink name with `pactl list sinks short` and update the constant.
- **Sample rate** — the mic/speaker sample rate assumed in `wake_loop.py` and `tts.py` matches this project's specific USB mic and speaker. A different mic or speaker may support a different rate; check yours with `pactl list sources` / `arecord -l` and adjust if audio sounds distorted or fails to open.
- **Mic silence threshold** — the value used to detect when someone's stopped talking (currently tuned to `400`) is specific to this microphone's noise floor. Re-run `calibrate_mic.py` with your own mic before relying on it.
- **Backlight sysfs path** — brightness control points at a specific path (`/sys/class/backlight/.../brightness`) tied to this DSI display's driver. A different display exposes backlight control at a different path; check `ls /sys/class/backlight/` on your Pi and update `functions.py`. (No special permissions setup needed on stock Raspberry Pi OS — the file is owned by `root:video`, and the default user is already in the `video` group, so no `sudo` or udev rule is required.)
- **Camera model** — `presence_loop.py` is written specifically for the Raspberry Pi AI Camera (IMX500) and its on-sensor inference. A standard Pi Camera Module or USB webcam will not work without rewriting the detection logic. (No special permission setup needed here either — the only requirement is the `--system-site-packages` venv flag from Setup, since `picamera2` is a system `apt` package rather than a `pip` one.)
- **Display overlay** — the `dtoverlay=vc4-kms-dsi-7inch` line in `config.txt` is specific to this 7" display model; a different screen needs a different overlay.
- **openWakeWord version** — wake word model files ship bundled inside `openwakeword` 0.4.0 (what this project uses), so no separate download step is needed on that version. Other versions of the library may require running a one-time model download instead — worth checking if you install a different version.

## Known limitations

Things to be aware of if you're setting this up fresh rather than just reading the code:

- **Three processes need to run for the full experience** — the voice pipeline (`wake_loop.py`), presence detection (`presence_loop.py`), and the touchscreen UI (`main.qml`) are separate processes, not one combined app. There's currently no single launcher or systemd setup that starts all three together.
- **Some assets aren't included** — the ambient home-screen wallpapers, the alarm sound file, and the offline Piper voice model files were intentionally left out (privacy/licensing reasons for the images and audio, file size for the Piper models). Code paths that reference them will fail until you supply your own.
- **Hardware assumptions throughout** — see the section above. Running this on anything other than the exact mic, speaker, display, and camera used here will likely require some debugging, not just a config change.
- **API keys must be set before first run** — both `wake_loop.py` and `tts_elevenlabs.py` will raise an error immediately if `OPENAI_API_KEY` / `ELEVENLABS_API_KEY` aren't set in the environment.
- **Requires a live internet connection** — Whisper, GPT-4o, and ElevenLabs are all cloud API calls. Without internet, voice interaction won't work (though Piper's offline fallback can still handle TTS).

## Roadmap

- Local intent classifier for command routing (reduce reliance on cloud API calls)
- Local STT via `faster-whisper` to cut Whisper API costs
- Semantic caching using sentence-transformer embeddings
- Confidence-gated local LLM fallback
- Optional BME280 environmental sensor (temperature/humidity/pressure)

## Lessons learned

- **PipeWire owns audio** — raw ALSA device access breaks once PipeWire has claimed the device
- **USB audio placement matters** — USB 2.0 ports reduce 2.4GHz interference with WiFi/Bluetooth
- **Bluetooth wasn't reliable for this use case** — the Pi 5 shares WiFi/BT on one radio, and headless A2DP reconnect proved fragile; wired USB audio was the more dependable choice
- **Bare speaker drivers need an amplifier board** — GPIO pins can't drive a speaker directly; USB-powered speakers sidestep this
- **DSI display config is particular** — the DSI overlay and auto-detect settings conflict, and it's worth confirming SSH works before rebooting into a new display config

## License

MIT — see `LICENSE`.

## Author

Djordje — mechanical engineering student, Penn State (expected May 2028).
