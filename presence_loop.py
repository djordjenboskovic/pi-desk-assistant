"""
Presence-based screen brightness. Runs as its own background process
(same pattern as wake_loop.py for voice) -- watches for a person using the
AI Camera's on-sensor MobileNet SSD model, brightens the screen when
someone's around, and dims it after a stretch of nobody being detected.

Deliberately headless (no preview window) -- this runs silently in the
background, it doesn't need to show you anything.

Setup:
    sudo apt install imx500-all   (if you haven't already, from earlier)
    Run this alongside wake_loop.py and ui_main.py in its own terminal.

Run:
    python presence_loop.py
"""

import time

from picamera2 import Picamera2
from picamera2.devices import IMX500
from picamera2.devices.imx500 import NetworkIntrinsics, postprocess_nanodet_detection

from functions import set_brightness

MODEL_PATH = "/usr/share/imx500-models/imx500_network_ssd_mobilenetv2_fpnlite_320x320_pp.rpk"
CONFIDENCE_THRESHOLD = 0.55
DIM_AFTER_SECONDS = 10   # how long nobody has to be absent before dimming
BRIGHT_PERCENT = 50      # brightness while someone's present
DIM_PERCENT = 0          # maps to the floor we already set up (~10% actual,
                         # never fully off) -- same scale as the Settings slider

# Must happen before Picamera2 is instantiated
imx500 = IMX500(MODEL_PATH)
intrinsics = imx500.network_intrinsics
if not intrinsics:
    intrinsics = NetworkIntrinsics()
    intrinsics.task = "object detection"

if intrinsics.labels is None:
    with open("coco_labels.txt") as f:
        intrinsics.labels = f.read().splitlines()
intrinsics.update_with_defaults()

labels = intrinsics.labels

picam2 = Picamera2(imx500.camera_num)
config = picam2.create_preview_configuration(
    controls={"FrameRate": intrinsics.inference_rate}, buffer_count=12,
)
imx500.show_network_fw_progress_bar()
picam2.start(config, show_preview=False)  # headless -- no GUI window


def person_in_frame(metadata) -> bool:
    """Returns True if a person is detected in this frame above threshold.
    Only checks scores/classes -- we don't need box coordinates since we're
    not drawing anything, just answering "is someone there?"."""
    np_outputs = imx500.get_outputs(metadata, add_batch=True)
    if np_outputs is None:
        return False

    if intrinsics.postprocess == "nanodet":
        _, scores, classes = postprocess_nanodet_detection(
            outputs=np_outputs[0], conf=CONFIDENCE_THRESHOLD, iou_thres=0.65, max_out_dets=10,
        )[0]
    else:
        _, scores, classes = np_outputs[0][0], np_outputs[1][0], np_outputs[2][0]

    for score, category in zip(scores, classes):
        if score > CONFIDENCE_THRESHOLD and labels[int(category)] == "person":
            return True
    return False


def main():
    print("Watching for presence... (Ctrl+C to stop)")
    last_seen_person = None
    is_bright = None  # None forces the first real state to actually apply

    while True:
        metadata = picam2.capture_metadata()
        seen_now = person_in_frame(metadata)

        now = time.monotonic()
        if seen_now:
            last_seen_person = now

        # Tracking "time since last seen" (not resetting the instant one
        # frame misses) means a single dropped frame can't falsely trigger
        # dimming -- as long as a person is redetected at least once within
        # the window, the countdown never actually completes.
        should_be_bright = (
            last_seen_person is not None and (now - last_seen_person) < DIM_AFTER_SECONDS
        )

        if should_be_bright != is_bright:
            is_bright = should_be_bright
            if is_bright:
                print("Person detected -- brightening")
                set_brightness(BRIGHT_PERCENT)
            else:
                print("No one around for a while -- dimming")
                set_brightness(DIM_PERCENT)


if __name__ == "__main__":
    main()
