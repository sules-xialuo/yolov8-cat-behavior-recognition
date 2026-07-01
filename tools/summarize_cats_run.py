from __future__ import annotations

import argparse
import csv
from pathlib import Path


NAMES = ["shangtai", "qianqing", "xiachui", "shuangbian", "yuantong", "quansuo", "shutong"]
BASELINE_MAP5095 = 0.26973


def read_results(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def count_labels(root: Path) -> list[int]:
    counts = [0] * len(NAMES)
    for label_path in root.glob("*.txt"):
        for line in label_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            parts = line.split()
            if len(parts) == 5 and parts[0].isdigit():
                cls = int(parts[0])
                if 0 <= cls < len(counts):
                    counts[cls] += 1
    return counts


def write_report(run_dir: Path, dataset_dir: Path, out_path: Path) -> None:
    rows = read_results(run_dir / "results.csv")
    best = max(rows, key=lambda r: float(r["metrics/mAP50-95(B)"]))
    last = rows[-1]
    train_counts = count_labels(dataset_dir / "labels" / "train")
    val_counts = count_labels(dataset_dir / "labels" / "val")

    lines = [
        "# Cats Focus Fine-Tune Report",
        "",
        f"Run directory: `{run_dir}`",
        f"Dataset directory: `{dataset_dir}`",
        f"Baseline mAP50-95: `{BASELINE_MAP5095:.5f}`",
        "",
        "## Metrics",
        "",
        "| row | epoch | precision | recall | mAP50 | mAP50-95 | delta vs baseline |",
        "|---|---:|---:|---:|---:|---:|---:|",
        (
            f"| best | {best['epoch']} | {float(best['metrics/precision(B)']):.5f} | "
            f"{float(best['metrics/recall(B)']):.5f} | {float(best['metrics/mAP50(B)']):.5f} | "
            f"{float(best['metrics/mAP50-95(B)']):.5f} | "
            f"{float(best['metrics/mAP50-95(B)']) - BASELINE_MAP5095:+.5f} |"
        ),
        (
            f"| last | {last['epoch']} | {float(last['metrics/precision(B)']):.5f} | "
            f"{float(last['metrics/recall(B)']):.5f} | {float(last['metrics/mAP50(B)']):.5f} | "
            f"{float(last['metrics/mAP50-95(B)']):.5f} | "
            f"{float(last['metrics/mAP50-95(B)']) - BASELINE_MAP5095:+.5f} |"
        ),
        "",
        "## Label Distribution",
        "",
        "| class | name | train boxes | val boxes |",
        "|---:|---|---:|---:|",
    ]
    for i, name in enumerate(NAMES):
        lines.append(f"| {i} | {name} | {train_counts[i]} | {val_counts[i]} |")

    lines.extend(
        [
            "",
            "## Review Priority",
            "",
            "Prioritize manual review and new annotations for `quansuo`, `xiachui`, and `shangtai`, then inspect",
            "`confusion_matrix_normalized.png` for the most confused class pairs in this run.",
        ]
    )
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize a cats fine-tuning run and dataset balance.")
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, default=Path("datasets/cats_focus"))
    parser.add_argument("--out", type=Path, default=Path("runs/detect/cats_focus_report.md"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    write_report(args.run, args.dataset, args.out)
    print(f"report={args.out}")


if __name__ == "__main__":
    main()
