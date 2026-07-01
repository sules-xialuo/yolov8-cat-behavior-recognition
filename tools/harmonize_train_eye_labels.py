from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path


PUPIL_CLASSES = {4: "yuantong", 6: "shutong"}


def parse_label(path: Path) -> list[list[str]]:
    rows = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        parts = line.split()
        if len(parts) == 5:
            rows.append(parts)
    return rows


def write_label(path: Path, rows: list[list[str]]) -> None:
    path.write_text("\n".join(" ".join(row) for row in rows) + ("\n" if rows else ""), encoding="utf-8")


def harmonize_rows(rows: list[list[str]]) -> tuple[list[list[str]], bool, str]:
    pupil_indexes = [idx for idx, row in enumerate(rows) if int(row[0]) in PUPIL_CLASSES]
    pupil_classes = {int(rows[idx][0]) for idx in pupil_indexes}
    if len(pupil_classes) < 2:
        return rows, False, ""

    counts = {cls: sum(1 for idx in pupil_indexes if int(rows[idx][0]) == cls) for cls in pupil_classes}
    winner = max(counts, key=lambda cls: (counts[cls], cls))
    loser = min(counts, key=lambda cls: (counts[cls], cls))

    # Only harmonize obvious duplicate-eye conflicts. If there is a tie, keep labels for manual review.
    if counts[winner] == counts[loser]:
        return rows, False, f"tie {PUPIL_CLASSES[loser]} vs {PUPIL_CLASSES[winner]}"

    changed = False
    for idx in pupil_indexes:
        if int(rows[idx][0]) != winner:
            rows[idx][0] = str(winner)
            changed = True

    reason = f"{PUPIL_CLASSES[loser]} -> {PUPIL_CLASSES[winner]}"
    return rows, changed, reason


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Harmonize conflicting pupil labels in YOLO train labels only.")
    parser.add_argument("--labels", type=Path, default=Path("datasets/cats/labels/train"))
    parser.add_argument("--backup-root", type=Path, default=Path("review/eye_label_harmonize_backups"))
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    backup_dir = args.backup_root / datetime.now().strftime("%Y%m%d_%H%M%S")
    changed_count = 0
    skipped_tie = 0

    for label_path in sorted(args.labels.glob("*.txt")):
        rows = parse_label(label_path)
        new_rows, changed, reason = harmonize_rows(rows)
        if reason.startswith("tie"):
            skipped_tie += 1
            print(f"skip_tie={label_path.name} {reason}")
            continue
        if not changed:
            continue

        changed_count += 1
        print(f"changed={label_path.name} {reason}")
        if args.dry_run:
            continue
        backup_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(label_path, backup_dir / label_path.name)
        write_label(label_path, new_rows)

    print(f"changed_labels={changed_count}")
    print(f"skipped_tie={skipped_tie}")
    if args.dry_run:
        print("dry_run=true")
    else:
        print(f"backup_dir={backup_dir}")


if __name__ == "__main__":
    main()
