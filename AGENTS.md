# AGENTS.md

Guia para trabajar este proyecto en distintas maquinas y mantener contexto entre agentes/personas.

## Regla Principal

Cada cambio funcional, estructural, de dependencias, comandos de ejecucion o flujo de trabajo debe documentarse en este archivo antes de finalizar la tarea.

Si se agrega, mueve, elimina o cambia el proposito de una carpeta/archivo importante, actualizar la seccion correspondiente. Si se cambia como se instala o ejecuta el proyecto, actualizar los comandos.

## Resumen Del Proyecto

Este proyecto tiene dos modos:

- App de escritorio Python/OpenCV: se ejecuta con `python main.py`.
- MVP web local: frontend React captura la camara en el navegador y backend Python procesa pose/logica por WebSocket.

El modo escritorio debe conservarse funcionando aunque se agreguen funciones web.

## Estructura

```text
.
├── main.py                 # Entrada de la app escritorio OpenCV.
├── requirements.txt        # Dependencias Python compartidas.
├── AGENTS.md               # Guia viva del proyecto.
├── backend/                # Backend web FastAPI.
├── frontend/               # Frontend web React/Vite/TypeScript.
├── core/                   # Camara, pose engine, renderer OpenCV, video player.
├── games/                  # Logica/render de juegos escritorio.
├── utils/                  # Landmarks, matematicas, tracking de golpes.
├── assets/                 # Modelos y videos usados por los juegos.
└── venv/                   # Entorno virtual local, no versionar.
```

## Backend Python

Carpeta: `backend/`

- `backend/app.py`: crea la app FastAPI.
  - `GET /health`: verifica que el backend esta vivo.
  - `WS /ws/game`: canal realtime para frames/comandos del frontend y estado del juego.
  - `GET /assets/...`: sirve archivos de `assets/`.
- `backend/session.py`: coordina sesion web, decode de frames, `PoseEngine`, estado actual y respuestas JSON.
  - Durante pantallas finales de resumen acepta aplauso sostenido de 3.5s para volver al menu.
- `backend/web_menu.py`: version serializable del menu con la misma logica de `games/menu.py` (muneca sobre boton + aplauso sostenido).
- `backend/web_boxing.py`: version serializable de la logica de boxeo para React. Reutiliza constantes/reglas de `games/boxing.py` y expone targets, popups, ripples, esquive y metricas para el render web. No reemplaza `games/boxing.py`.
- `backend/web_pose_challenge.py`: version serializable de Yoga usando condiciones y tiempos de `games/pose_challenge.py`.
- `backend/web_aerobics.py`: version serializable de Aerobicos usando checkpoints y conteo de `games/aerobics.py`.

El backend reutiliza:

- `core.pose_engine.PoseEngine`
- constantes y reglas de `games.boxing`
- utilidades de `utils/`

## Frontend React

Carpeta: `frontend/`

- Stack: Vite + React + TypeScript.
- `frontend/src/App.tsx`: layout principal y loop de captura/envio de frames.
  - Muestra un indicador pequeno fijo arriba con los FPS aproximados de la camara.
  - En resumen final de Box/Yoga/Aerobico muestra progreso de aplauso sostenido para volver al menu.
- `frontend/src/hooks/useCamera.ts`: acceso a webcam con `getUserMedia`.
- `frontend/src/hooks/useGameSocket.ts`: WebSocket con el backend.
- `frontend/src/components/CameraCanvas.tsx`: render de camara, skeleton, targets y mensajes.
  - En Box tambien dibuja los efectos serializados por backend: entrada/hit de targets, ripples, popups y overlay/progreso de esquive.
- `frontend/src/components/MainMenu.tsx`: menu web visual tipo landing, pero usando el estado/rectangulos calculados por `backend/web_menu.py`.
- `frontend/src/components/TrainerVideo.tsx`: video de entrenamiento servido desde backend.
- `frontend/src/types.ts`: contrato TypeScript del estado recibido del backend.

MVP actual web:

- Menu con la misma interaccion de `games/menu.py`.
- Boxeo, Yoga y Aerobicos funcionan desde React con logica Python en backend.

## App Escritorio

Entrada: `main.py`

Flujo:

1. Abre camara con `core.camera.CameraCapture`.
2. Procesa pose con `core.pose_engine.PoseEngine`.
3. Mantiene estado entre menu, boxeo, yoga y aerobicos.
4. Renderiza todo con OpenCV usando `core.renderer`.
5. Muestra ventana con `cv2.imshow`.

Importante:

- No romper `python main.py`.
- No cambiar la logica de juego escritorio salvo que la tarea lo pida explicitamente.
- Si una regla se comparte con web, preferir extraer/adaptar con cuidado antes que duplicar grandes bloques.

## Juegos

Carpeta: `games/`

- `base_game.py`: interfaz comun de juegos escritorio.
- `menu.py`: menu controlado por munecas y aplauso.
- `boxing.py`: boxeo escritorio, objetivos, golpes, score, esquive y videos.
- `pose_challenge.py`: yoga/posturas.
- `aerobics.py`: aerobicos/repeticiones.

El web MVP solo migro boxeo mediante `backend/web_boxing.py`.

## Assets

Carpeta: `assets/`

- `assets/models/pose_landmarker_lite.task`: modelo MediaPipe.
- `assets/videos/box/`: videos de boxeo.
- `assets/videos/yoga/`: videos de yoga.
- `assets/videos/aerobicos/`: videos de aerobicos.

En modo web, FastAPI sirve estos archivos desde `/assets/...`.

## Instalacion En Una Maquina Nueva

Desde la raiz del proyecto:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --no-cache-dir -r requirements.txt
```

Si PowerShell bloquea scripts:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
```

Instalar frontend:

```powershell
cd frontend
npm.cmd install --cache .\.npm-cache
```

Usar `npm.cmd` en PowerShell si `npm` falla por politica de ejecucion.

## Como Ejecutar

Modo escritorio:

```powershell
.\venv\Scripts\Activate.ps1
python main.py
```

Backend web:

```powershell
.\venv\Scripts\Activate.ps1
uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000
```

Frontend web, en otra terminal:

```powershell
cd frontend
npm.cmd run dev -- --host 127.0.0.1
```

Abrir:

```text
http://127.0.0.1:5173
```

## Verificacion

Python:

```powershell
.\venv\Scripts\python.exe -m pip check
.\venv\Scripts\python.exe -m compileall -q backend core games utils
```

Frontend:

```powershell
cd frontend
npm.cmd run build
```

Backend health:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

## Git Y Archivos Que No Se Versionan

No versionar:

- `venv/`
- `__pycache__/`
- `*.pyc`
- `frontend/node_modules/`
- `frontend/dist/`
- `frontend/.npm-cache/`
- caches temporales

Si aparece una gran cantidad de cambios dentro de `venv/` o `node_modules/`, no son cambios del codigo del juego.

## Reglas Para Futuras Tareas

- Leer este archivo antes de modificar el proyecto.
- Mantener `main.py` funcionando salvo instruccion contraria.
- Documentar aqui cualquier cambio relevante.
- Preferir cambios pequenos y verificables.
- No borrar assets, videos, modelos ni archivos importantes sin permiso explicito.
- No recrear `venv/` o reinstalar dependencias salvo que sea necesario para la tarea.
- Si se agregan nuevas dependencias, actualizar `requirements.txt` o `frontend/package.json` y esta guia.
- Si se agrega un nuevo endpoint, comando o contrato WebSocket, documentarlo aqui.
- Si se migra Yoga o Aerobicos al frontend, actualizar las secciones de Backend, Frontend y Juegos.

## Historial De Cambios Documentados

- Se agrego arquitectura web MVP con `backend/` FastAPI y `frontend/` React/Vite/TypeScript.
- Se agrego WebSocket `/ws/game` para frames, comandos y estado del juego.
- Se agrego serving de assets desde FastAPI en `/assets/...`.
- Se agrego `backend/web_boxing.py` para boxeo serializable en React.
- Se agrego `backend/web_menu.py` y el frontend ahora usa la logica de hover con muneca + aplauso sostenido del menu escritorio.
- Se ajusto el menu web a una pantalla completa visual con tres disciplinas en fila, sin cambiar la logica de seleccion por muneca + aplauso.
- Se corrigio el layout del menu web para que use toda la pantalla sin superposiciones: se oculta el HUD del juego en menu, se separan titulo/texto/tarjetas y se bajan las zonas de seleccion.
- Se cambio el menu web para posicionar tarjetas y cursores por porcentajes reales de viewport derivados de las coordenadas 640x480 del backend, evitando que el contenido quede comprimido a la izquierda.
- Se ajusto el menu web para evitar superposiciones entre descripcion, prompts y puntos de color; las tarjetas bajaron y los puntos ahora se anclan al extremo derecho de cada disciplina.
- Se quitaron los puntos de color del menu web y se reajusto el espaciado vertical para separar titulo, descripcion y disciplinas.
- Se aumento el `line-height` del titulo principal del menu web para evitar que letras de lineas distintas se toquen.
- Se subieron el kicker y el titulo principal del menu web sin mover la frase descriptiva.
- Se corrigio el envio de comandos del frontend: `selectGame` y `sendCommand` ahora se envian inmediatamente por WebSocket, aunque la camara no este enviando frames.
- Se agrego una pantalla de transicion antes de cada modulo de boxeo: pausa el video, muestra cuenta regresiva de 5 segundos e instrucciones, y luego permite iniciar el entrenamiento sin cambiar la logica de deteccion.
- Se habilitaron los botones de Yoga y Aerobicos en web: backend serializa la logica de `pose_challenge.py` y `aerobics.py`, y React muestra paneles de progreso/condiciones/repeticiones.
- Se corrigio Yoga/Aerobicos en web para que el menu no se superponga al juego, usen la misma transicion de preparacion que Box y pausen la logica mientras corre el contador.
- Se cambio el modo de juego web a pantalla completa con dos mitades: video de entrenamiento a la izquierda y camara/canvas a la derecha, remapeando skeleton, targets y mensajes al tamano real del canvas.
- Se ajusto Aerobicos para mostrar una sola transicion inicial por video con la misma estructura de Box/Yoga: contador, titulo motivador y preview pequeno del video, sin pantallas entre modulos internos.
- Se cambio el escalado del canvas de camara en modo juego de `cover` a `contain` para evitar que los targets de Box y los landmarks se corten en los costados cuando la mitad de pantalla no tiene proporcion 4:3.
- Se cambio el escalado del video guia en Box, Yoga y Aerobico de `cover` a `contain` para evitar que se recorten manos, pies o cuerpo completo; el fondo queda negro cuando hay bandas.
- Se mantienen los videos originales de Yoga (`yoga1.mp4` a `yoga4.mp4`) en `assets/videos/yoga/`; no se normalizan a 4:3.
- Se agrego versionado automatico a las URLs de videos de Yoga en `backend/web_pose_challenge.py` usando fecha/tamano del archivo para evitar que el navegador mantenga en cache archivos con el mismo nombre.
- Se restauro paridad visual de Box web con `games/boxing.py`: radio de target desde la constante original, animacion de entrada del circulo, etiqueta visible despues de entrar y viraje a rojo al agotarse el tiempo, sin cambiar la deteccion de golpes.
- Se agrego un layout visual exclusivo para Box en frontend: video de entrenamiento a la izquierda, panel derecho oscuro con skeleton neon y targets existentes, mas HUD inferior tipo arcade; no se cambio la logica de `games/boxing.py`.
- Se conecto el HUD de Box a metricas reales del adaptador web: porcentaje inicia en 0 y sube solo con aciertos, combo se reinicia al fallar, hay evaluacion al final de cada video y resumen final con botones clickeables de menu/reintentar.
- Se corrigio `backend/session.py` para exponer el bloque `boxing` al frontend; sin esto el HUD/resumen de Box quedaba siempre en 0. El resumen final ahora muestra barras de porcentaje por modulo.
- Se corrigio la pantalla de resultado entre modulos de Box para que dure 7 segundos y luego permita continuar al mini contador del siguiente modulo; el temporizador ahora depende del id estable del resultado.
- Se bajo la pantalla de resultado entre modulos de Box a 4 segundos y se bloqueo el mini contador hasta que termine esa calificacion, evitando que ambas pantallas se superpongan.
- Se compacto la pantalla final de Box para que el mensaje principal, porcentajes, barras y botones de menu/reintentar entren completos en pantalla.
- Se ajustaron los rangos de calificacion final de Box: 0-59 `PUEDES HACERLO MEJOR`, 60-74 `BIEN`, 75-89 `MUY BIEN`, 90-100 `EXCELENTE`.
- Se agrego layout visual especial para Yoga: video guia a la izquierda, panel de camara/skeleton neon a la derecha, barra inferior de 10 segundos basada en `activity.progress`, y feedback simple de estabilidad sin el recuadro grande de condiciones.
- Se agrego puntuacion web para Yoga por opcion/lado segun segundos sostenidos de 10s, pantallas zen de resultado por postura/opcion, resumen final con puntaje total y frases de respiracion; no se cambio `games/pose_challenge.py`.
- Se bloqueo la reacumulacion de tiempo en Yoga para una opcion/lado ya puntuado, evitando duplicar puntos mientras el video aun no cambia al siguiente lado.
- Se corrigio el flujo de resultados de Yoga: completar 10s muestra solo un mensaje zen intermedio, el porcentaje del modulo aparece al terminar el video completo, y el resumen final espera a mostrar primero el resultado del ultimo modulo.
- Se quito la pantalla intermedia de Yoga al completar 10s para no cortar el video a mitad de movimiento; ahora solo se muestra puntaje al final de cada modulo completo. El boton Menu limpia overlays antes de volver al menu.
- Se ajusto la escala de puntos de Yoga web: modulo 1 vale 10, modulo 2 vale 20, modulo 3 vale 20 y modulo 4 vale 40; en modulos con dos lados el puntaje se divide entre opciones.
- Se corrigio el cierre del ultimo modulo de Yoga en web: `videoEnded` ahora conserva el tiempo real del video y ya no se ignora si la postura estaba en estado de exito, permitiendo mostrar el resumen final tras el modulo 4/4.
- Se ajusto el contador visible de puntos de Yoga para que muestre solo los puntos del modulo actual y se reinicie al pasar a la siguiente postura; el resumen final conserva el total acumulado.
- Se corrigio la validacion web de Yoga para que una opcion ya puntuada no bloquee el contador visual ni la deteccion de postura; se evita duplicar puntos, pero el hold vuelve a responder como en la logica original.
- Se agrego desglose visible de puntaje por lado en Yoga: los resultados de modulo y el resumen final muestran Lado A/B con sus puntos individuales, incluyendo 0 puntos si un lado no se completo.
- Se corrigio el avance entre modulos web tras `videoEnded`: la sesion ya no ejecuta un segundo `update()` con el tiempo del video anterior, evitando que el siguiente modulo de Yoga marque lados en 0 antes de comenzar. La pantalla de resultado ahora muestra porcentaje y puntos del modulo de forma explicita.
- Se corrigio el flujo final de Box en frontend: el resultado del ultimo modulo ahora se muestra antes del resumen final, en vez de saltar directo a la pantalla de porcentaje general.
- Se agrego un layout visual propio para Aerobico en frontend: video a la izquierda, panel de camara/skeleton a la derecha y HUD inferior tipo cardio, todo en amarillo fosforescente; tambien se cambio la transicion inicial de Aerobico de verde a amarillo.
- Se creo `assets/audio/aerobics/` para la musica de Aerobico. El frontend reproduce solo en Aerobico `/assets/audio/aerobics/aerobics.mp3`, sincronizando play/pausa con el video de entrenamiento.
- Se agrego audio corto para el contador inicial de Aerobico: `/assets/audio/aerobics/aerobics-countdown.mp3` suena durante la transicion de 5 segundos y luego inicia la musica principal sincronizada con el video.
- Se separo el HUD de Aerobico en barra superior tipo reproductor de musica y barra inferior de progreso de reps; al terminar el video ahora se muestra una pantalla final amarilla con porcentaje, pasos logrados y desglose por modulo.
- Se sincronizo la barra superior de musica de Aerobico con el audio real: el waveform se ilumina segun `currentTime / duration` de `aerobics.mp3` y muestra tiempo actual/duracion.
- Se aumento el alto del HUD de Aerobico y se separaron verticalmente contador, energia, waveform y barra de reps para evitar superposiciones.
- Se reajusto el menu principal: se agrego una mini pantalla de pose/camara para demostrar tracking activo, se reservo un bloque de logo arriba a la derecha y se redujo el ancho del texto para evitar cruces con la preview.
- Se creo `assets/images/logo/` para el logo del proyecto. El menu busca `/assets/images/logo/neofit-logo.png`; si no existe, muestra un placeholder. La mini pantalla del menu ahora usa fondo negro/neon y skeleton, no la camara clara directa.
- Se limpio el logo del menu quitando recuadro/fondo y se bajo la mini pantalla de tracking para evitar solapamientos.
- Se genero `assets/images/logo/neofit-logo-transparent.png` removiendo el fondo negro del logo y el menu ahora usa esa version transparente.
- Se creo `assets/audio/yoga/` para la musica de Yoga. El frontend reproduce `/assets/audio/yoga/yoga.mp3` durante todo el nivel de Yoga y no reinicia la musica al cambiar de modulo/postura.
- Se creo `assets/audio/boxing/` para la musica de Box. El frontend reproduce `/assets/audio/boxing/boxing.mp3` durante todo el nivel de Box y no reinicia la musica al cambiar de modulo/combo.
- Se creo `assets/audio/celebration/` para aplausos/ovacion. El frontend reproduce `/assets/audio/celebration/celebration.mp3` una vez cuando aparece la pantalla final de resultados de Box, Yoga o Aerobico.
- Se creo `assets/audio/menu/` para la musica del menu. El frontend espera `/assets/audio/menu/menu.mp3`, lo reproduce en loop en el menu, lo pausa durante los juegos y lo vuelve a usar despues de `celebration.mp3` en resultados sin reiniciarlo al volver al menu.
- Se ajustaron colores visuales del frontend: Box usa verde neon en HUD, resultados, resumen y contador de transicion; Yoga usa rosa neon en HUD, resultados, resumen, transicion y adornos del canvas, manteniendo el cambio de color del skeleton cuando la postura esta correcta.
- Se quito el porcentaje duplicado del lado izquierdo del HUD de Box; se mantiene solo la precision del lado derecho y la barra inferior de progreso.
- Se ajusto el menu principal para que las disciplinas usen colores por nivel: Box verde neon, Yoga rosa neon y Aerobico amarillo neon; tambien se aumento contraste, tamano y brillo de los textos descriptivos debajo de cada nombre.
- Se ajusto el texto blanco principal del menu para que use solo brillo directo tipo neon, sin recuadro ni luz de fondo de color.
- Se agrego un indicador pequeno fijo arriba de todo que muestra los FPS aproximados de la camara en frontend.
- Se completo la integracion web de Box para serializar y renderizar efectos que estaban en `games/boxing.py`: ripples, popups flotantes con alpha, halo de hit y overlay/progreso/resultado de esquive, manteniendo la deteccion y tiempos del juego original en backend.
- Se ajusto Yoga en `games/pose_challenge.py`: el modulo 2 `Inclinacion Lateral` ya no exige rodillas rectas en ninguna de sus dos opciones; web hereda el cambio mediante `backend/web_pose_challenge.py`.
- Se ajustaron las posiciones de los targets de gancho en `games/boxing.py`: `GANCHO_L` y `GANCHO_R` ahora aparecen un poco mas hacia el centro y mas arriba; web hereda el cambio desde `PUNCH_POS`.
- Se agrego salida por gesto en resumen web: al terminar Box, Yoga o Aerobico se puede volver al menu con aplauso sostenido de 3.5 segundos; `backend/session.py` detecta el gesto y `frontend/src/App.tsx` muestra la barra de progreso.
- Se puso el video guia de Box en modo espejo solo en frontend mediante CSS (`.appShell.boxingMode .trainerVideo { transform: scaleX(-1); }`), sin modificar los archivos MP4 ni afectar Yoga/Aerobico.
- Se simplificaron los mensajes finales de Yoga a `EXCELENTE`, `MUY BIEN`, `BIEN` y `PUEDES HACERLO MEJOR`; tambien se quitaron los botones de resumen final en Box/Yoga/Aerobico para dejar solo el regreso al menu por aplauso, enmarcado con el color de cada nivel.
- Se mantiene el modo escritorio con `python main.py`.
- Se agrego esta guia y la regla de mantenerla actualizada con cada cambio.
