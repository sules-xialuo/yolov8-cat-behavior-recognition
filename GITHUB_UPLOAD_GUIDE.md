# GitHub 上传指南

## 建议上传的核心内容

- `README.md`
- `LICENSE`
- `cat_web_app.py`
- `run_cats_dynamic_hparam_pipeline.py`
- `train_cats_focus_reviewed_finetune.py`
- `tools/`
- `yolo-cats.yaml`
- `yolo-cats-aug.yaml`
- `yolo-cats-focus.yaml`
- `requirements-cat-app.txt`
- `CATS_DYNAMIC_HPARAM_README.md`
- `weights/README.md`
- `weights/cats_focus_best.pt`
- `UPLOAD_MANIFEST.md`

## 不建议上传的内容

以下内容已在 `.gitignore` 中排除：

- `datasets/`
- `runs/`
- `review/`
- `logs/`
- `pt_check*/`
- `recovery_check/`
- `resume_render*/`
- `thesis_render/`
- `.tmp/`
- `.ultralytics_config/`
- `*.docx`
- `*.pdf`
- `~$*`
- `yolov8*.pt`
- 除 `weights/cats_focus_best.pt` 以外的其它 `.pt` 权重

## 关于 ultralytics

为了控制 GitHub 网页上传文件数，干净上传包不包含完整 `ultralytics/` 源码目录。运行项目时通过依赖安装：

```powershell
pip install -r requirements-cat-app.txt
```

## 上传前检查

在有 Git 的终端里执行：

```powershell
git status --short
```

确认没有出现以下目录或文件：

```text
datasets/
runs/
review/
logs/
*.docx
*.pdf
yolov8s.pt
yolov8n.pt
ultralytics/
```

如果出现这些文件，先不要提交，检查 `.gitignore` 是否生效。

## 第一次上传示例

```powershell
git init
git add .
git status --short
git commit -m "Initial cat behavior recognition project"
git branch -M main
git remote add origin https://github.com/<your-name>/<your-repo>.git
git push -u origin main
```

## 关于模型权重

当前部署模型 `weights/cats_focus_best.pt` 大约 20 多 MB，低于 GitHub 单文件 100 MB 限制，可以直接上传。若后续模型超过 100 MB，建议使用 Git LFS 或 GitHub Releases。
