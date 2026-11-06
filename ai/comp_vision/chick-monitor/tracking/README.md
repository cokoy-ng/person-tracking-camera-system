# IDs temporales y trayectorias

`temporary.py` asocia detecciones de forma geométrica, uno a uno, con centro
predicho por velocidad reciente, distancia e IoU. No usa identificación por aspecto
ni reconoce un animal de forma permanente. Un cruce u oclusión puede cambiar IDs.

- IDs crecientes por sesión del worker; no se reutilizan al perder una trayectoria.
- Confirmación tras dos observaciones consecutivas con menos de 0,75 s entre ellas.
- Retención máxima sin observar: 1 s. Las cajas perdidas no se devuelven al frontend.
- Trayectorias: hasta 24 observaciones y hasta 6 s; segmentos entre posiciones observadas.
- Cambios de geometría, retroceso del reloj o pausas de más de 1 s reinician asociación.
- Una pérdida de cámara o error de inferencia borra seguimiento y agrupamientos.

Los IDs reinician al reiniciar el worker, con una nueva `tracking_session`.
El total mostrado es visible, no un censo de animales únicos del lote. Los falsos
positivos del detector también pueden adquirir IDs: sigue siendo experimental.
