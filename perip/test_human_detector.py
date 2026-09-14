"""Pruebas reales del modelo; ejecutar con el Python de IA."""
import unittest

try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None

from human_detector import HumanDetector, MODEL_DIR


@unittest.skipIf(cv2 is None, 'Requiere el entorno de IA con OpenCV')
class HumanDetectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.detector = HumanDetector()

    def test_blank_frame_has_no_people(self):
        self.assertEqual(self.detector.detect(np.zeros((480, 640, 3), dtype=np.uint8)), [])

    def test_repository_examples_detect_people_with_valid_boxes(self):
        count = 0
        for path in sorted((MODEL_DIR / 'images').glob('*.jpg')):
            frame = cv2.imread(str(path))
            self.assertIsNotNone(frame, str(path))
            for x1, y1, x2, y2 in self.detector.detect(frame):
                self.assertTrue(0 <= x1 < x2 <= frame.shape[1])
                self.assertTrue(0 <= y1 < y2 <= frame.shape[0])
                count += 1
        self.assertGreater(count, 0, 'No se detectaron personas en los ejemplos originales')


if __name__ == '__main__':
    unittest.main()
