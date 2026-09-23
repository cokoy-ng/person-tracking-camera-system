"""Detección de personas con los pesos del clon MobileNet-SSD y OpenCV."""
from pathlib import Path

MODEL_DIR = Path(__file__).resolve().parents[2] / 'ai' / 'comp_vision' / 'human-detector'


class HumanDetector:
    def __init__(self, confidence=0.5):
        import cv2
        self.cv2 = cv2
        self.confidence = confidence
        self.net = cv2.dnn.readNetFromCaffe(
            str(MODEL_DIR / 'deploy.prototxt'),
            str(MODEL_DIR / 'mobilenet_iter_73000.caffemodel'))

    def detect(self, frame):
        height, width = frame.shape[:2]
        self.net.setInput(self.cv2.dnn.blobFromImage(
            frame, 0.007843, (300, 300), 127.5, swapRB=False, crop=False))
        people = []
        for detection in self.net.forward()[0, 0]:
            # Clase 15 = person en VOC (ver human-detector/demo.py).
            if int(detection[1]) != 15 or detection[2] < self.confidence:
                continue
            x1, y1, x2, y2 = (detection[3:7] * [width, height, width, height]).astype(int)
            x1, x2 = max(0, min(width, x1)), max(0, min(width, x2))
            y1, y2 = max(0, min(height, y1)), max(0, min(height, y2))
            if x2 > x1 and y2 > y1:
                people.append((x1, y1, x2, y2))
        return people
