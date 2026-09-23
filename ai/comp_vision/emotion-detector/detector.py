"""Modelos de dev, con rutas absolutas y carga explícita para reutilizarlos."""
from pathlib import Path
import shutil
import tempfile

ROOT = Path(__file__).resolve().parent
CLASSES = ['angry', 'disgust', 'fear', 'happy', 'neutral', 'sad', 'surprise']


class Detector:
    def __init__(self, emotions=True):
        import cv2
        import numpy as np
        self.cv2, self.np = cv2, np
        self.face_net = cv2.dnn.readNetFromCaffe(
            str(ROOT / 'face_detector/deploy.prototxt'),
            str(ROOT / 'face_detector/res10_300x300_ssd_iter_140000.caffemodel'))
        self.model = None
        if emotions:
            import os
            os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '2')
            import tensorflow as tf
            import tf_keras as keras

            class BlurLayer(keras.layers.Layer):
                def build(self, input_shape):
                    kernel = tf.constant([[1, 2, 1], [2, 4, 2], [1, 2, 1]], dtype=tf.float32)
                    kernel = tf.reshape(kernel / tf.reduce_sum(kernel), [3, 3, 1, 1])
                    kernel = tf.tile(kernel, [1, 1, input_shape[-1], 1])
                    self.blur_filter = tf.Variable(kernel, trainable=False, name='blur_filter')

                def call(self, x):
                    return tf.nn.depthwise_conv2d(x, self.blur_filter, [1, 1, 1, 1], 'SAME')

            self.model = keras.models.model_from_json(
                (ROOT / 'model/67emotion_human.json').read_text(),
                custom_objects={'BlurLayer': BlurLayer, 'Sequential': keras.Sequential})
            # HDF5 file locking is unsupported by the Windows -> WSL share.
            # Load an unchanged temporary copy on the Windows local filesystem.
            with tempfile.TemporaryDirectory(prefix='camera-model-') as folder:
                weights = Path(folder) / 'weights.h5'
                shutil.copyfile(ROOT / 'model/67emotion_human.h5', weights)
                self.model.load_weights(str(weights))
            # Verify the actual weights and all custom layers before opening USB devices.
            result = self.model(np.zeros((1, 48, 48, 1), dtype=np.float32), training=False).numpy()
            if result.shape != (1, 7) or not np.isfinite(result).all():
                raise RuntimeError('El modelo no devuelve las siete clases esperadas.')

    def detect(self, frame):
        cv2, np = self.cv2, self.np
        height, width = frame.shape[:2]
        self.face_net.setInput(cv2.dnn.blobFromImage(frame, 1.0, (300, 300), (104, 177, 123)))
        detections = self.face_net.forward()
        faces = []
        for detection in detections[0, 0]:
            if detection[2] < 0.7:
                continue
            x1, y1, x2, y2 = (detection[3:7] * [width, height, width, height]).astype(int)
            x1, x2 = max(0, min(width, x1)), max(0, min(width, x2))
            y1, y2 = max(0, min(height, y1)), max(0, min(height, y2))
            if x2 <= x1 or y2 <= y1:
                continue
            faces.append((x1, y1, x2, y2))
        return faces

    def emotion(self, frame, box):
        if self.model is None:
            return ''
        x1, y1, x2, y2 = box
        face = self.cv2.cvtColor(frame[y1:y2, x1:x2], self.cv2.COLOR_BGR2GRAY)
        face = self.cv2.resize(face, (48, 48)).astype('float32')[None, :, :, None] / 255.0
        prediction = self.model(face, training=False).numpy()[0]
        index = int(self.np.argmax(prediction))
        return f'{CLASSES[index]} {prediction[index]:.0%} (estimacion)'
