from __future__ import annotations

import argparse
import hashlib
import shutil
from pathlib import Path


NAMES = ["shangtai", "qianqing", "xiachui", "shuangbian", "yuantong", "quansuo", "shutong"]
IMAGE_EXTS = [".jpg", ".jpeg", ".png", ".bmp", ".webp"]


def read_label(path: Path) -> None:
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        parts = line.split()
        if len(parts) != 5:
            continue
        cls = int(parts[0])
        values = [float(x) for x in parts[1:]]
        if cls < 0 or cls >= len(NAMES) or any(v < 0 or v > 1 for v in values) or values[2] <= 0 or values[3] <= 0:
            raise ValueError(f"Invalid YOLO label in {path}: {line}")


def find_image(image_root: Path, stem: str) -> Path | None:
    for ext in IMAGE_EXTS:
        path = image_root / f"{stem}{ext}"
        if path.exists():
            return path
    return None


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
    parser = argparse.ArgumentParser(description="Merge newly labeled original cat images into datasets/cats.")
    parser.add_argument("--src", type=Path, default=Path(r"D:\catshuju\original_dataset"))
    parser.add_argument("--dst", type=Path, default=Path("datasets/cats"))
    parser.add_argument("--val-ratio", type=float, default=0.2)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    image_root = args.src / "images"
    label_root = args.src / "labels"
    added = {"train": 0, "val": 0}
    skipped_existing = {"train": 0, "val": 0}
    skipped_missing_image = 0
    skipped_non_label = 0

    for label in sorted(label_root.glob("*.txt")):
        if label.name.lower() == "classes.txt":
            skipped_non_label += 1
            continue

        image = find_image(image_root, label.stem)
        if image is None:
            skipped_missing_image += 1
            continue

        train_label = args.dst / "labels" / "train" / label.name
        val_label = args.dst / "labels" / "val" / label.name
        if train_label.exists():
            skipped_existing["train"] += 1
            continue
        if val_label.exists():
            skipped_existing["val"] += 1
            continue

        read_label(label)
        split = split_for(label.stem, args.val_ratio)
        copy_pair(image, label, args.dst, split)
        added[split] += 1

    print(f"added_train={added['train']}")
    print(f"added_val={added['val']}")
    print(f"skipped_existing_train={skipped_existing['train']}")
    print(f"skipped_existing_val={skipped_existing['val']}")
    print(f"skipped_missing_image={skipped_missing_image}")
    print(f"skipped_non_label={skipped_non_label}")


if __name__ == "__main__":
    main()
