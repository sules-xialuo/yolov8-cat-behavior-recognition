from __future__ import annotations

import argparse
import csv
import filecmp
import shutil
from datetime import datetime
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync manually reviewed LabelImg labels back to source datasets.")
    parser.add_argument("--review", type=Path, default=Path(r"review/suspect_labels"))
    parser.add_argument("--datasets-root", type=Path, default=Path(r"datasets/cats"))
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def backup_file(path: Path, backup_root: Path) -> Path:
    backup_root.mkdir(parents=True, exist_ok=True)
    backup_path = backup_root / path.name
    shutil.copy2(path, backup_path)
    return backup_path


def dataset_label_targets(source_label: Path, datasets_root: Path) -> list[Path]:
    targets = []
    for split in ("train", "val"):
        candidate = datasets_root / "labels" / split / source_label.name
        if candidate.exists():
            targets.append(candidate)
    return targets


def main() -> None:
    args = parse_args()
    manifest = args.review / "manifest.csv"
    if not manifest.exists():
        raise FileNotFoundError(manifest)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = args.review / "backups" / timestamp
    changed = 0
    synced_targets = 0

    with manifest.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    for row in rows:
        review_label = Path(row["review_label"])
        source_label = Path(row["source_label"])
        if not review_label.exists():
            print(f"missing_review_label={review_label}")
            continue
        if not source_label.exists():
            print(f"missing_source_label={source_label}")
            continue
        if filecmp.cmp(review_label, source_label, shallow=False):
            continue

        changed += 1
        targets = [source_label] + dataset_label_targets(source_label, args.datasets_root)
        print(f"changed={source_label.name}")
        for target in targets:
            print(f"  sync_target={target}")
            if args.dry_run:
                continue
            backup_file(target, backup_root / target.parent.name)
            shutil.copy2(review_label, target)
            synced_targets += 1

    print(f"changed_review_labels={changed}")
    print(f"synced_targets={synced_targets}")
    if args.dry_run:
        print("dry_run=true")
    else:
        print(f"backup_dir={backup_root}")


if __name__ == "__main__":
    main()
