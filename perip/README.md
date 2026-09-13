# Cámara USB y servo desde Python

Punto de entrada para controlar ambos periféricos desde VS Code / WSL.
La cámara externa se selecciona por el nombre `USB 2.0 CAMERA`; no se elige
automáticamente la cámara HP ni la cámara virtual Camo.

## Arranque en una sola ejecución

```bash
/home/tucu/yo/camera/start.sh
```

Comprueba Python y las dependencias de Windows, instala las versiones faltantes,
prepara las variables y el entorno de WSL e inicia `tracking.py`. No necesitas
activar un entorno manualmente. Usa `start.sh --check` para validar solo entorno
y modelos, o `start.sh --setup-only` para preparar dependencias sin abrir
dispositivos. Las opciones de `tracking.py`, como `--no-servo` y `--reverse`,
se pueden pasar al lanzador.

La configuración opcional está en `.env` en la raíz, basada en `.env.example`.
Consulta [el README principal](../README.md#ejecutar-la-integración) para conocer
las variables, requisitos de sistema y modos de arranque.

## Usar la cámara

```bash
cd /home/tucu/yo/camera/perip
source .venv/bin/activate
python camera.py
```

Abre una ventana de Windows con video en vivo. En esa ventana, **Q** o **Esc**
cierran la cámara; **S** guarda una foto en `perip/captures/`. También se puede
cerrar la ventana o detener la terminal con Ctrl+C. No se graba video.

```bash
python camera.py --list
python camera.py --check
python camera.py --snapshot captures/foto.jpg
python camera.py --name "USB 2.0 CAMERA" --width 640 --height 480
python camera.py --seconds 10
```

`--check` verifica 30 fotogramas reales sin abrir una ventana. `--snapshot`
guarda una foto después de leer 10 fotogramas. La resolución solicitada depende
de lo que admita la cámara; se imprime la resolución recibida. Si hay cámaras
con el mismo nombre, usa `--list` y `--index N`. Los índices pueden cambiar al
reconectar dispositivos. Si la cámara no aparece o deja de entregar imágenes,
revisa el USB y cierra otras aplicaciones que puedan estar usándola.

## Usar el servo

En otra terminal con el mismo entorno:

```bash
cd /home/tucu/yo/camera/perip
source .venv/bin/activate
python servo.py --port COM3 --check
python servo.py --port COM3 --demo --cycles 3
python servo.py --port COM3 --angle 90
```

`servo.py` reutiliza el controlador de `../arduino/servo.py`, con señal en D2.
El firmware USB se conserva en `../arduino/firmware/servo_usb/servo_usb.ino`.
Un ángulo individual se mantiene un segundo y luego se libera. No ejecutes dos
controladores del servo a la vez. La cámara y el servo sí pueden usarse juntos,
porque son dispositivos distintos. Para control automático usa `tracking.py`.

## Rostro, modelo de IA y servo

```bash
cd /home/tucu/yo/camera/perip
source .venv/bin/activate
python tracking.py
```

Ejecuta en Windows los modelos del repositorio `../emotion-detector`, rama `dev`,
con la cámara `USB 2.0 CAMERA` y el servo D2 en COM3. Cierra antes `camera.py` y
cualquier demo del servo. La ventana muestra el rostro seleccionado y la
clasificación estimada de expresión facial; esa etiqueta no mide el estado
emocional de la persona ni decide el movimiento.

El rostro de mayor tamaño controla el ángulo por su posición horizontal en la
imagen: izquierda 0°, centro 45°, derecha 90°. Requiere tres detecciones
consecutivas, limita los cambios a 5° cada 150 ms y evita ajustes inferiores a
3°. Si no detecta un rostro durante un segundo, libera el servo. Q/Esc, cerrar
la ventana o Ctrl+C terminan la sesión y envían STOP. Espacio pausa o reanuda el
servo. Esto controla la posición del servo con una cámara fija; no implementa
un control de centrado para una cámara montada sobre el propio servo.

```bash
python tracking.py --no-servo              # IA y cámara solamente
python tracking.py --face-only             # Rostro y servo, sin expresiones
python tracking.py --reverse               # Invertir dirección
python tracking.py --seconds 30            # Prueba de 30 segundos
python tracking.py --check-models          # Cargar pesos, sin abrir dispositivos
```

También puedes ejecutar `python3 emotion-detector/run_camera.py` desde la raíz.
El `main.py` original del repositorio se conserva como referencia. La integración
usa `detector.py`, con rutas independientes del directorio de ejecución.

Para recrear el entorno de IA, ejecuta `python3 setup_ai.py` desde `perip`.
Usa Python 3.12 de Windows y `%LOCALAPPDATA%\camera-ai\venv`, con versiones compatibles en
`emotion-detector/requirements-windows.txt`. Se utiliza
[Keras 2 mediante tf-keras](https://keras.io/getting_started/) para cargar el
modelo existente. Pruebas de control: `python -m unittest discover -s perip`
desde la raíz del proyecto. El entorno de IA reside en el disco de Windows para
evitar la carga lenta de bibliotecas desde la carpeta compartida de WSL; el
código y los modelos siguen en este proyecto. `CAMERA_AI_PYTHON` permite indicar
otra ruta de ejecutable, usando el formato `/mnt/c/.../python.exe` desde WSL.

## Instalar o recrear entornos

Desde WSL:

```bash
cd /home/tucu/yo/camera/perip
python3 setup.py
source .venv/bin/activate
```

El instalador crea `.venv` para WSL y `.venv-win` para Windows. La captura usa
OpenCV en Windows porque los dispositivos USB están conectados a ese sistema.
El lanzador de WSL convierte las rutas y ejecuta el Python de `.venv-win`.
Los entornos y las fotos quedan excluidos de Git. No hace falta abrir Arduino IDE.

Referencias de implementación: [captura con OpenCV](https://docs.opencv.org/4.12.0/dd/d43/tutorial_py_video_display.html)
y [enumeración por nombre e índice](https://github.com/lukehugh/cv2_enumerate_cameras).
