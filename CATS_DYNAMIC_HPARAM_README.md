# Cats dynamic hyperparameter pipeline

Run from this project root:

```powershell
D:\anaconda\envs\yolov8\python.exe run_cats_dynamic_hparam_pipeline.py
```

What it does:

1. Sync is not repeated automatically. Finish LabelImg review first, then run `tools/sync_reviewed_labels.py` if needed.
2. Rebuild `datasets/cats` from `D:\catshuju\original_dataset`.
3. Apply train-only pupil-label harmonization for obvious non-tie cases.
4. Build a timestamped augmented dataset: `datasets/cats_aug_dynamic_YYYYMMDD_HHMMSS`.
5. Build a timestamped focus dataset: `datasets/cats_focus_dynamic_YYYYMMDD_HHMMSS`.
6. Validate all generated datasets.
7. Validate the current `weights/cats_focus_best.pt` as baseline.
8. Train 4 safe YOLOv8s fine-tuning trials from `weights/cats_focus_best.pt`.
9. Save a summary CSV under `runs/detect/dynamic_hparam_summaries`.
10. If the best trial beats baseline mAP50-95, back up and update `weights/cats_focus_best.pt`.

Trial groups:

- `stable_lr5e5`: stable low learning rate, light augmentation.
- `low_lr2e5`: lower learning rate, longer patience, safest for preserving old weights.
- `light_aug_lr1e4`: slightly stronger learning rate and augmentation.
- `cls_balance_lr5e5`: increases class-loss weight to test weak-class stability.

Conservative runtime options:

```powershell
D:\anaconda\envs\yolov8\python.exe run_cats_dynamic_hparam_pipeline.py --max-trials 2
```

Run tests but do not replace the main best weight:

```powershell
D:\anaconda\envs\yolov8\python.exe run_cats_dynamic_hparam_pipeline.py --no-update-best
```

Use existing generated dataset and only run trials:

```powershell
D:\anaconda\envs\yolov8\python.exe run_cats_dynamic_hparam_pipeline.py --skip-rebuild
```
