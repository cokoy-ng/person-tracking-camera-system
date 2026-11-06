import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def validated_model():
    manifest = json.loads((ROOT / 'models/provenance.json').read_text(encoding='utf-8'))
    path = ROOT / 'models' / manifest['file']
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != manifest['sha256']:
        raise RuntimeError('Falta el modelo verificado. Ejecuta evaluation/setup_windows.py con Python de Windows.')
    return path


class ChickenDetector:
    threshold = 0.4

    def __init__(self):
        import torch
        from ultralytics import YOLO
        torch.set_num_threads(max(1, min(4, (os.cpu_count() or 2)//2)))
        self.model = YOLO(str(validated_model()), task='detect')
        if self.model.names != {0: 'chicken'}:
            raise RuntimeError('El modelo no tiene la clase chicken esperada')

    def detect(self, image):
        results = self.model.predict(image, imgsz=640, conf=self.threshold, iou=0.45,
            max_det=100, device='cpu', verbose=False, save=False)[0]
        boxes = []
        if results.boxes is not None:
            for box, confidence, category in zip(results.boxes.xyxyn.tolist(),
                    results.boxes.conf.tolist(), results.boxes.cls.tolist()):
                if int(category) != 0:
                    continue
                x1, y1, x2, y2 = [max(0.0, min(1.0, float(value))) for value in box]
                if x2 > x1 and y2 > y1:
                    boxes.append(dict(x=x1, y=y1, width=x2-x1, height=y2-y1,
                                      confidence=round(float(confidence), 4), label='Pollito'))
        return boxes
