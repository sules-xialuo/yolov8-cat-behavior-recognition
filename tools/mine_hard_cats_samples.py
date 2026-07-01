from __future__ import annotations

import argparse
import csv
from pathlib import Path

from PIL import Image
from ultralytics import YOLO


NAMES = ["shangtai", "qianqing", "xiachui", "shuangbian", "yuantong", "quansuo", "shutong"]
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def read_yolo_label(path: Path) -> list[tuple[int, tuple[float, float, float, float]]]:
    labels = []
    if not path.exists():
        return labels
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        parts = line.split()
        if len(parts) != 5:
            continue
        cls = int(parts[0])
        x, y, w, h = [float(v) for v in parts[1:]]
        labels.append((cls, (x, y, w, h)))
    return labels


def yolo_to_xyxy(box: tuple[float, float, float, float], width: int, height: int) -> tuple[float, float, float, float]:
    x, y, w, h = box
    x1 = (x - w / 2) * width
    y1 = (y - h / 2) * height
    x2 = (x + w / 2) * width
    y2 = (y + h / 2) * height
    return x1, y1, x2, y2


def iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    inter = iw * ih
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def mine(args: argparse.Namespace) -> list[dict[str, object]]:
    model = YOLO(str(args.weights))
    rows: list[dict[str, object]] = []
    image_paths = sorted(p for p in args.images.glob("*") if p.suffix.lower() in IMAGE_EXTS)

    for image_path in image_paths:
        label_path = args.labels / f"{image_path.stem}.txt"
        labels = read_yolo_label(label_path)
        with Image.open(image_path) as im:
            width, height = im.size

        gt_boxes = [(cls, yolo_to_xyxy(box, width, height)) for cls, box in labels]
        result = model.predict(
            source=str(image_path),
            imgsz=args.imgsz,
            conf=args.conf,
            iou=args.nms_iou,
            device=args.device,
            verbose=False,
        )[0]

        preds = []
        if result.boxes is not None:
            xyxy = result.boxes.xyxy.cpu().numpy()
            classes = result.boxes.cls.cpu().numpy()
            confs = result.boxes.conf.cpu().numpy()
            for box, cls, conf in zip(xyxy, classes, confs):
                preds.append((int(cls), tuple(float(v) for v in box), float(conf)))

        matched_pred_indexes: set[int] = set()
        missed = 0
        low_iou = 0
        best_ious = []

        for gt_cls, gt_box in gt_boxes:
            same_class = [
                (idx, iou(gt_box, pred_box))
                for idx, (pred_cls, pred_box, _conf) in enumerate(preds)
                if pred_cls == gt_cls and idx not in matched_pred_indexes
            ]
            if not same_class:
                missed += 1
                best_ious.append(0.0)
                continue
            best_idx, best_iou = max(same_class, key=lambda item: item[1])
            if best_iou >= args.match_iou:
                matched_pred_indexes.add(best_idx)
            else:
                low_iou += 1
            best_ious.append(best_iou)

        false_positive = len(preds) - len(matched_pred_indexes)
        mean_best_iou = sum(best_ious) / len(best_ious) if best_ious else 0.0
        score = missed * 3 + low_iou * 2 + false_positive + max(0.0, args.match_iou - mean_best_iou)
        classes = sorted({NAMES[cls] for cls, _box in gt_boxes})

        rows.append(
            {
                "score": round(score, 4),
                "image": str(image_path),
                "label": str(label_path),
                "classes": ";".join(classes),
                "gt_count": len(gt_boxes),
                "pred_count": len(preds),
                "missed": missed,
                "low_iou": low_iou,
                "false_positive": false_positive,
                "mean_best_iou": round(mean_best_iou, 4),
            }
        )

    rows.sort(key=lambda row: (float(row["score"]), int(row["missed"]), int(row["low_iou"])), reverse=True)
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rank validation images that are likely hard or mislabeled.")
    parser.add_argument("--weights", type=Path, default=Path(r"runs/detect/cats_focus_yolov8s4/weights/best.pt"))
    parser.add_argument("--images", type=Path, default=Path("datasets/cats_focus/images/val"))
    parser.add_argument("--labels", type=Path, default=Path("datasets/cats_focus/labels/val"))
    parser.add_argument("--output", type=Path, default=Path("runs/detect/cats_focus_yolov8s4/hard_samples.csv"))
    parser.add_argument("--top", type=int, default=30)
    parser.add_argument("--imgsz", type=int, default=768)
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--nms-iou", type=float, default=0.7)
    parser.add_argument("--match-iou", type=float, default=0.5)
    parser.add_argument("--device", default="0")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = mine(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        if rows:
            writer.writeheader()
            writer.writerows(rows)

    print(f"output={args.output}")
    print(f"images_checked={len(rows)}")
    for row in rows[: args.top]:
        print(
            f"{row['score']}\tmissed={row['missed']}\tlow_iou={row['low_iou']}\t"
            f"fp={row['false_positive']}\tmean_iou={row['mean_best_iou']}\t{row['image']}"
        )


if __name__ == "__main__":
    main()
