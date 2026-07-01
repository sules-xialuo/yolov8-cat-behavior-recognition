from __future__ import annotations

import argparse
import shutil
from pathlib import Path


NAMES = ["shangtai", "qianqing", "xiachui", "shuangbian", "yuantong", "quansuo", "shutong"]


def copy_tree_files(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for path in src.glob("*"):
        if path.is_file():
            shutil.copy2(path, dst / path.name)


def read_label(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(path)
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) != 5:
            continue
        cls = int(parts[0])
        values = [float(x) for x in parts[1:]]
        if cls < 0 or cls >= len(NAMES) or any(v < 0 or v > 1 for v in values) or values[2] <= 0 or values[3] <= 0:
            raise ValueError(f"Invalid YOLO label in {path}: {line}")
        lines.append(line)
    return lines


def write_yaml(dst: Path, yaml_path: Path) -> None:
    content = (
        f"path: {dst.resolve()}\n"
        "train: images/train\n"
        "val: images/val\n\n"
        f"nc: {len(NAMES)}\n"
        f"names: {NAMES}\n"
    )
    yaml_path.write_text(content, encoding="utf-8")


def repeat_for_label(label_lines: list[str], repeat: int, rare_repeat: int) -> int:
    classes = {int(line.split()[0]) for line in label_lines if line.split()}
    # Put a little more weight on historically weaker / lower-count classes.
    if classes.intersection({0, 2, 5}):
        return rare_repeat
    return repeat


def add_focus_samples(src: Path, selected: Path, dst: Path, repeat: int, rare_repeat: int) -> tuple[int, int, int]:
    train_label_root = src / "labels" / "train"
    val_label_root = src / "labels" / "val"
    image_dst = dst / "images" / "train"
    label_dst = dst / "labels" / "train"
    focus_count = 0
    excluded_val_count = 0
    copied_focus_count = 0

    for image_path in sorted(selected.glob("*.jpg")):
        train_label = train_label_root / f"{image_path.stem}.txt"
        val_label = val_label_root / f"{image_path.stem}.txt"

        if val_label.exists() and not train_label.exists():
            excluded_val_count += 1
            continue
        if not train_label.exists():
            raise FileNotFoundError(f"Missing train label for selected image: {image_path}")

        label_lines = read_label(train_label)
        sample_repeat = repeat_for_label(label_lines, repeat, rare_repeat)
        for idx in range(1, sample_repeat + 1):
            out_stem = f"{image_path.stem}_focus{idx}"
            shutil.copy2(image_path, image_dst / f"{out_stem}.jpg")
            (label_dst / f"{out_stem}.txt").write_text("\n".join(label_lines) + "\n", encoding="utf-8")
            copied_focus_count += 1
        focus_count += 1

    return focus_count, excluded_val_count, copied_focus_count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a second-stage focus fine-tuning dataset for cats.")
    parser.add_argument("--src", type=Path, default=Path("datasets/cats"))
    parser.add_argument("--aug", type=Path, default=Path("datasets/cats_aug"))
    parser.add_argument("--selected", type=Path, default=Path(r"D:\catshuju\tiaoxuan"))
    parser.add_argument("--dst", type=Path, default=Path("datasets/cats_focus"))
    parser.add_argument("--yaml", type=Path, default=Path("yolo-cats-focus.yaml"))
    parser.add_argument("--repeat", type=int, default=2)
    parser.add_argument("--rare-repeat", type=int, default=3)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.repeat < 1 or args.repeat > 3:
        raise ValueError("--repeat must be between 1 and 3")
    if args.rare_repeat < args.repeat or args.rare_repeat > 3:
        raise ValueError("--rare-repeat must be between --repeat and 3")

    if args.dst.exists():
        if not args.overwrite:
            raise SystemExit(f"{args.dst} already exists. Use --overwrite to recreate it.")
        shutil.rmtree(args.dst)

    copy_tree_files(args.aug / "images" / "train", args.dst / "images" / "train")
    copy_tree_files(args.aug / "labels" / "train", args.dst / "labels" / "train")
    copy_tree_files(args.src / "images" / "val", args.dst / "images" / "val")
    copy_tree_files(args.src / "labels" / "val", args.dst / "labels" / "val")

    focus_count, excluded_val_count, copied_focus_count = add_focus_samples(
        args.src, args.selected, args.dst, args.repeat, args.rare_repeat
    )
    write_yaml(args.dst, args.yaml)
    print(f"focus_train_images={focus_count}")
    print(f"excluded_selected_val_images={excluded_val_count}")
    print(f"focus_repeat={args.repeat}")
    print(f"rare_focus_repeat={args.rare_repeat}")
    print(f"copied_focus_images={copied_focus_count}")


if __name__ == "__main__":
    main()
