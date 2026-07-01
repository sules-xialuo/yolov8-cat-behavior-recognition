from __future__ import annotations

import argparse
import csv
import shutil
from pathlib import Path


NAMES = ["shangtai", "qianqing", "xiachui", "shuangbian", "yuantong", "quansuo", "shutong"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect suspected mislabeled images into a LabelImg review folder.")
    parser.add_argument(
        "--suspects",
        type=Path,
        default=Path(r"runs/detect/cats_focus_yolov8s4/suspect_label_mismatches_review_numeric.csv"),
    )
    parser.add_argument("--output", type=Path, default=Path(r"review/suspect_labels"))
    parser.add_argument("--min-iou", type=float, default=0.90)
    parser.add_argument("--min-conf", type=float, default=0.70)
    parser.add_argument("--limit", type=int, default=0, help="0 means no limit.")
    parser.add_argument("--exclude-manifest", type=Path, default=None)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def read_rows(path: Path, min_iou: float, min_conf: float) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    filtered = [
        row
        for row in rows
        if float(row["iou"]) >= min_iou and float(row["pred_conf"]) >= min_conf
    ]
    filtered.sort(key=lambda row: (float(row["iou"]), float(row["pred_conf"])), reverse=True)
    return filtered


def unique_by_image(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    seen = set()
    unique = []
    for row in rows:
        image = row["image"]
        if image in seen:
            continue
        seen.add(image)
        unique.append(row)
    return unique


def read_excluded_images(path: Path | None) -> set[str]:
    if path is None or not path.exists():
        return set()

    excluded = set()
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            source_image = row.get("source_image")
            if source_image:
                excluded.add(str(Path(source_image).resolve()).lower())
    return excluded


def write_classes(path: Path) -> None:
    path.write_text("\n".join(NAMES) + "\n", encoding="utf-8")


def write_manifest(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "review_image",
        "review_label",
        "source_image",
        "source_label",
        "gt_class_id",
        "gt_class",
        "pred_class_id",
        "pred_class",
        "pred_conf",
        "iou",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_open_script(output: Path, class_file: Path, labelimg_py: Path, labelimg_python: Path) -> None:
    script = output / "open_labelimg_review.ps1"
    content = (
        "$ErrorActionPreference = 'Stop'\n"
        f"& '{labelimg_python}' '{labelimg_py}' '{output / 'images'}' '{class_file}' '{output / 'labels'}'\n"
    )
    script.write_text(content, encoding="utf-8")


def main() -> None:
    args = parse_args()
    if args.output.exists():
        if not args.overwrite:
            raise SystemExit(f"{args.output} already exists. Use --overwrite to recreate it.")
        shutil.rmtree(args.output)

    images_dir = args.output / "images"
    labels_dir = args.output / "labels"
    images_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)

    excluded_images = read_excluded_images(args.exclude_manifest)
    rows = [
        row
        for row in unique_by_image(read_rows(args.suspects, args.min_iou, args.min_conf))
        if str(Path(row["image"]).resolve()).lower() not in excluded_images
    ]
    if args.limit > 0:
        rows = rows[: args.limit]

    manifest_rows = []
    for index, row in enumerate(rows, start=1):
        source_image = Path(row["image"])
        source_label = Path(row["label"])
        prefix = f"{index:04d}"
        review_image = images_dir / f"{prefix}_{source_image.name}"
        review_label = labels_dir / f"{prefix}_{source_label.name}"
        shutil.copy2(source_image, review_image)
        shutil.copy2(source_label, review_label)
        manifest_rows.append(
            {
                "review_image": str(review_image.resolve()),
                "review_label": str(review_label.resolve()),
                "source_image": str(source_image.resolve()),
                "source_label": str(source_label.resolve()),
                "gt_class_id": row["gt_class_id"],
                "gt_class": row["gt_class"],
                "pred_class_id": row["pred_class_id"],
                "pred_class": row["pred_class"],
                "pred_conf": row["pred_conf"],
                "iou": row["iou"],
            }
        )

    class_file = args.output / "classes.txt"
    labels_class_file = labels_dir / "classes.txt"
    write_classes(class_file)
    write_classes(labels_class_file)
    write_manifest(args.output / "manifest.csv", manifest_rows)
    write_open_script(
        args.output.resolve(),
        class_file.resolve(),
        Path(r"C:\Users\34296\.conda\envs\labelimg\Lib\site-packages\labelImg\labelImg.py"),
        Path(r"C:\Users\34296\.conda\envs\labelimg\python.exe"),
    )

    print(f"review_dir={args.output.resolve()}")
    print(f"images_collected={len(manifest_rows)}")
    print(f"excluded_images={len(excluded_images)}")
    print(f"manifest={args.output / 'manifest.csv'}")
    print(f"open_script={args.output / 'open_labelimg_review.ps1'}")


if __name__ == "__main__":
    main()
