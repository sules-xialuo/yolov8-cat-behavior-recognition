# 基于 YOLOv8 的猫行为状态识别系统

这是一个基于 YOLOv8 的猫局部视觉特征检测与行为状态反馈项目。项目使用猫的尾巴、耳朵、瞳孔等视觉部位状态进行检测，并在网页端给出面向日常照护的状态解释和建议。

## 功能概览

- 使用 YOLOv8 检测猫的 7 类局部状态：
  - `shangtai`：尾巴上抬
  - `qianqing`：耳朵前倾
  - `xiachui`：尾巴下垂
  - `shuangbian`：双边耳朵
  - `yuantong`：圆瞳
  - `quansuo`：尾巴蜷缩/收缩
  - `shutong`：竖瞳
- 提供本地网页应用：上传图片后展示检测框与文字反馈。
- 支持纯文本状态输入：用户可手动选择瞳孔、耳朵、尾巴状态并生成建议。
- 包含数据重建、离线增强、精选样本微调、动态超参数试验脚本。

## 主要入口

### 启动网页应用

```powershell
D:\anaconda\envs\yolov8\python.exe cat_web_app.py
```

浏览器打开：

```text
http://127.0.0.1:7860
```

网页后端会调用：

```text
weights/cats_focus_best.pt
```

### 动态超参数训练流水线

```powershell
D:\anaconda\envs\yolov8\python.exe run_cats_dynamic_hparam_pipeline.py
```

该脚本会执行：

1. 从 `D:\catshuju\original_dataset` 重建训练/验证数据集。
2. 对训练集进行必要标签一致性处理。
3. 生成增强数据集。
4. 构建精选样本二阶段微调数据集。
5. 跑 4 组安全的动态超参数 trial。
6. 按 `mAP50-95` 自动选择最佳模型。
7. 若优于当前基线，则备份旧权重并更新 `weights/cats_focus_best.pt`。

## 当前最佳 trial

历史实验中表现最好的动态超参数组为：

```text
low_lr2e5
Precision: 0.66476
Recall:    0.65107
mAP50:     0.65697
mAP50-95:  0.43504
best_epoch: 1
```

独立复查结果：

```text
Precision: 0.64458
Recall:    0.65991
mAP50:     0.65841
mAP50-95:  0.43592
```

## 项目结构

```text
cat_web_app.py                         # 本地网页应用入口
run_cats_dynamic_hparam_pipeline.py    # 数据重建 + 增强 + 动态超参数训练流水线
train_cats_focus_reviewed_finetune.py  # 单组保守微调脚本
tools/                                 # 数据构建、增强、复核、同步、校验工具
ultralytics/                           # YOLOv8 本地源码
weights/cats_focus_best.pt             # 当前用于部署的最佳模型权重
yolo-cats.yaml                         # 基础数据配置
yolo-cats-aug.yaml                     # 增强数据配置
yolo-cats-focus.yaml                   # 精选微调数据配置
requirements-cat-app.txt               # 项目运行依赖参考
GITHUB_UPLOAD_GUIDE.md                 # GitHub 上传说明
```
8n.pt`、`yolov8s.pt` 等基础预训练权重

## 数据说明

本项目默认数据源路径为：

```text
D:\catshuju\original_dataset
```

## 环境说明

开发环境示例：

```text
Python 3.8
PyTorch 1.13.1 + CUDA 11.6
Ultralytics YOLOv8 Python 包
Windows + NVIDIA RTX 4060 Laptop GPU
```

可参考 `requirements-cat-app.txt` 安装必要依赖，其中包含 `ultralytics`。


