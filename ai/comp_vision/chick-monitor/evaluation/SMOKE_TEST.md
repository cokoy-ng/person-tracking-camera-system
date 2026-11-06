# Comprobación inicial del detector

Fecha: 2026-11-06. Modelo y hash: `../models/provenance.json`.

Pruebas ejecutadas sobre imágenes independientes del flujo de cámara:

| Entrada | Resultado observado | Inferencia después de calentamiento |
|---|---|---|
| Imagen pública `img/frame00001.png`, 1920×1080 | 25 detecciones, umbral 0,4 | 77,0 ms |
| Captura del dashboard con objetos del montaje y sin aves | 1 falso positivo, confianza 0,8912 | 80,9 ms |

Fuente de la imagen de aves:
[Chicken-Behavior-Analysis, revisión 1f1bab3](https://github.com/TaherehZarratEhsan/Chicken-Behavior-Analysis/blob/1f1bab335e76ba588359ab5ce8a71c6cc0e12b0a/img/frame00001.png).
Se descargó solo como muestra temporal en `.runtime/`, sin incorporarla a un
dataset ni usarla para entrenamiento. Estas cifras no representan precisión,
recall ni exactitud de conteo: no se hizo anotación de referencia de las imágenes.

El falso positivo confirma que la confianza del modelo no equivale a probabilidad
calibrada de que haya un pollito. Hace falta evaluación con negativos del montaje
y con recién nacidos antes de validar la función. No se ha entrenado ni afinado
el modelo y no se ha medido exactitud en pollitos recién nacidos.

## Integración web verificada

Chrome Windows: API real `GET /api/vision` devolvió resultados recientes, 4,1 FPS
de análisis y 79,3 ms por inferencia en una muestra. Con IA activa, el navegador
recibió 51 imágenes en aproximadamente 12 s: 4,09 FPS; retraso captura→navegador
p95 8,30 ms y máximo 265,49 ms (sin incluir exposición del sensor).

Se verificaron recuadros y conteo con datos de prueba limitados a la página del
navegador de pruebas, alineación de coordenadas normalizadas, retiro de resultados
caducados y retorno a resultados reales. Las pruebas no sustituyeron imágenes ni
resultados en el servicio de producción. Vista móvil 390 px sin desborde; ver/ocultar,
reapertura y recuperación de conexión correctos; Arduino siguió conectado.
54 pruebas backend y build/lint frontend correctos.

## IDs, agrupamientos y zonas

Segunda etapa, 2026-11-06: 67 pruebas backend correctas. Incluyen asociación uno a
uno, orden de detección cambiado, desapariciones sin cajas fantasma, expiración,
trayectorias acotadas, distancias con aspecto de imagen, grupos conectados,
persistencia continua sin sumar pérdidas de observación, centros de zonas,
guardado atómico, conflictos de revisión y protección de archivos dañados.

Chrome Windows verificó un ID real de la captura y el editor real de zonas:
dibujar mediante puntero, guardar, leer y rechazar revisión antigua con409. Se
restauraron las zonas originales sin posiciones de prueba. Un fixture limitado
a la página del navegador probó tres IDs, trayectorias, enlaces, grupo sostenido,
conteo por zona, vecino más cercano y retiro por caducidad. El fixture no se
publicó en API ni reemplazó resultados de producción.

Vista móvil390sin desborde ni erroresJS. Video con seguimiento y navegador activos:
35 imágenes en~10s,3.93FPS,máxima separación observada0.95s. En una consulta real,
el análisis reportó2.0FPS y151.9ms por inferencia; son métricas de ese intervalo,
no garantías de rendimiento. Arduino siguió conectado. No se ha validado todavía
la estabilidad de IDs ni precisión de grupos con pollitos reales.
