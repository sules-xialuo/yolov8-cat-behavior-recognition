# GitHub upload package manifest

This folder is a clean GitHub upload package with fewer than 100 files.

## Included
- Application: `cat_web_app.py`
- Deployment model: `weights/cats_focus_best.pt`
- Training pipeline: `run_cats_dynamic_hparam_pipeline.py`
- Fine-tuning script: `train_cats_focus_reviewed_finetune.py`
- Data tools: `tools/`
- YOLO dataset configs: `yolo-cats*.yaml`
- Documentation: `README.md`, `GITHUB_UPLOAD_GUIDE.md`, `CATS_DYNAMIC_HPARAM_README.md`
- Dependency list: `requirements-cat-app.txt`
- License

## Not included
- `ultralytics/` source tree. Install it with `pip install ultralytics`.
- datasets
- runs
- review folders
- logs
- paper documents
- resumes
- base weights such as `yolov8s.pt`
- old checkpoints
