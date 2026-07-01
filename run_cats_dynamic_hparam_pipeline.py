from __future__ import annotations

import argparse
import csv
import gc
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PYTHON = sys.executable
BASE_WEIGHTS = ROOT / "weights" / "cats_focus_best.pt"
SUMMARY_DIR = ROOT / "runs" / "detect" / "dynamic_hparam_summaries"


TRIALS = [
    {
        "name": "stable_lr5e5",
        "epochs": 24,
        "patience": 7,
        "lr0": 0.00005,
        "lrf": 0.01,
        "weight_decay": 0.0005,
        "box": 7.5,
        "cls": 0.8,
        "dfl": 1.5,
        "degrees": 0.5,
        "translate": 0.01,
        "scale": 0.05,
        "hsv_h": 0.005,
        "hsv_s": 0.25,
        "hsv_v": 0.18,
    },
    {
        "name": "low_lr2e5",
        "epochs": 26,
        "patience": 8,
        "lr0": 0.00002,
        "lrf": 0.05,
        "weight_decay": 0.0005,
        "box": 7.5,
        "cls": 0.8,
        "dfl": 1.5,
        "degrees": 0.3,
        "translate": 0.01,
        "scale": 0.03,
        "hsv_h": 0.004,
        "hsv_s": 0.20,
        "hsv_v": 0.15,
    },
    {
        "name": "light_aug_lr1e4",
        "epochs": 22,
        "patience": 7,
        "lr0": 0.00010,
        "lrf": 0.01,
        "weight_decay": 0.0006,
        "box": 7.5,
        "cls": 0.85,
        "dfl": 1.5,
        "degrees": 1.0,
        "translate": 0.02,
        "scale": 0.08,
        "hsv_h": 0.006,
        "hsv_s": 0.30,
        "hsv_v": 0.22,
    },
    {
        "name": "cls_balance_lr5e5",
        "epochs": 24,
        "patience": 7,
        "lr0": 0.00005,
        "lrf": 0.02,
        "weight_decay": 0.0005,
        "box": 8.0,
        "cls": 1.0,
        "dfl": 1.5,
        "degrees": 0.5,
        "translate": 0.015,
        "scale": 0.05,
        "hsv_h": 0.005,
        "hsv_s": 0.25,
        "hsv_v": 0.18,
    },
]


def run(command: list[str]) -> None:
    print("\n>>> " + " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def count_original_pairs() -> tuple[int, int, int]:
    image_root = Path(r"D:\catshuju\original_dataset\images")
    label_root = Path(r"D:\catshuju\original_dataset\labels")
    image_exts = [".jpg", ".jpeg", ".png", ".bmp", ".webp"]
    labels = [p for p in label_root.glob("*.txt") if p.name.lower() != "classes.txt"]
    paired = 0
    for label in labels:
        if any((image_root / f"{label.stem}{ext}").exists() for ext in image_exts):
            paired += 1
    return len(labels), paired, len(list(image_root.glob("*")))


def rebuild_datasets(tag: str) -> tuple[Path, Path]:
    aug_dir = ROOT / "datasets" / f"cats_aug_dynamic_{tag}"
    focus_dir = ROOT / "datasets" / f"cats_focus_dynamic_{tag}"

    run([PYTHON, "tools/rebuild_cats_dataset_from_original.py", "--overwrite"])
    run([PYTHON, "tools/harmonize_train_eye_labels.py"])
    run(
        [
            PYTHON,
            "tools/augment_cats_dataset.py",
            "--dst",
            str(aug_dir),
            "--yaml",
            "yolo-cats-aug.yaml",
            "--base-copies",
            "0",
            "--medium-copies",
            "1",
            "--rare-copies",
            "3",
            "--quarantine-invalid",
            "--overwrite",
        ]
    )
    run(
        [
            PYTHON,
            "tools/build_cats_focus_dataset.py",
            "--aug",
            str(aug_dir),
            "--dst",
            str(focus_dir),
            "--yaml",
            "yolo-cats-focus.yaml",
            "--repeat",
            "2",
            "--rare-repeat",
            "3",
            "--overwrite",
        ]
    )
    for dataset in ("datasets/cats", str(aug_dir), str(focus_dir)):
        run([PYTHON, "tools/validate_cats_dataset.py", "--root", dataset])

    return aug_dir, focus_dir


def metric_value(row: dict[str, str], key: str) -> float:
    return float(row.get(key, "0") or 0)


def best_row_from_results(run_dir: Path) -> dict[str, str]:
    results_csv = run_dir / "results.csv"
    if not results_csv.exists():
        raise FileNotFoundError(results_csv)
    with results_csv.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise RuntimeError(f"No rows in {results_csv}")
    return max(rows, key=lambda row: metric_value(row, "metrics/mAP50-95(B)"))


def validate_baseline(tag: str) -> dict[str, float]:
    from ultralytics import YOLO

    print("\n>>> baseline validation", flush=True)
    model = YOLO(str(BASE_WEIGHTS))
    metrics = model.val(
        data="yolo-cats-focus.yaml",
        imgsz=768,
        batch=8,
        device=0,
        workers=0,
        plots=True,
        name=f"cats_dynamic_pretrain_val_{tag}",
    )
    return {
        "precision": float(metrics.box.mp),
        "recall": float(metrics.box.mr),
        "map50": float(metrics.box.map50),
        "map50_95": float(metrics.box.map),
    }


def train_trial(trial: dict[str, object], tag: str) -> dict[str, object]:
    from ultralytics import YOLO

    run_name = f"cats_dynamic_{tag}_{trial['name']}"
    run_dir = ROOT / "runs" / "detect" / run_name
    print(f"\n>>> train trial: {run_name}", flush=True)
    model = YOLO(str(BASE_WEIGHTS))
    model.train(
        data="yolo-cats-focus.yaml",
        epochs=int(trial["epochs"]),
        patience=int(trial["patience"]),
        imgsz=768,
        batch=8,
        device=0,
        workers=0,
        cache=False,
        amp=False,
        pretrained=True,
        optimizer="AdamW",
        seed=0,
        deterministic=True,
        lr0=float(trial["lr0"]),
        lrf=float(trial["lrf"]),
        cos_lr=True,
        warmup_epochs=0.0,
        warmup_bias_lr=0.0001,
        weight_decay=float(trial["weight_decay"]),
        box=float(trial["box"]),
        cls=float(trial["cls"]),
        dfl=float(trial["dfl"]),
        mosaic=0.0,
        mixup=0.0,
        copy_paste=0.0,
        degrees=float(trial["degrees"]),
        translate=float(trial["translate"]),
        scale=float(trial["scale"]),
        shear=0.0,
        perspective=0.0,
        fliplr=0.5,
        flipud=0.0,
        hsv_h=float(trial["hsv_h"]),
        hsv_s=float(trial["hsv_s"]),
        hsv_v=float(trial["hsv_v"]),
        close_mosaic=0,
        freeze=0,
        multi_scale=False,
        save=True,
        save_period=5,
        plots=True,
        name=run_name,
    )
    del model
    gc.collect()

    best_row = best_row_from_results(run_dir)
    return {
        "trial": trial["name"],
        "run_dir": str(run_dir),
        "weights": str(run_dir / "weights" / "best.pt"),
        "best_epoch": int(float(best_row["epoch"])),
        "precision": metric_value(best_row, "metrics/precision(B)"),
        "recall": metric_value(best_row, "metrics/recall(B)"),
        "map50": metric_value(best_row, "metrics/mAP50(B)"),
        "map50_95": metric_value(best_row, "metrics/mAP50-95(B)"),
        "lr0": trial["lr0"],
        "epochs": trial["epochs"],
        "patience": trial["patience"],
    }


def write_summary(tag: str, baseline: dict[str, float], rows: list[dict[str, object]]) -> Path:
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    path = SUMMARY_DIR / f"cats_dynamic_hparam_summary_{tag}.csv"
    fieldnames = [
        "trial",
        "best_epoch",
        "precision",
        "recall",
        "map50",
        "map50_95",
        "lr0",
        "epochs",
        "patience",
        "weights",
        "run_dir",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print("\n=== baseline ===", flush=True)
    print(
        f"P={baseline['precision']:.5f} R={baseline['recall']:.5f} "
        f"mAP50={baseline['map50']:.5f} mAP50-95={baseline['map50_95']:.5f}",
        flush=True,
    )
    print("\n=== trial summary ===", flush=True)
    for row in sorted(rows, key=lambda item: float(item["map50_95"]), reverse=True):
        print(
            f"{row['trial']}: epoch={row['best_epoch']} "
            f"P={float(row['precision']):.5f} R={float(row['recall']):.5f} "
            f"mAP50={float(row['map50']):.5f} mAP50-95={float(row['map50_95']):.5f}",
            flush=True,
        )
    print(f"\nsummary_csv={path}", flush=True)
    return path


def maybe_update_best(tag: str, baseline: dict[str, float], rows: list[dict[str, object]], no_update_best: bool) -> None:
    best = max(rows, key=lambda item: float(item["map50_95"]))
    best_map = float(best["map50_95"])
    baseline_map = float(baseline["map50_95"])
    if best_map <= baseline_map:
        print(
            f"\nBest trial did not beat baseline mAP50-95 ({best_map:.5f} <= {baseline_map:.5f}). "
            "weights/cats_focus_best.pt was not changed.",
            flush=True,
        )
        return
    if no_update_best:
        print(
            f"\nBest trial beats baseline ({best_map:.5f} > {baseline_map:.5f}), "
            "but --no-update-best was set.",
            flush=True,
        )
        return

    backup_dir = ROOT / "weights" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / f"cats_focus_best_before_dynamic_{tag}.pt"
    shutil.copy2(BASE_WEIGHTS, backup)
    shutil.copy2(Path(str(best["weights"])), BASE_WEIGHTS)
    print(f"\nUpdated weights/cats_focus_best.pt from trial {best['trial']}", flush=True)
    print(f"previous_best_backup={backup}", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rebuild cat datasets and test several safe YOLOv8s fine-tuning hyperparameters.")
    parser.add_argument("--skip-rebuild", action="store_true", help="Use existing yolo-cats-focus.yaml dataset.")
    parser.add_argument("--max-trials", type=int, default=len(TRIALS), help="Limit number of hyperparameter trials.")
    parser.add_argument("--no-update-best", action="store_true", help="Do not copy the best improved trial to weights/cats_focus_best.pt.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not BASE_WEIGHTS.exists():
        raise FileNotFoundError(BASE_WEIGHTS)

    tag = datetime.now().strftime("%Y%m%d_%H%M%S")
    label_count, paired_count, image_count = count_original_pairs()
    print(f"original_images={image_count}", flush=True)
    print(f"original_labels={label_count}", flush=True)
    print(f"original_labeled_pairs={paired_count}", flush=True)

    if not args.skip_rebuild:
        aug_dir, focus_dir = rebuild_datasets(tag)
        print(f"aug_dataset={aug_dir}", flush=True)
        print(f"focus_dataset={focus_dir}", flush=True)

    baseline = validate_baseline(tag)
    selected_trials = TRIALS[: max(1, min(args.max_trials, len(TRIALS)))]
    rows = [train_trial(trial, tag) for trial in selected_trials]
    write_summary(tag, baseline, rows)
    maybe_update_best(tag, baseline, rows, args.no_update_best)


if __name__ == "__main__":
    main()
