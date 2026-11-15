"""Segmentos de video por escena.

Por defecto: MOVIMIENTO CINEMATOGRÁFICO (gratis, ilimitado). La imagen de la
escena se mueve con un zoom/pan lento (efecto Ken Burns) durante exactamente
lo que dura su audio, así cada escena es larga y la duración la marca el
diálogo, no un clip de 5 segundos.

OPCIONAL: clips de movimiento real con fal.ai, Magic Hour o FreeLLMAPI. Solo
se usan si el usuario configuró la clave en variables de entorno. Si el
servicio falla o no hay clave, se usa el movimiento cinematográfico y se avisa.
Nunca hay claves en el código.
"""

from __future__ import annotations

import json
import os
import subprocess
import time

import requests


def _correr_ffmpeg(cmd: list, descripcion: str) -> None:
    resultado = subprocess.run(cmd, capture_output=True, text=True)
    if resultado.returncode != 0:
        raise RuntimeError(
            f"{descripcion} falló: {resultado.stderr.strip()[-600:]}"
        )


def segmento_cinematografico(
    imagen: str,
    duracion: float,
    salida: str,
    direccion: str = "acercar",
    fps: int = 25,
    ancho: int = 1280,
    alto: int = 720,
) -> str:
    """Crea un segmento de video desde una imagen fija con zoom/pan lento.

    La imagen se escala a 2560 px de ancho y zoompan la recorre; la duración
    es exacta (tantos fotogramas como duracion*fps). La dirección alterna
    entre escenas para que el movimiento no se sienta repetitivo.
    """
    duracion = max(duracion, 1.0)
    frames = max(int(round(duracion * fps)), fps)
    if direccion == "alejar":
        zoom = f"max(1.18-0.0009*on,1.0)"
    else:
        zoom = f"min(1+0.0009*on,1.18)"
    filtro = (
        f"scale=2560:1440,"
        f"zoompan=z='{zoom}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        f":d={frames}:s={ancho}x{alto}:fps={fps}"
    )
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-framerate", "1", "-i", imagen,
        "-vf", filtro,
        "-frames:v", str(frames),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps),
        "-an", salida,
    ]
    _correr_ffmpeg(cmd, f"Segmento cinematográfico de {imagen}")
    return salida


# ---------------------------------------------------------------------------
# Movimiento real (OPCIONAL). Cada proveedor lee su clave de variables de
# entorno. Estas funciones no se probaron sin clave: son el camino preparado
# para quien quiera pagar o usar su propio servidor.
# ---------------------------------------------------------------------------

def _clip_magic_hour(imagen: str, prompt: str, duracion: int) -> str:
    """Magic Hour: sube la imagen, crea el clip y espera a que termine."""
    clave = os.environ.get("MAGIC_HOUR_API_KEY", "")
    if not clave:
        raise RuntimeError("Falta MAGIC_HOUR_API_KEY en las variables de entorno.")
    base = "https://api.magichour.ai"
    headers = {"Authorization": f"Bearer {clave}", "Content-Type": "application/json"}
    # 1. URL de subida
    r = requests.post(
        f"{base}/v1/files/upload-urls",
        headers=headers,
        json={"files": [{"content_type": "image/jpeg", "file_name": os.path.basename(imagen)}]},
        timeout=60,
    )
    r.raise_for_status()
    subida = r.json()["urls"][0]
    with open(imagen, "rb") as f:
        requests.put(subida["upload_url"], data=f.read(), timeout=120).raise_for_status()
    ruta = subida["file_path"]
    # 2. Crear el clip (modelo barato, 5 s, 480p en el plan gratuito)
    r = requests.post(
        f"{base}/v1/image-to-video",
        headers=headers,
        json={
            "assets": {"image_file_path": ruta},
            "model": "ltx-2.5",
            "end_seconds": min(duracion, 5),
            "resolution": "480p",
            "audio": False,
            "name": "escena",
        },
        timeout=60,
    )
    r.raise_for_status()
    proyecto = r.json()["id"]
    # 3. Esperar (hasta 10 minutos)
    for _ in range(60):
        time.sleep(10)
        r = requests.get(f"{base}/v1/video-projects/{proyecto}", headers=headers, timeout=60)
        r.raise_for_status()
        datos = r.json()
        if datos.get("status") == "complete":
            return datos["downloads"][0]["url"]
        if datos.get("status") in ("failed", "error"):
            raise RuntimeError(f"Magic Hour falló: {datos}")
    raise RuntimeError("Magic Hour tardó demasiado; intenta de nuevo.")


def _clip_fal(imagen_url: str, prompt: str, duracion: int) -> str:
    """fal.ai: envía la imagen (debe ser una URL pública) y espera el clip."""
    clave = os.environ.get("FAL_API_KEY", "")
    if not clave:
        raise RuntimeError("Falta FAL_API_KEY en las variables de entorno.")
    modelo = os.environ.get("FAL_MODEL", "fal-ai/minimax/hailuo-07/image-to-video")
    headers = {"Authorization": f"Key {clave}", "Content-Type": "application/json"}
    r = requests.post(
        f"https://queue.fal.run/{modelo}",
        headers=headers,
        json={"image_url": imagen_url, "prompt": prompt, "duration": str(min(duracion, 10))},
        timeout=60,
    )
    r.raise_for_status()
    estado_url = r.json()["status_url"]
    for _ in range(60):
        time.sleep(10)
        r = requests.get(estado_url, headers=headers, timeout=60)
        r.raise_for_status()
        datos = r.json()
        if datos.get("status") == "COMPLETED":
            return datos["video"]["url"]
        if datos.get("status") == "FAILED":
            raise RuntimeError(f"fal.ai falló: {datos}")
    raise RuntimeError("fal.ai tardó demasiado; intenta de nuevo.")


def _clip_freellmapi(imagen: str, prompt: str, duracion: int) -> str:
    """FreeLLMAPI (tu propio servidor): /v1/videos/generations estilo OpenAI."""
    base = os.environ.get("FREELLMAPI_URL", "http://localhost:3001").rstrip("/")
    clave = os.environ.get("FREELLMAPI_KEY", "")
    if not clave:
        raise RuntimeError("Falta FREELLMAPI_KEY en las variables de entorno.")
    import base64

    with open(imagen, "rb") as f:
        imagen_b64 = base64.b64encode(f.read()).decode()
    r = requests.post(
        f"{base}/v1/videos/generations",
        headers={"Authorization": f"Bearer {clave}", "Content-Type": "application/json"},
        json={
            "prompt": prompt,
            "image": f"data:image/jpeg;base64,{imagen_b64}",
            "duration": min(duracion, 10),
        },
        timeout=600,
    )
    r.raise_for_status()
    datos = r.json()
    url = datos.get("data", [{}])[0].get("url") or datos.get("url")
    if not url:
        raise RuntimeError(f"FreeLLMAPI no devolvió video: {str(datos)[:300]}")
    return url


def _descargar(url: str, salida: str) -> str:
    r = requests.get(url, timeout=300)
    r.raise_for_status()
    with open(salida, "wb") as f:
        f.write(r.content)
    return salida


def segmento_escena(
    imagen: str,
    prompt_movimiento: str,
    duracion: float,
    salida: str,
    movimiento: str = "cinematografico",
    proveedor: str = "magic-hour",
    direccion: str = "acercar",
    fps: int = 25,
    ancho: int = 1280,
    alto: int = 720,
) -> str:
    """Segmento de una escena: intenta clip real si se pidió y hay clave;
    si no, movimiento cinematográfico (siempre funciona, gratis)."""
    if movimiento == "real":
        try:
            if proveedor == "magic-hour":
                url = _clip_magic_hour(imagen, prompt_movimiento, int(duracion))
            elif proveedor == "fal":
                url = _clip_fal(imagen, prompt_movimiento, int(duracion))
            elif proveedor == "freellmapi":
                url = _clip_freellmapi(imagen, prompt_movimiento, int(duracion))
            else:
                raise RuntimeError(f"Proveedor desconocido: {proveedor}")
            _descargar(url, salida)
            print(f"  [Video] clip real listo ({proveedor})")
            return salida
        except Exception as e:
            print(f"  [Video] clip real no disponible ({e}). Uso movimiento cinematográfico.")
    return segmento_cinematografico(
        imagen, duracion, salida, direccion=direccion, fps=fps, ancho=ancho, alto=alto
    )
