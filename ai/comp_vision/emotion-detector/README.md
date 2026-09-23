# Real-Time Emotion Detection using CNN and OpenCV

## Integración local con cámara USB y servo (rama dev)

Desde `/home/tucu/yo/person-tracking-camera-system` ejecuta `python3 emotion-detector/run_camera.py`.
Usa la cámara `USB 2.0 CAMERA` y Arduino COM3/D2 mediante el entorno Windows
`%LOCALAPPDATA%\camera-ai\venv`. Consulta [las instrucciones de perip](../perip/README.md)
para instalarlo, invertir el servo o ejecutar solo la detección.

`detector.py` reutiliza los pesos originales con Keras 2 compatible con Python
3.12. `requirements-windows.txt` corresponde a esta integración; los requisitos
y el `main.py` originales se conservan debajo como referencia.

This project implements a real-time facial emotion detection system using a convolutional neural network (CNN) model trained on the FER2013 dataset. It combines OpenCV for face detection and Matplotlib for live emotion probability visualization.

---

## Project Structure

```

emotion-detector/
│
├── face\_detector/                          # Pre-trained face detection model (Caffe)
│   ├── deploy.prototxt                     # Model architecture definition
│   ├── res10\_300x300\_ssd\_iter\_140000.caffemodel  # Model weights
│   └── z\_links.txt                         # Optional: download links or reference
│
├── model/                                  # Emotion classification model
│   ├── 67emotion\_human.h5                  # CNN model weights
│   └── 67emotion\_human.json                # CNN model architecture
│
├── main.py                                 # Main script for real-time emotion detection
│
├── requirements.txt                        # Python dependencies
│
└── README.md                               # Documentation and instructions

````

---

## Features

- Real-time face detection using OpenCV and SSD model (Caffe).
- Emotion classification: `angry`, `disgust`, `fear`, `happy`, `neutral`, `sad`, `surprise`.
- Live Matplotlib bar chart showing emotion probabilities.
- FPS and emotion label overlay on webcam video.

---

## Requirements

- Python **3.10.11**
- Windows 10/11 (tested on PowerShell)
- Working webcam
- Virtual environment (`venv`)

---

## Installation and Running (Windows 10/11)

### 1. Clone the repository

```bash
git clone https://github.com/your-user/emotion-detector.git
cd emotion-detector
````

### 2. Create a virtual environment

```powershell
python -m venv venv310
```

### 3. Activate the virtual environment

```powershell
.\venv310\Scripts\Activate
```

### 4. Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

> If you're not using a GPU, TensorFlow will fall back to CPU. You can ignore `cudart64_110.dll` or `nvcuda.dll` warnings unless you're setting up CUDA.

### 5. Run the system

```bash
python main.py
```

Press `q` to exit the camera feed.

---

## Models Used

* **Face Detector**: `res10_300x300_ssd_iter_140000.caffemodel` based on Single Shot Detector with Caffe.
* **Emotion Detector**: Custom CNN model using a `BlurLayer`, trained on FER2013 dataset.

  * `67emotion_human.json` – model architecture
  * `67emotion_human.h5` – model weights

---

## Visualization

* Detected faces are outlined with bounding boxes and labeled with the predicted emotion + confidence.
* A real-time **bar chart** shows the probabilities of all 7 emotions per frame.

---

## Windows-Specific Notes

* Webcam initialized with `cv2.VideoCapture(0, cv2.CAP_DSHOW)` for better compatibility.
* Run from PowerShell or CMD, not from within VS Code’s Run button.
* Ensure no other app is using the webcam.
* TensorFlow CPU is used by default; no GPU or CUDA is required.

---

## License

MIT License – free to use, modify, and redistribute for educational or research purposes.

---

## Credits

* Inspired by [David Revelo Luna](https://www.youtube.com/channel/UCr_dJOULDvSXMHA1PSHy2rg) (https://github.com/DavidReveloLuna/Face_Emotion) 
* Adapted and improved by **Plinior Zavala** with emotion graphing, cleaner structure, and Windows compatibility.
