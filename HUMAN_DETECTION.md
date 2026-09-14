# Rostros, personas y servo

`bash start.sh --port COM3` ejecuta los dos detectores en la misma cámara y controla
el mismo servo. Cierra cualquier ejecución anterior con Ctrl+C antes de iniciar.
Los rostros aparecen en verde y las personas en azul. El texto indica el objetivo.
Se selecciona el rostro de mayor área; si no hay rostros, la persona de mayor área.
No identifica personas ni conserva la identidad del objetivo entre fotogramas.
El servo usa el centro horizontal elegido, conserva sus límites, pasos de cinco
grados y confirmación de tres fotogramas. Si pierde el objetivo, envía STOP tras
un segundo. Espacio pausa el servo; Q/Esc cierra la aplicación.

```bash
bash start.sh --check                  # Carga los tres modelos sin abrir dispositivos
bash start.sh --no-servo               # Rostros, expresiones y personas sin servo
bash start.sh --no-humans --port COM3   # Comportamiento anterior: rostros y expresiones
bash start.sh --face-only --port COM3   # Solo rostros, sin expresiones ni personas
```

El repositorio original se clonó en `human-detector/`:
https://github.com/chuanqi305/MobileNet-SSD

Revisión: `bb17b6c3eef36d80be441ae8e5339be66e8e3b7a` (licencia MIT, incluida en el clon).
Se usan `deploy.prototxt` y `mobilenet_iter_73000.caffemodel` mediante OpenCV DNN.
El adaptador está en `perip/human_detector.py`; filtra la clase VOC 15 (persona)
con confianza mínima 0.5. No requiere instalar Caffe ni nuevas dependencias.
Es un modelo ligero antiguo; puede fallar con oclusiones, poca luz o personas pequeñas.
Ejecutar ambos detectores puede reducir los fotogramas por segundo.

Para recuperar el clon en otra instalación:

```bash
git clone https://github.com/chuanqi305/MobileNet-SSD.git human-detector
git -C human-detector checkout bb17b6c3eef36d80be441ae8e5339be66e8e3b7a
```
