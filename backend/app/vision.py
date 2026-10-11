from __future__ import annotations

from pathlib import Path
from uuid import uuid4
from PIL import Image

from .config import UPLOAD_DIR, YOLO_DEVICE, YOLO_MODEL_PATH

_model = None


def _install_checkpoint_compatibility():
    """Expose the small set of custom layers required by bundled YOLO checkpoints."""
    import ultralytics.nn as ultralytics_nn

    compatibility_path = Path(__file__).parent / "yolo_compat" / "ultralytics" / "nn"
    path_value = str(compatibility_path)
    if path_value not in ultralytics_nn.__path__:
        ultralytics_nn.__path__.append(path_value)


def _load_model():
    global _model
    if not YOLO_MODEL_PATH:
        raise RuntimeError("未配置 YOLO_MODEL_PATH；请指向已验证的 .pt 权重文件后重试。")
    if not Path(YOLO_MODEL_PATH).is_file():
        raise RuntimeError("YOLO_MODEL_PATH 不存在或不可读取。")
    if _model is None:
        _install_checkpoint_compatibility()
        from ultralytics import YOLO
        _model = YOLO(YOLO_MODEL_PATH)
    return _model


def infer_image(filename: str, content: bytes, conf: float = 0.25) -> dict:
    suffix = Path(filename).suffix.lower() or ".jpg"
    target = UPLOAD_DIR / f"vision_{uuid4().hex}{suffix}"
    target.write_bytes(content)
    image = Image.open(target).convert("RGB")
    width, height = image.size
    result = _load_model().predict(source=str(target), conf=conf, device=YOLO_DEVICE, verbose=False)[0]
    names, detections = result.names, []
    for box in result.boxes:
        cls_id = int(box.cls.item())
        x1, y1, x2, y2 = [round(float(value), 1) for value in box.xyxy[0].tolist()]
        detections.append({"defect_type": str(names[cls_id]), "confidence": round(float(box.conf.item()), 4), "position": f"bbox=({x1},{y1},{x2},{y2})", "bbox_xyxy": [x1, y1, x2, y2]})
    return {"model_path": YOLO_MODEL_PATH, "image_name": filename, "width": width, "height": height, "detections": detections}
