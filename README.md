# Consola Multijuegos / NeoFit

Proyecto local con dos modos:

- App de escritorio Python/OpenCV: usa la camara directamente y abre una ventana con `cv2.imshow`.
- App web local: React captura la camara en el navegador y FastAPI procesa la logica de pose por WebSocket.

## Requisitos

- Python 3.10+ recomendado.
- Node.js y npm.
- Webcam disponible.
- Permiso de camara en el navegador.

## Instalacion

Desde la raiz del proyecto:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --no-cache-dir -r requirements.txt
```

Instalar el frontend:

```powershell
cd frontend
npm.cmd install --cache .\.npm-cache
```

Si PowerShell bloquea scripts, usa esta terminal solo para la sesion actual:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

## Ejecutar La Version Web

Terminal 1, backend:

```powershell
.\venv\Scripts\Activate.ps1
uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000
```

Terminal 2, frontend:

```powershell
cd frontend
npm.cmd run dev -- --host 127.0.0.1
```

Abrir en el navegador:

```text
http://127.0.0.1:5173
```

## Ejecutar La Version Escritorio

```powershell
.\venv\Scripts\Activate.ps1
python main.py
```

Presiona `Esc` para salir. Presiona `m` para volver al menu.

## Verificacion Rapida

Backend:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Frontend:

```powershell
cd frontend
npm.cmd run build
```

Python:

```powershell
.\venv\Scripts\python.exe -m compileall backend core games utils main.py
```

## Notas

- El backend sirve videos, audio, imagenes y modelo desde `/assets/...`.
- La version web usa `ws://127.0.0.1:8000/ws/game`.
- Para que el juego funcione, backend y frontend deben estar abiertos al mismo tiempo.
