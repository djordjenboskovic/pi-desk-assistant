"""
Simple capture tool -- takes a burst of photos and saves them to a named
folder. Useful for both face enrollment (a handful of photos of you, from
different angles/expressions) and later, gesture training data (many
photos of you doing/not doing the thumbs-up).

Run:
    python capture_photos.py --name my_face --count 10
    python capture_photos.py --name thumbs_up --count 60
    python capture_photos.py --name not_thumbs_up --count 60
"""

import argparse
import time
from pathlib import Path

from picamera2 import Picamera2

OUTPUT_ROOT = Path.home() / "training_photos"


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True, help="Subfolder name, e.g. 'my_face' or 'thumbs_up'")
    parser.add_argument("--count", type=int, default=10, help="How many photos to capture")
    parser.add_argument("--delay", type=float, default=1.0, help="Seconds between each photo")
    return parser.parse_args()


def main():
    args = get_args()
    out_dir = OUTPUT_ROOT / args.name
    out_dir.mkdir(parents=True, exist_ok=True)

    picam2 = Picamera2()
    config = picam2.create_still_configuration()
    picam2.start(config)
    time.sleep(1)  # let auto-exposure/white-balance settle before the first shot

    existing = list(out_dir.glob("*.jpg"))
    start_index = len(existing)

    print(f"Capturing {args.count} photos into {out_dir}")
    print("Move slightly between shots (angle, expression, distance) for a more useful dataset.")

    for i in range(args.count):
        index = start_index + i
        path = out_dir / f"{index:04d}.jpg"
        picam2.capture_file(str(path))
        print(f"[{i + 1}/{args.count}] saved {path.name}")
        time.sleep(args.delay)

    picam2.stop()
    print("Done.")


if __name__ == "__main__":
    main()
