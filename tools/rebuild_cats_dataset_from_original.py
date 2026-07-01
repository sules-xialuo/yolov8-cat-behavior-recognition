from __future__ import annotations

import argparse
import hashlib
import shutil
from pathlib import Path

import cv2


NAMES = ["shangtai", "qianqing", "xiachui", "shuangbian", "yuantong", "quansuo", "shutong"]
IMAGE_EXTS = [".jpg", ".jpeg", ".png", ".bmp", ".webp"]


def read_label(path: Path) -> None:
    for line_no, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
        parts = line.split()
        if len(parts) != 5:
            continue
        cls = int(parts[0])
        values = [float(x) for x in parts[1:]]
        if cls < 0 or cls >= len(NAMES) or any(v < 0 or v > 1 for v in values) or values[2] <= 0 or values[3] <= 0:
            raise ValueError(f"Invalid YOLO label in {path}:{line_no}: {line}")


def find_image(image_root: Path, stem: str) -> Path | None:
    for ext in IMAGE_EXTS:
        path = image_root / f"{stem}{ext}"
        if path.exists():
            return path
    return None


def is_valid_image(path: Path) -> bool:
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
        return False
    image = cv2.imread(str(path))
    return image is not None and image.size > 0


def split_for(stem: str, val_ratio: float) -> str:
    bucket = int(hashlib.md5(stem.encode("utf-8")).hexdigest()[:8], 16) / 0xFFFFFFFF
    return "val" if bucket < val_ratio else "train"


def copy_pair(image: Path, label: Path, dst: Path, split: str) -> None:
    image_dst = dst / "images" / split
    label_dst = dst / "labels" / split
    image_dst.mkdir(parents=True, exist_ok=True)
    label_dst.mkdir(parents=True, exist_ok=True)
    shutil.copy2(image, image_dst / f"{image.stem}{image.suffix.lower()}")
    shutil.copy2(label, label_dst / label.name)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rebuild datasets/cats from a flat original YOLO dataset.")
    parser.add_argument("--src", type=Path, default=Path(r"D:\catshuju\original_dataset"))
    parser.add_argument("--dst", type=Path, default=Path("datasets/cats"))
    parser.add_argument("--val-ratio", type=float, default=0.2)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    image_root = args.src / "images"
    label_root = args.src / "labels"
    if args.dst.exists():
        if not args.overwrite:
            raise SystemExit(f"{args.dst} already exists. Use --overwrite to recreate it.")
        shutil.rmtree(args.dst)

    counts = {"train": 0, "val": 0}
    skipped_missing_image = 0
    skipped_non_label = 0
    skipped_invalid_image = 0

    for label in sorted(label_root.glob("*.txt")):
        if label.name.lower() == "classes.txt":
            skipped_non_label += 1
            continue
        image = find_image(image_root, label.stem)
        if image is None:
            skipped_missing_image += 1
            continue
        if not is_valid_image(image):
            skipped_invalid_image += 1
            print(f"skipped_invalid_image={image}")
            continue
        read_label(label)
        split = split_for(label.stem, args.val_ratio)
        copy_pair(image, label, args.dst, split)
        counts[split] += 1

    print(f"train={counts['train']}")
    print(f"val={counts['val']}")
    print(f"skipped_missing_image={skipped_missing_image}")
    print(f"skipped_invalid_image={skipped_invalid_image}")
    print(f"skipped_non_label={skipped_non_label}")


if __name__ == "__main__":
    main()
