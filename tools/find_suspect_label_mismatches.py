from __future__ import annotations

import argparse
import csv
from pathlib import Path

import cv2
from ultralytics import YOLO


NAMES = ["shangtai", "qianqing", "xiachui", "shuangbian", "yuantong", "quansuo", "shutong"]
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def find_image_paths(image_root: Path) -> list[Path]:
    return sorted(path for path in image_root.glob("*") if path.suffix.lower() in IMAGE_EXTS)


def read_labels(label_path: Path) -> list[tuple[int, tuple[float, float, float, float]]]:
    labels = []
    if not label_path.exists():
        return labels

    for line_no, line in enumerate(label_path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
        parts = line.split()
        if len(parts) != 5:
            continue
        cls = int(parts[0])
        x, y, w, h = [float(value) for value in parts[1:]]
        if cls < 0 or cls >= len(NAMES):
            raise ValueError(f"Invalid class id in {label_path}:{line_no}: {line}")
        labels.append((cls, (x, y, w, h)))
    return labels


def yolo_to_xyxy(box: tuple[float, float, float, float], width: int, height: int) -> tuple[float, float, float, float]:
    x, y, w, h = box
    return (
        (x - w / 2) * width,
        (y - h / 2) * height,
        (x + w / 2) * width,
        (y + h / 2) * height,
    )


def calc_iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def draw_box(
    image,
    box: tuple[float, float, float, float],
    text: str,
    color: tuple[int, int, int],
) -> None:
    x1, y1, x2, y2 = [int(round(value)) for value in box]
    cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
    text_y = max(16, y1 - 6)
    cv2.putText(image, text, (x1, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2, cv2.LINE_AA)


def save_review_image(
    image_path: Path,
    output_path: Path,
    gt_box: tuple[float, float, float, float],
    gt_name: str,
    pred_box: tuple[float, float, float, float],
    pred_name: str,
    pred_conf: float,
) -> None:
    image = cv2.imread(str(image_path))
    if image is None:
        return
    draw_box(image, gt_box, f"GT {gt_name}", (0, 255, 255))
    draw_box(image, pred_box, f"PRED {pred_name} {pred_conf:.2f}", (0, 0, 255))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), image)


def scan(args: argparse.Namespace) -> list[dict[str, object]]:
    model = YOLO(str(args.weights))
    rows: list[dict[str, object]] = []
    review_saved = 0

    for image_path in find_image_paths(args.images):
        label_path = args.labels / f"{image_path.stem}.txt"
        labels = read_labels(label_path)
        if not labels:
            continue

        image = cv2.imread(str(image_path))
        if image is None:
            continue
        height, width = image.shape[:2]
        gt_items = [(cls, yolo_to_xyxy(box, width, height)) for cls, box in labels]

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
            for box, cls, conf in zip(
                result.boxes.xyxy.cpu().numpy(),
                result.boxes.cls.cpu().numpy(),
                result.boxes.conf.cpu().numpy(),
            ):
                preds.append((int(cls), tuple(float(v) for v in box), float(conf)))

        for gt_index, (gt_cls, gt_box) in enumerate(gt_items):
            if not preds:
                continue
            best_pred_cls, best_pred_box, best_conf = max(
                preds,
                key=lambda pred: calc_iou(gt_box, pred[1]),
            )
            best_iou = calc_iou(gt_box, best_pred_box)

            if best_iou < args.match_iou or best_pred_cls == gt_cls:
                continue

            review_path = ""
            if review_saved < args.save_top:
                review_file = args.review_dir / f"{image_path.stem}_gt{gt_index}_{NAMES[gt_cls]}_pred_{NAMES[best_pred_cls]}.jpg"
                save_review_image(image_path, review_file, gt_box, NAMES[gt_cls], best_pred_box, NAMES[best_pred_cls], best_conf)
                review_path = str(review_file)
                review_saved += 1

            rows.append(
                {
                    "image": str(image_path),
                    "label": str(label_path),
                    "gt_class_id": gt_cls,
                    "gt_class": NAMES[gt_cls],
                    "pred_class_id": best_pred_cls,
                    "pred_class": NAMES[best_pred_cls],
                    "pred_conf": round(best_conf, 4),
                    "iou": round(best_iou, 4),
                    "gt_index": gt_index,
                    "review_image": review_path,
                }
            )

    rows.sort(key=lambda row: (float(row["iou"]), float(row["pred_conf"])), reverse=True)
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Find likely class-name mismatches using high-IoU model predictions.")
    parser.add_argument("--weights", type=Path, default=Path(r"runs/detect/cats_focus_yolov8s4/weights/best.pt"))
    parser.add_argument("--images", type=Path, default=Path(r"D:\catshuju\original_dataset\images"))
    parser.add_argument("--labels", type=Path, default=Path(r"D:\catshuju\original_dataset\labels"))
    parser.add_argument("--output", type=Path, default=Path(r"runs/detect/cats_focus_yolov8s4/suspect_label_mismatches.csv"))
    parser.add_argument("--review-dir", type=Path, default=Path(r"runs/detect/cats_focus_yolov8s4/suspect_label_mismatch_images"))
    parser.add_argument("--save-top", type=int, default=80)
    parser.add_argument("--top", type=int, default=30)
    parser.add_argument("--imgsz", type=int, default=768)
    parser.add_argument("--conf", type=float, default=0.45)
    parser.add_argument("--nms-iou", type=float, default=0.7)
    parser.add_argument("--match-iou", type=float, default=0.65)
    parser.add_argument("--device", default="0")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = scan(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8-sig") as f:
        fieldnames = [
            "image",
            "label",
            "gt_class_id",
            "gt_class",
            "pred_class_id",
            "pred_class",
            "pred_conf",
            "iou",
            "gt_index",
            "review_image",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"output={args.output}")
    print(f"review_dir={args.review_dir}")
    print(f"suspect_mismatches={len(rows)}")
    for row in rows[: args.top]:
        print(
            f"iou={row['iou']}\tconf={row['pred_conf']}\t"
            f"gt={row['gt_class']} -> pred={row['pred_class']}\t{row['image']}"
        )


if __name__ == "__main__":
    main()
