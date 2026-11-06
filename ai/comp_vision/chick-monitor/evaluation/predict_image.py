"""Prueba explícita sobre una imagen; nunca sustituye los resultados de la cámara."""
import argparse
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', type=Path)
    args = parser.parse_args()
    os.environ.setdefault('YOLO_CONFIG_DIR', str(Path(os.environ.get('LOCALAPPDATA', '/tmp')) / 'chick-monitor/settings'))
    os.environ.setdefault('YOLO_AUTOINSTALL', 'false')
    import cv2
    import numpy as np
    from detector.yolo import ChickenDetector
    image = cv2.imdecode(np.frombuffer(args.image.read_bytes(), dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError('Imagen no válida')
    detector = ChickenDetector()
    detector.detect(np.zeros_like(image))
    started = time.perf_counter()
    boxes = detector.detect(image)
    print(json.dumps(dict(image=str(args.image), width=image.shape[1], height=image.shape[0],
        count=len(boxes), detections=boxes, inference_ms=round((time.perf_counter()-started)*1000, 1)), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
