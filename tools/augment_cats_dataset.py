from __future__ import annotations

import argparse
import random
import shutil
from pathlib import Path

import albumentations as A
import cv2


NAMES = ["shangtai", "qianqing", "xiachui", "shuangbian", "yuantong", "quansuo", "shutong"]
SUPPORTED_IMAGE_SUFFIXES = {".bmp", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}
MEDIUM_RARE_CLASSES = {0, 2}  # shangtai, xiachui
RARE_CLASSES = {5}  # quansuo


def read_yolo_labels(path: Path) -> tuple[list[int], list[list[float]]]:
    classes: list[int] = []
    boxes: list[list[float]] = []
    if not path.exists():
        return classes, boxes

    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split()
        if len(parts) != 5:
            continue
        cls, x, y, w, h = parts
        classes.append(int(cls))
        boxes.append([float(x), float(y), float(w), float(h)])
    return classes, boxes


def write_yolo_labels(path: Path, classes: list[int], boxes: list[list[float]]) -> None:
    lines = [
        f"{cls} {box[0]:.6f} {box[1]:.6f} {box[2]:.6f} {box[3]:.6f}"
        for cls, box in zip(classes, boxes)
    ]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def is_valid_image(path: Path) -> bool:
    if path.suffix.lower() not in SUPPORTED_IMAGE_SUFFIXES:
        return False
    image = cv2.imread(str(path))
    return image is not None and image.size > 0


def quarantine_pair(src: Path, image_path: Path, label_path: Path, split: str) -> None:
    quarantine_root = src.parent / f"{src.name}_invalid"
    image_dst = quarantine_root / "images" / split
    label_dst = quarantine_root / "labels" / split
    image_dst.mkdir(parents=True, exist_ok=True)
    label_dst.mkdir(parents=True, exist_ok=True)

    shutil.move(str(image_path), image_dst / image_path.name)
    if label_path.exists():
        shutil.move(str(label_path), label_dst / label_path.name)


def copies_for(classes: list[int], base_copies: int, medium_copies: int, rare_copies: int) -> int:
    class_set = set(classes)
    if class_set.intersection(RARE_CLASSES):
        return rare_copies
    if class_set.intersection(MEDIUM_RARE_CLASSES):
        return medium_copies
    return base_copies


def make_transform(seed: int) -> A.Compose:
    random.seed(seed)
    return A.Compose(
        [
            A.HorizontalFlip(p=0.5),
            A.OneOf(
                [
                    A.Affine(
                        scale=(0.92, 1.08),
                        translate_percent=(-0.04, 0.04),
                        rotate=(-5, 5),
                        shear=(-2, 2),
                        mode=cv2.BORDER_CONSTANT,
                        cval=(114, 114, 114),
                        p=1.0,
                    ),
                    A.Perspective(scale=(0.01, 0.025), keep_size=True, fit_output=False, p=1.0),
                ],
                p=0.55,
            ),
            A.OneOf(
                [
                    A.RandomBrightnessContrast(brightness_limit=0.12, contrast_limit=0.12, p=1.0),
                    A.HueSaturationValue(hue_shift_limit=4, sat_shift_limit=12, val_shift_limit=10, p=1.0),
                    A.CLAHE(clip_limit=(1, 2), tile_grid_size=(8, 8), p=1.0),
                ],
                p=0.65,
            ),
            A.OneOf(
                [
                    A.GaussianBlur(blur_limit=(3, 3), p=1.0),
                    A.GaussNoise(var_limit=(4.0, 18.0), mean=0.0, p=1.0),
                ],
                p=0.15,
            ),
        ],
        bbox_params=A.BboxParams(
            format="yolo",
            label_fields=["class_labels"],
            min_visibility=0.45,
            clip=True,
        ),
    )


def copy_split(src: Path, dst: Path, split: str, quarantine_invalid: bool) -> None:
    image_dst = dst / "images" / split
    label_dst = dst / "labels" / split
    image_dst.mkdir(parents=True, exist_ok=True)
    label_dst.mkdir(parents=True, exist_ok=True)

    for image_path in (src / "images" / split).glob("*"):
        if not image_path.is_file():
            continue

        label_path = src / "labels" / split / f"{image_path.stem}.txt"
        if not is_valid_image(image_path):
            print(f"Skipping invalid image: {image_path}")
            if quarantine_invalid:
                quarantine_pair(src, image_path, label_path, split)
            continue

        shutil.copy2(image_path, image_dst / image_path.name)
        if label_path.exists():
            shutil.copy2(label_path, label_dst / label_path.name)


def augment_train(src: Path, dst: Path, base_copies: int, medium_copies: int, rare_copies: int) -> None:
    image_dst = dst / "images" / "train"
    label_dst = dst / "labels" / "train"
    image_src = src / "images" / "train"
    label_src = src / "labels" / "train"
    transform = make_transform(seed=0)

    for image_path in sorted(image_src.glob("*")):
        if not image_path.is_file():
            continue
        label_path = label_src / f"{image_path.stem}.txt"
        classes, boxes = read_yolo_labels(label_path)
        if not boxes:
            continue

        image = cv2.imread(str(image_path))
        if image is None:
            print(f"Skipping invalid train image during augmentation: {image_path}")
            continue

        for idx in range(copies_for(classes, base_copies, medium_copies, rare_copies)):
            transformed = transform(image=image, bboxes=boxes, class_labels=classes)
            aug_boxes = [list(box) for box in transformed["bboxes"]]
            aug_classes = [int(cls) for cls in transformed["class_labels"]]
            if not aug_boxes:
                continue

            out_stem = f"{image_path.stem}_aug{idx + 1}"
            cv2.imwrite(str(image_dst / f"{out_stem}.jpg"), transformed["image"], [cv2.IMWRITE_JPEG_QUALITY, 95])
            write_yolo_labels(label_dst / f"{out_stem}.txt", aug_classes, aug_boxes)


def write_yaml(dst: Path, yaml_path: Path) -> None:
    content = (
        f"path: {dst}\n"
        "train: images/train\n"
        "val: images/val\n\n"
        f"nc: {len(NAMES)}\n"
        f"names: {NAMES}\n"
    )
    yaml_path.write_text(content, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a YOLO cats dataset with conservative offline augmentation.")
    parser.add_argument("--src", type=Path, default=Path("datasets/cats"))
    parser.add_argument("--dst", type=Path, default=Path("datasets/cats_aug"))
    parser.add_argument("--yaml", type=Path, default=Path("yolo-cats-aug.yaml"))
    parser.add_argument("--base-copies", type=int, default=0)
    parser.add_argument("--medium-copies", type=int, default=1)
    parser.add_argument("--rare-copies", type=int, default=3)
    parser.add_argument("--quarantine-invalid", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.dst.exists():
        if not args.overwrite:
            raise SystemExit(f"{args.dst} already exists. Use --overwrite to recreate it.")
        shutil.rmtree(args.dst)

    copy_split(args.src, args.dst, "train", args.quarantine_invalid)
    copy_split(args.src, args.dst, "val", args.quarantine_invalid)
    augment_train(args.src, args.dst, args.base_copies, args.medium_copies, args.rare_copies)
    write_yaml(args.dst.resolve(), args.yaml)


if __name__ == "__main__":
    main()
