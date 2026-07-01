from __future__ import annotations

import argparse
from pathlib import Path

import cv2


NAMES = ["shangtai", "qianqing", "xiachui", "shuangbian", "yuantong", "quansuo", "shutong"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate YOLO labels and count dataset images.")
    parser.add_argument("--root", type=Path, default=Path("datasets/cats_focus"))
    return parser.parse_args()


def validate_label(path: Path) -> tuple[int, int]:
    total = 0
    bad = 0
    for line_no, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
        parts = line.split()
        if len(parts) != 5:
            continue
        total += 1
        try:
            cls = int(parts[0])
            values = [float(x) for x in parts[1:]]
            if cls < 0 or cls >= len(NAMES) or any(v < 0 or v > 1 for v in values) or values[2] <= 0 or values[3] <= 0:
                bad += 1
                print(f"bad_label={path}:{line_no}:{line}")
        except ValueError:
            bad += 1
            print(f"bad_label={path}:{line_no}:{line}")
    return total, bad


def validate_image(path: Path) -> bool:
    header = path.read_bytes()[:16]
    suffix = path.suffix.lower()
    signatures = {
        ".jpg": header.startswith(b"\xff\xd8\xff"),
        ".jpeg": header.startswith(b"\xff\xd8\xff"),
        ".png": header.startswith(b"\x89PNG\r\n\x1a\n"),
        ".bmp": header.startswith(b"BM"),
        ".webp": header.startswith(b"RIFF") and header[8:12] == b"WEBP",
    }
    if not signatures.get(suffix, False):
        print(f"bad_image={path}")
        return False
    image = cv2.imread(str(path))
    if image is not None and image.size > 0:
        return True
    print(f"bad_image={path}")
    return False


def main() -> None:
    args = parse_args()
    total_labels = 0
    bad_labels = 0
    bad_images = 0
    for split in ("train", "val"):
        images = list((args.root / "images" / split).glob("*"))
        labels = list((args.root / "labels" / split).glob("*.txt"))
        print(f"{args.root} {split}_images={len(images)}")
        print(f"{args.root} {split}_labels={len(labels)}")
        for image in images:
            if not validate_image(image):
                bad_images += 1
        for label in labels:
            total, bad = validate_label(label)
            total_labels += total
            bad_labels += bad
    print(f"total_labels_checked={total_labels}")
    print(f"bad_labels={bad_labels}")
    print(f"bad_images={bad_images}")


if __name__ == "__main__":
    main()
