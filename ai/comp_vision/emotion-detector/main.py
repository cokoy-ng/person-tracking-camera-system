import cv2
import imutils
import numpy as np
import time
import matplotlib.pyplot as plt
import tensorflow as tf

from tensorflow.keras.models import model_from_json, Sequential
from tensorflow.keras.preprocessing.image import img_to_array
from tensorflow.keras.utils import get_custom_objects

# ========== BlurLayer class EXACTLY as in training ========== 
@tf.keras.utils.register_keras_serializable()
class BlurLayer(tf.keras.layers.Layer):
    def __init__(self, **kwargs):
        super(BlurLayer, self).__init__(**kwargs)

    def build(self, input_shape):
        channels = input_shape[-1]
        blur_kernel = tf.constant([[1, 2, 1],
                                   [2, 4, 2],
                                   [1, 2, 1]], dtype=tf.float32)
        blur_kernel = blur_kernel / tf.reduce_sum(blur_kernel)
        blur_kernel = tf.reshape(blur_kernel, [3, 3, 1, 1])
        blur_kernel = tf.tile(blur_kernel, [1, 1, channels, 1])
        self.blur_filter = tf.Variable(initial_value=blur_kernel, trainable=False, name='blur_filter')

    def call(self, x):
        return tf.nn.depthwise_conv2d(x, self.blur_filter, strides=[1, 1, 1, 1], padding='SAME')

# ========== Register custom classes ========== 
get_custom_objects()['BlurLayer'] = BlurLayer
get_custom_objects()['Sequential'] = Sequential

# ========== Emotion configuration ========== 
classes = ['angry', 'disgust', 'fear', 'happy', 'neutral', 'sad', 'surprise']
colors = ['r', 'g', 'b', 'y', 'k', 'm', 'c']  # Valid list of colors
x = list(range(len(classes)))
y = [0.0] * len(classes)

# ========== Live plot configuration ========== 
plt.ion()
figure = plt.figure()

# ========== Face detector (Caffe model) ========== 
face_model_path = "face_detector"
prototxtPath = f"{face_model_path}/deploy.prototxt"
weightsPath = f"{face_model_path}/res10_300x300_ssd_iter_140000.caffemodel"
faceNet = cv2.dnn.readNet(prototxtPath, weightsPath)

# ========== Load emotion model ========== 
with open("model/67emotion_human.json", "r") as json_file:
    model_json = json_file.read()

emotionModel = model_from_json(model_json, custom_objects={
    "BlurLayer": BlurLayer,
    "Sequential": Sequential
})

emotionModel.load_weights("model/67emotion_human.h5")
print("✅ Model successfully loaded")

# ========== Emotion prediction function ========== 
def predict_emotion(frame, faceNet, emotionModel):
    blob = cv2.dnn.blobFromImage(frame, 1.0, (300, 300), (104.0, 177.0, 123.0))
    faceNet.setInput(blob)
    detections = faceNet.forward()

    faces, locs, preds = [], [], []

    for i in range(detections.shape[2]):
        confidence = detections[0, 0, i, 2]

        if confidence > 0.4:
            box = detections[0, 0, i, 3:7] * np.array([
                frame.shape[1], frame.shape[0],
                frame.shape[1], frame.shape[0]
            ])
            (Xi, Yi, Xf, Yf) = box.astype("int")
            Xi, Yi = max(0, Xi), max(0, Yi)

            face = frame[Yi:Yf, Xi:Xf]
            if face.size == 0:
                continue  # skip if the cropped face is invalid

            face = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
            face = cv2.resize(face, (48, 48))
            face_array = img_to_array(face)
            face_array = np.expand_dims(face_array, axis=0) / 255.0

            locs.append((Xi, Yi, Xf, Yf))
            pred = emotionModel.predict(face_array, verbose=0)
            preds.append(pred[0])

    return locs, preds

# ========== Start webcam ========== 
cam = cv2.VideoCapture(0, cv2.CAP_DSHOW)

if not cam.isOpened():
    print("❌ Failed to open webcam")
    exit()

prev_frame_time = 0

# ========== Main loop ========== 
while True:
    ret, frame = cam.read()
    if not ret or frame is None:
        print("⚠️ Failed to capture frame.")
        continue

    frame = imutils.resize(frame, width=640)
    locs, preds = predict_emotion(frame, faceNet, emotionModel)

    for (box, pred) in zip(locs, preds):
        (Xi, Yi, Xf, Yf) = box
        (angry, disgust, fear, happy, neutral, sad, surprise) = pred
        label = f"{classes[np.argmax(pred)]}: {np.max(pred) * 100:.0f}%"

        # Draw label and bounding box
        cv2.rectangle(frame, (Xi, Yi - 40), (Xf, Yi), (255, 0, 0), -1)
        cv2.putText(frame, label, (Xi + 5, Yi - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        cv2.rectangle(frame, (Xi, Yi), (Xf, Yf), (255, 0, 0), 2)

        # Update emotion bar plot
        y = [angry, disgust, fear, happy, neutral, sad, surprise]
        plt.clf()
        plt.xticks(x, classes)
        plt.grid(True)
        plt.ylim([0.0, 1.0])
        plt.bar(x, y, color=colors, width=0.8)
        figure.canvas.draw()

    # Calculate FPS
    new_frame_time = time.time()
    fps = 1 / (new_frame_time - prev_frame_time) if prev_frame_time != 0 else 0
    prev_frame_time = new_frame_time

    cv2.putText(frame, f"{int(fps)} FPS", (5, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)
    cv2.imshow("Emotion Detection", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# ========== Cleanup ========== 
cam.release()
cv2.destroyAllWindows()
