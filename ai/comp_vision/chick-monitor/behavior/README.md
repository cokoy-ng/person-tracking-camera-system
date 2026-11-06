# Cercanía, agrupamiento y zonas

`spatial.py` utiliza únicamente detecciones visibles con ID temporal confirmado.
No diagnostica enfermedades, interpreta causas térmicas ni gobierna el Arduino.

La distancia entre centros se calcula en píxeles y se divide por la diagonal de
la imagen. Es relativa, no distancia en centímetros ni contacto físico. No se ha
calibrado el plano del suelo. El vecino más cercano se publica para cada ID que
tenga otro ID confirmado visible.

Los pares a distancia menor o igual al umbral forman enlaces. Un grupo es una
componente conectada con al menos N IDs: no requiere que todos sus miembros estén
mutuamente dentro del umbral. Se marca sostenido al mantener el grupo durante el
tiempo configurado. Se conserva el grupo si la similitud Jaccard de miembros es
al menos 0,5 y no falta observación por más de 1 s. Perder el tamaño mínimo,
interrumpir observaciones o cambiar criterios reinicia duración. Puede cambiar
parte de sus miembros mientras el grupo sigue presente.

Valores iniciales: cercanía 12 % de diagonal, mínimo 3 IDs, persistencia 5 s.
Configurables en frontend: cercanía 3–40 %, mínimo 2–20 y persistencia 2–300 s.

`configuration.py` valida y guarda zonas rectangulares normalizadas para comedero,
bebedero y calefacción. Inicialmente no hay zonas: las dibuja el usuario sobre el
video y las guarda explícitamente. El conteo usa el centro de cada caja observada;
las zonas superpuestas pueden contar un mismo ID en ambas. Si se mueve la cámara,
se deben volver a dibujar. No se infiere que el ave coma, beba o reciba calor por
estar en una zona.

Persistencia: `backend/data/vision_config.json` (ignorado por Git, conservar).
Guardado atómico con revisión para rechazar escrituras de una pestaña antigua.
Un archivo existente dañado se conserva y se rechaza sobrescribirlo silenciosamente.
No se graban imágenes ni se crean históricos de trayectorias en esta etapa.
