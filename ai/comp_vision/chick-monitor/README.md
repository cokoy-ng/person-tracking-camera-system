# Visión del criadero: detección de pollitos

Localiza aves con recuadros, confianza y conteo de detecciones, IDs temporales,
trayectorias cortas, agrupamientos y ocupación de zonas configurables sobre el
video de http://localhost:5173. El modelo está **en evaluación**:
no está validado para pollitos recién nacidos y puede confundir objetos del montaje.

## Organización

- `detector/`: adaptador YOLOv8 con coordenadas normalizadas.
- `tracking/`: asociación geométrica con IDs temporales y trayectorias de hasta 6 s.
- `behavior/`: cercanía relativa, agrupamientos persistentes y ocupación de zonas.
- `models/`: pesos verificados y procedencia con revisión y SHA256.
- `evaluation/`: preparación del entorno, prueba sobre imágenes y resultados observados.
- `worker.py`: proceso de inferencia independiente de la captura y del Arduino.

## Modelo y procedencia

Se utiliza únicamente `weights/best.pt` de
[drcardinal/chicken-detector](https://github.com/drcardinal/chicken-detector), revisión
`1f22e8083f7e6109edd47c5ef17f735a7241af05`, renombrado como
`models/chicken-yolov8n.pt`. Su clase es `chicken`; se presenta en español como
posibles pollitos. Procedencia y hash están en `models/provenance.json`.

El checkpoint declara AGPL-3.0 de Ultralytics. El repositorio original no publica
una licencia principal; esta integración no incorpora su aplicación Streamlit ni
presupone que todos sus archivos compartan la licencia del checkpoint. El adaptador
local se escribió para esta aplicación. No se usa `best_seg.pt` ni su clasificación
de comportamientos/enfermedades.

## Preparación e inicio

Ejecutar una vez `evaluation/setup_windows.py` con Python 3.12 de Windows. Crea
`%LOCALAPPDATA%/chick-monitor/venv`, instala PyTorch CPU y las versiones de
`requirements-windows.txt`, y descarga el modelo de revisión fija. Verifica SHA256
antes de cargarlo. No modifica los entornos de cámara, sensores o expresiones.

Después usar desde WSL:

```bash
./sh/monitoreo_pollitos.sh
./sh/monitoreo_pollitos.sh --estado
./sh/monitoreo_pollitos.sh --stop
```

Pulsar **Ver cámara** en el dashboard. Se muestran recuadros con confianza, conteo
estimado visible y FPS/tiempo de inferencia. El video sigue mostrando su flujo
original mientras el proceso de visión analiza la imagen más reciente. Los
recuadros corresponden al último análisis reciente; los IDs no garantizan identidad
permanente ni un censo del lote. Se retiran al perder datos o superar 1,5 s de edad.
Una pérdida del detector se muestra como ausencia de resultado, nunca como cero aves.

## Funcionamiento

`scrips/vision_pollitos.py` gestiona el proceso. Puede configurarse otro Python con
`CHICK_VISION_PYTHON` (ruta Windows). Logs: `.runtime/vision.log`.

El capturador mantiene un único lector USB y entrega el último JPEG por
`127.0.0.1:8766/frame?after=<secuencia>`. El worker solicita imágenes nuevas,
infiere en CPU y publica JSON en `127.0.0.1:8767/status`, solo en Windows local.
No acumula imágenes pendientes ni escribe fotogramas por disco. El backend expone
`GET /api/vision`; React consulta resultados mientras la cámara está desplegada.
Los modelos y el procesamiento de visión viven en esta carpeta; los auxiliares de
servicios están en `scrips/`, y la presentación en `frontend/`.

Umbral de confianza: 0,4; NMS IoU: 0,45; entrada del modelo: 640; máximo: 100
detecciones. Reescalar una imagen de la webcam a 640 no añade detalle al original
320×240. La cámara actual sigue limitada a aproximadamente 4 FPS. Ningún resultado
visual envía órdenes al Arduino ni altera referencias, bomba, puerta o calefacción.

## IDs, agrupamiento y zonas

Los números de los recuadros son IDs temporales; `?` indica una asociación aún
sin confirmar. Las líneas de colores son trayectorias y las líneas verdes unen
vecinos próximos. Los grupos muestran miembros, duración y si el agrupamiento
es sostenido. En **IDs y vecino más cercano** se muestra separación como porcentaje
de diagonal. No son centímetros ni diagnósticos de frío o enfermedad.

Para zonas: **Configurar zonas y cercanía → Dibujar Comedero/Bebedero/Calefacción**,
arrastra un rectángulo sobre el video y pulsa **Guardar configuración**. También
puedes ajustar cercanía, mínimo de IDs y persistencia. **Cancelar** descarta la
vista previa. No se asignan zonas automáticamente. Los conteos usan centros de
IDs confirmados visibles, no acumulados ni tiempos de consumo.

`GET/POST /api/vision/config` comunica con `/config` del worker. La configuración
persiste en `backend/data/vision_config.json`, independiente del control climático.
Revisiones evitan sobrescribir cambios de otra pestaña; guardar reinicia temporizadores
de grupos. Ver [seguimiento](tracking/README.md) y [análisis espacial](behavior/README.md).

## Evaluación

`evaluation/predict_image.py <imagen>` ejecuta una prueba explícita y muestra JSON;
no sustituye ni publica resultados de prueba en la cámara en vivo.

Se requiere evaluar imágenes del criadero con pollitos reales, diversos fondos,
iluminación, tamaños y oclusiones. Revisar falsos positivos, omisiones, conteo y
latencia antes de interpretar el conteo como una medida fiable. Las observaciones
iniciales están en `evaluation/SMOKE_TEST.md`.
