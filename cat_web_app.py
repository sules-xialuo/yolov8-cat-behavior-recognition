# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import random
import time
import uuid
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parent
YOLO_CONFIG_ROOT = ROOT / "runs" / "ultralytics_config"
YOLO_CONFIG_ROOT.mkdir(parents=True, exist_ok=True)
os.environ["YOLO_CONFIG_DIR"] = str(YOLO_CONFIG_ROOT)

from ultralytics import YOLO


OUTPUT_DIR = ROOT / "runs" / "cat_web_app"
NAMES = ["shangtai", "qianqing", "xiachui", "shuangbian", "yuantong", "quansuo", "shutong"]
MODEL_CANDIDATES = [
    ROOT / "runs" / "detect" / "cats_focus_yolov8s6" / "weights" / "best.pt",
    ROOT / "weights" / "cats_focus_best.pt",
    ROOT / "runs" / "detect" / "cats_focus_yolov8s" / "weights" / "best.pt",
]

CLASS_LABELS = {
    "shangtai": "上抬",
    "qianqing": "前倾",
    "xiachui": "下垂",
    "shuangbian": "双边耳朵",
    "yuantong": "圆瞳",
    "quansuo": "蜷缩/收缩",
    "shutong": "竖瞳",
}

BOX_COLORS = {
    "shangtai": (116, 143, 99),
    "qianqing": (92, 129, 153),
    "xiachui": (195, 138, 53),
    "shuangbian": (207, 126, 112),
    "yuantong": (139, 115, 160),
    "quansuo": (138, 99, 72),
    "shutong": (82, 112, 94),
}

STATE_OPTIONS = {
    "pupil": {
        "shutong": "竖瞳",
        "yuantong": "圆瞳",
        "inconsistent": "双眼不一致",
        "unknown": "未判断",
    },
    "ears": {
        "shuangbian": "双边耳朵",
        "qianqing": "前倾",
        "unknown": "未判断",
    },
    "tail": {
        "xiachui": "尾巴下垂",
        "shangtai": "尾巴上抬",
        "quansuo": "尾巴蜷缩/贴近身体",
        "unknown": "未判断",
    },
}


@dataclass
class Detection:
    cls_name: str
    label: str
    conf: float
    xyxy: tuple[int, int, int, int]
    adjusted_from: str | None = None


MODEL: YOLO | None = None


def model_path() -> Path:
    for path in MODEL_CANDIDATES:
        if path.exists():
            return path
    raise FileNotFoundError(
        "未找到猫姿态模型权重。请将 best.pt 放回 runs/detect/cats_focus_yolov8s6/weights/best.pt "
        "或 weights/cats_focus_best.pt。"
    )


def get_model() -> YOLO:
    global MODEL
    if MODEL is None:
        MODEL = YOLO(str(model_path()))
    return MODEL


def pick_state(detections: list[Detection]) -> dict[str, str]:
    best: dict[str, Detection] = {}
    for det in detections:
        if det.cls_name in {"shutong", "yuantong"}:
            current = best.get("pupil")
            if current is None or det.conf > current.conf:
                best["pupil"] = det
        if det.cls_name in {"shuangbian", "qianqing"}:
            current = best.get("ears")
            if current is None or det.conf > current.conf:
                best["ears"] = det
        if det.cls_name in {"xiachui", "shangtai", "quansuo"}:
            current = best.get("tail")
            if current is None or det.conf > current.conf:
                best["tail"] = det
    return {
        "pupil": best["pupil"].cls_name if "pupil" in best else "unknown",
        "ears": best["ears"].cls_name if "ears" in best else "unknown",
        "tail": best["tail"].cls_name if "tail" in best else "unknown",
    }


def harmonize_pupil_detections(detections: list[Detection]) -> list[str]:
    pupils = [det for det in detections if det.cls_name in {"shutong", "yuantong"}]
    classes = {det.cls_name for det in pupils}
    if len(classes) < 2:
        return []

    best_by_class = {
        cls_name: max([det for det in pupils if det.cls_name == cls_name], key=lambda item: item.conf)
        for cls_name in classes
    }
    high, low = sorted(best_by_class.values(), key=lambda item: item.conf, reverse=True)[:2]

    if high.conf >= 0.60 and high.conf - low.conf >= 0.12:
        for det in pupils:
            if det.cls_name != high.cls_name:
                det.adjusted_from = det.cls_name
                det.cls_name = high.cls_name
                det.label = CLASS_LABELS[high.cls_name]
        return [
            f"眼部一致性修正：检测到两类瞳孔状态冲突，已将低置信度的 {CLASS_LABELS[low.cls_name]} "
            f"按高置信度 {CLASS_LABELS[high.cls_name]} 处理。"
        ]

    return [
        "检测到双眼瞳孔状态不一致，但置信度差距不够大，系统未强行合并。若肉眼也确认两眼明显不同，建议尽快咨询兽医。"
    ]


def human_state(state: dict[str, str]) -> dict[str, str]:
    return {key: STATE_OPTIONS[key].get(value, "未判断") for key, value in state.items()}


def advice_for(state: dict[str, str]) -> dict[str, object]:
    pupil = state.get("pupil", "unknown")
    ears = state.get("ears", "unknown")
    tail = state.get("tail", "unknown")

    risk = "observe"
    title = "需要结合环境继续观察"
    summary_pool = [
        "当前线索还不完整，建议结合声音、身体高度、是否躲避和环境刺激一起判断。",
        "这组姿态更适合作为提醒信号，而不是单独下结论。请观察它是否能很快恢复放松。",
    ]
    actions = [
        "先降低刺激源，例如停止追逐、抱起或强行互动。",
        "给猫留出退路和高处/隐蔽处，观察 5 到 10 分钟。",
        "如果伴随持续躲藏、攻击、食欲下降或呼吸异常，应联系兽医。",
    ]
    notes = [
        "单一姿态不等于诊断，最可靠的判断来自多个身体信号和当时环境。",
        "如果状态持续存在或突然改变，优先排除疼痛、惊吓和环境压力。",
    ]

    if pupil == "shutong" and ears == "shuangbian" and tail == "xiachui":
        risk = "danger"
        title = "高警戒或防御倾向"
        summary_pool = [
            "竖瞳、双侧耳部紧张和尾巴下垂同时出现时，常见于猫正在评估威胁或准备拉开距离。",
            "这更像是紧张、警戒或防御前的姿态组合，不建议继续靠近或逗弄。",
            "当视觉专注、耳部紧张和尾部下压同时出现时，猫通常已经不太愿意继续承受刺激。",
        ]
        actions = [
            "立刻停止触摸、拍摄逼近或逗猫棒刺激。",
            "让猫能主动离开，避免堵住门口、猫窝或高处通道。",
            "移除可能的刺激源，如陌生人、噪声、其他宠物或突然移动的物体。",
            "如果伴随哈气、低吼、扑咬或持续躲藏，按高风险处理。",
        ]
        notes = [
            "不要用手直接阻挡或抓回猫，防御状态下的抓咬往往是被迫反应。",
            "等猫主动恢复进食、梳理、慢眨眼或正常走动后，再考虑轻度互动。",
        ]
    elif tail == "quansuo" or (ears == "shuangbian" and pupil == "yuantong"):
        risk = "caution"
        title = "不安或压力上升"
        summary_pool = [
            "耳朵紧张、瞳孔变圆或尾巴贴近身体，通常提示猫的压力正在上升。",
            "这组信号常见于害怕、犹豫或不确定环境是否安全。",
            "它未必会攻击，但此时继续互动可能让压力升级。",
        ]
        actions = [
            "降低声音和动作幅度，暂时不要抱起。",
            "提供纸箱、猫窝或高处，让它自己选择是否靠近。",
            "把互动改成低强度，例如远距离慢眨眼或安静陪伴。",
            "把食物、水和猫砂盆放在容易到达但不被打扰的位置。",
        ]
        notes = [
            "可以记录触发因素，例如陌生人、吹风机、同伴靠近或环境变化。",
            "如果压力状态反复出现，建议优化躲藏点、垂直空间和资源分布。",
        ]
    elif tail == "shangtai" and ears == "qianqing" and pupil != "yuantong":
        risk = "calm"
        title = "好奇或相对放松"
        summary_pool = [
            "尾巴上抬、耳朵前倾通常更接近探索、关注或愿意互动的状态。",
            "这组表现整体偏正向，但仍要看尾尖是否快速抽动、身体是否僵硬。",
            "如果它能主动靠近、嗅闻并保持柔软步态，通常可以温和互动。",
        ]
        actions = [
            "可以用轻柔声音回应，避免突然伸手到头顶。",
            "让猫主动靠近，再尝试短时间抚摸脸颊或下巴附近。",
            "如果尾巴快速甩动或耳朵转平，及时停止互动。",
            "用短时游戏或少量零食强化它主动靠近的行为。",
        ]
        notes = [
            "放松不代表可以无限互动，猫离开时应允许它结束接触。",
            "如果瞳孔突然放大、尾巴甩动加快，可能从好奇转为兴奋或压力。",
        ]
    elif ears == "qianqing" and tail == "xiachui":
        risk = "observe"
        title = "专注但略有保留"
        summary_pool = [
            "耳朵前倾说明它在关注目标，尾巴下垂则可能表示谨慎或情绪不完全放松。",
            "这可能是观察新事物、等待或轻微不确定的组合。",
            "它可能还在判断眼前事物是否安全，因此更适合给时间，而不是催促靠近。",
        ]
        actions = [
            "保持环境稳定，让猫自己决定靠近或离开。",
            "不要突然伸手，可用食物或玩具建立正向联系。",
            "观察尾巴是否继续下压、耳朵是否转平，若有升级就减少刺激。",
        ]
        notes = [
            "这种状态适合继续观察，不建议立刻做护理、洗澡或强制抱起。",
            "如果它主动靠近并嗅闻，可以给予简短、低强度回应。",
        ]

    if pupil == "inconsistent":
        risk = "caution"
        title = "双眼瞳孔不一致，需要医学排查"
        summary_pool = [
            "如果肉眼确认两只眼睛的瞳孔大小或形态明显不同，这更像是眼科或神经系统信号，而不是普通情绪姿态。",
            "双眼瞳孔不一致不应只按行为状态解释，建议优先排除眼部疼痛、外伤、炎症或神经问题。",
        ]
        actions = [
            "不要自行滴人用眼药水，也不要强光长时间照射眼睛。",
            "观察是否有流泪、眯眼、角膜浑浊、歪头、走路异常或精神沉郁。",
            "如果变化突然出现、持续存在或伴随疼痛表现，应尽快联系兽医或兽医眼科。",
        ]
        notes = [
            "该规则不会自动把异常情况当作训练错误处理。",
            "网页识别只能作为筛查线索，不能替代兽医检查。",
        ]

    return {
        "risk": risk,
        "title": title,
        "summary": random.choice(summary_pool),
        "actions": actions,
        "notes": notes,
    }


def draw_clean_boxes(image, detections: list[Detection]):
    canvas = image.copy()
    height, width = canvas.shape[:2]
    thickness = max(1, round(min(width, height) / 700))
    for det in detections:
        x1, y1, x2, y2 = det.xyxy
        color = BOX_COLORS.get(det.cls_name, (100, 130, 110))
        cv2.rectangle(canvas, (x1, y1), (x2, y2), color, thickness, cv2.LINE_AA)
    return canvas


def run_prediction(image_bytes: bytes) -> dict[str, object]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    image_array = cv2.imdecode(np.frombuffer(image_bytes, dtype="uint8"), cv2.IMREAD_COLOR)
    if image_array is None:
        raise ValueError("无法读取图片，请换一张 jpg/png 图片。")

    result = get_model().predict(source=image_array, imgsz=768, conf=0.25, iou=0.7, verbose=False)[0]
    detections: list[Detection] = []
    if result.boxes is not None:
        for box, cls, conf in zip(
            result.boxes.xyxy.cpu().numpy(),
            result.boxes.cls.cpu().numpy(),
            result.boxes.conf.cpu().numpy(),
        ):
            cls_name = NAMES[int(cls)]
            x1, y1, x2, y2 = [int(round(v)) for v in box]
            detections.append(Detection(cls_name, CLASS_LABELS[cls_name], float(conf), (x1, y1, x2, y2)))

    consistency_notes = harmonize_pupil_detections(detections)
    annotated = draw_clean_boxes(image_array, detections)
    output_name = f"{int(time.time())}_{uuid.uuid4().hex[:8]}.jpg"
    output_path = OUTPUT_DIR / output_name
    cv2.imwrite(str(output_path), annotated)

    state = pick_state(detections)
    return {
        "image_url": f"/outputs/{output_name}",
        "detections": [
            {"class": det.cls_name, "label": det.label, "confidence": round(det.conf, 3), "box": det.xyxy}
            for det in detections
        ],
        "state": human_state(state),
        "advice": advice_for(state),
        "consistency_notes": consistency_notes,
    }


HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>猫姿态识别与照护建议</title>
  <style>
    :root{--cream:#fff8ef;--paper:#fffdf9;--ink:#2b2520;--muted:#766a60;--line:#eadfce;--shadow:0 18px 50px rgba(65,49,31,.12)}
    *{box-sizing:border-box} body{margin:0;font-family:"Microsoft YaHei","Segoe UI",sans-serif;color:var(--ink);background:radial-gradient(circle at 18% 8%,rgba(255,220,169,.45),transparent 28%),linear-gradient(135deg,#fff6e8 0%,#f5f0e8 46%,#edf4ef 100%);min-height:100vh}
    header{padding:34px 28px 18px;max-width:1180px;margin:0 auto} h1{margin:0;font-size:clamp(28px,4vw,46px);line-height:1.12;letter-spacing:0}.sub{margin:12px 0 0;color:var(--muted);max-width:760px;line-height:1.8;font-size:15px}
    main{max-width:1180px;margin:0 auto;padding:16px 28px 44px;display:grid;grid-template-columns:minmax(0,1.25fr) minmax(330px,.75fr);gap:18px}
    section,.panel{background:rgba(255,253,249,.88);border:1px solid rgba(234,223,206,.95);border-radius:8px;box-shadow:var(--shadow)}.workspace{padding:18px}.toolbar{display:flex;gap:10px;flex-wrap:wrap;align-items:center;justify-content:space-between;margin-bottom:14px}
    .filebox{flex:1;min-width:260px;border:1px dashed #d9c8b4;background:#fffaf3;border-radius:8px;padding:12px}input[type=file]{width:100%}button{border:0;border-radius:8px;padding:12px 16px;background:#425d4b;color:white;cursor:pointer;font-weight:700;min-height:44px}button.secondary{background:#8d6b4d}button:disabled{opacity:.55;cursor:wait}
    .preview{min-height:380px;display:grid;place-items:center;background:#fbf6ee;border:1px solid var(--line);border-radius:8px;overflow:hidden}.preview img{width:100%;height:auto;display:block}.empty{color:var(--muted);text-align:center;padding:24px;line-height:1.8}
    aside{display:grid;gap:18px;align-content:start}.panel{padding:18px}h2{margin:0 0 12px;font-size:18px;letter-spacing:0}.det-list{display:grid;gap:8px}.pill{display:flex;justify-content:space-between;gap:10px;background:#f6efe4;border:1px solid #eadccb;padding:9px 10px;border-radius:8px;font-size:14px}
    .risk{border-radius:8px;padding:13px;margin-bottom:12px;border:1px solid var(--line)}.risk.danger{background:#fff0ee;border-color:#efc0bb}.risk.caution{background:#fff7e6;border-color:#ecd39d}.risk.calm{background:#edf7ef;border-color:#c6dec9}.risk.observe{background:#eef5f8;border-color:#c7dce7}.risk strong{display:block;margin-bottom:6px}.advice ul{margin:8px 0 0;padding-left:20px;line-height:1.7;color:#4c433b}
    label{display:block;color:var(--muted);margin:10px 0 5px;font-size:13px}select,textarea{width:100%;border:1px solid var(--line);border-radius:8px;padding:10px;background:#fffdf9;color:var(--ink);font:inherit}textarea{min-height:86px;resize:vertical}.state-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.small{color:var(--muted);font-size:13px;line-height:1.7}.sources{color:var(--muted);font-size:12px;line-height:1.7}
    @media(max-width:900px){main{grid-template-columns:1fr;padding:12px 16px 34px}header{padding:28px 16px 12px}.state-grid{grid-template-columns:1fr}}
  </style>
</head>
<body>
  <header><h1>猫姿态识别与照护建议</h1><p class="sub">上传猫的姿态图片，系统会识别瞳孔、耳朵、尾巴等部位状态，并给出温和、可执行的照护反馈。也可以跳过图片，直接按肉眼观察选择三类状态获得建议。</p></header>
  <main>
    <section class="workspace"><div class="toolbar"><div class="filebox"><input id="imageInput" type="file" accept="image/*" /></div><button id="detectBtn">上传识别</button></div><div class="preview" id="preview"><div class="empty">选择图片后点击上传识别。识别完成后，这里会显示带框结果。</div></div></section>
    <aside>
      <div class="panel advice"><h2>识别反馈</h2><div id="adviceBox" class="small">等待识别或手动选择状态。</div></div>
      <div class="panel"><h2>识别到的目标</h2><div id="detections" class="det-list small">暂无目标。</div></div>
      <div class="panel"><h2>肉眼观察输入</h2><div class="state-grid">
        <div><label>瞳孔</label><select id="manualPupil"><option value="unknown">未判断</option><option value="shutong">竖瞳</option><option value="yuantong">圆瞳</option><option value="inconsistent">双眼不一致</option></select></div>
        <div><label>耳朵</label><select id="manualEars"><option value="unknown">未判断</option><option value="shuangbian">双边耳朵</option><option value="qianqing">前倾</option></select></div>
        <div><label>尾巴</label><select id="manualTail"><option value="unknown">未判断</option><option value="xiachui">尾巴下垂</option><option value="shangtai">尾巴上抬</option><option value="quansuo">蜷缩/贴近身体</option></select></div>
      </div><label>补充观察</label><textarea id="manualNote" placeholder="例如：猫正在低吼、躲在桌下、尾巴快速摆动等。"></textarea><div style="margin-top:12px"><button class="secondary" id="manualBtn">生成文本反馈</button></div></div>
      <div class="panel sources">参考方向：Cornell Feline Health Center、PetMD 兽医行为内容、Merck Veterinary Manual、RSPCA 猫肢体语言资料。此页面用于日常观察辅助，不能替代兽医诊断。</div>
    </aside>
  </main>
  <script>
    const detectBtn=document.getElementById('detectBtn'),imageInput=document.getElementById('imageInput'),preview=document.getElementById('preview'),adviceBox=document.getElementById('adviceBox'),detections=document.getElementById('detections');
    function renderAdvice(data){const risk=data.advice.risk||'observe';const actions=(data.advice.actions||[]).map(a=>`<li>${a}</li>`).join('');const notes=(data.advice.notes||[]).map(a=>`<li>${a}</li>`).join('');const consistency=(data.consistency_notes||[]).map(a=>`<li>${a}</li>`).join('');const state=data.state||{};adviceBox.innerHTML=`<div class="risk ${risk}"><strong>${data.advice.title}</strong><div>${data.advice.summary}</div></div><div class="small">状态：瞳孔 ${state.pupil||'未判断'} · 耳朵 ${state.ears||'未判断'} · 尾巴 ${state.tail||'未判断'}</div><div class="small" style="margin-top:10px;font-weight:700;color:#3f352d;">建议做法</div><ul>${actions}</ul>${consistency?`<div class="small" style="margin-top:10px;font-weight:700;color:#3f352d;">一致性校正</div><ul>${consistency}</ul>`:''}<div class="small" style="margin-top:10px;font-weight:700;color:#3f352d;">观察提示</div><ul>${notes}</ul>`}
    function renderDetections(items){if(!items||!items.length){detections.innerHTML='未检测到目标，建议换一张更清晰、包含猫头部和尾部的图片。';return}detections.innerHTML=items.map(item=>`<div class="pill"><span>${item.label}</span><span>${Math.round(item.confidence*100)}%</span></div>`).join('')}
    detectBtn.onclick=async()=>{const file=imageInput.files[0];if(!file)return alert('请先选择图片。');detectBtn.disabled=true;detectBtn.textContent='识别中...';const fd=new FormData();fd.append('image',file);try{const res=await fetch('/api/predict',{method:'POST',body:fd});const data=await res.json();if(!res.ok)throw new Error(data.error||'识别失败');preview.innerHTML=`<img src="${data.image_url}" alt="识别结果" />`;renderAdvice(data);renderDetections(data.detections)}catch(err){alert(err.message)}finally{detectBtn.disabled=false;detectBtn.textContent='上传识别'}};
    document.getElementById('manualBtn').onclick=async()=>{const payload={pupil:document.getElementById('manualPupil').value,ears:document.getElementById('manualEars').value,tail:document.getElementById('manualTail').value,note:document.getElementById('manualNote').value};const res=await fetch('/api/manual',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const data=await res.json();renderAdvice(data);detections.innerHTML='文本反馈模式未调用图像识别。'};
  </script>
</body>
</html>
"""


class MultipartParser:
    def __init__(self, content_type: str, body: bytes):
        self.content_type = content_type
        self.body = body

    def file_bytes(self, field_name: str) -> bytes | None:
        marker = "boundary="
        if marker not in self.content_type:
            return None
        boundary = self.content_type.split(marker, 1)[1].encode()
        for part in self.body.split(b"--" + boundary):
            if f'name="{field_name}"'.encode() not in part or b"\r\n\r\n" not in part:
                continue
            return part.split(b"\r\n\r\n", 1)[1].rstrip(b"\r\n-")
        return None


class CatHandler(BaseHTTPRequestHandler):
    def send_json(self, payload: dict[str, object], status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            data = HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if parsed.path.startswith("/outputs/"):
            path = OUTPUT_DIR / Path(parsed.path).name
            if not path.exists():
                self.send_error(404)
                return
            data = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        self.send_error(404)

    def do_POST(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            if self.path == "/api/predict":
                image = MultipartParser(self.headers.get("Content-Type", ""), body).file_bytes("image")
                if not image:
                    self.send_json({"error": "没有收到图片文件。"}, 400)
                    return
                self.send_json(run_prediction(image))
                return
            if self.path == "/api/manual":
                payload = json.loads(body.decode("utf-8") or "{}")
                state = {
                    "pupil": payload.get("pupil", "unknown"),
                    "ears": payload.get("ears", "unknown"),
                    "tail": payload.get("tail", "unknown"),
                }
                self.send_json({"state": human_state(state), "advice": advice_for(state)})
                return
            self.send_error(404)
        except Exception as exc:
            self.send_json({"error": str(exc)}, 500)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", 7860), CatHandler)
    print("Cat web app running at http://127.0.0.1:7860")
    print("Model candidates:")
    for path in MODEL_CANDIDATES:
        print(f"  {path}")
    server.serve_forever()


if __name__ == "__main__":
    main()
