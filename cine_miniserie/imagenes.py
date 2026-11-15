"""Generación de imágenes con Pollinations keyless (gratis, sin clave ni cuenta).

Una imagen por vez, esperando 45 segundos entre llamadas (límite del plan
gratuito). Si se pasa el límite responde 402 con Retry-After; aquí se respeta
y se reintenta. La ficha fija de cada personaje se inyecta en el prompt de
todas las escenas donde aparece, para que no cambie de cara ni de ropa.
"""

from __future__ import annotations

import os
import time
import urllib.parse

import requests

URL_BASE = "https://image.pollinations.ai/prompt"
ESPERA_MINIMA_SEG = 45
TIMEOUT_SEG = 180
# Pollinations keyless genera hasta 768 px por lado; se pide 768x432 (16:9)
# y ffmpeg escala a 1280x720 al crear el segmento de video.
ANCHO_DEFECTO = 768
ALTO_DEFECTO = 432

_ultima_llamada = 0.0


def _respetar_espera() -> None:
    global _ultima_llamada
    ahora = time.time()
    falta = ESPERA_MINIMA_SEG - (ahora - _ultima_llamada)
    if falta > 0:
        time.sleep(falta)
    _ultima_llamada = time.time()


def construir_prompt_escena(
    prompt_base: str,
    fichas_personajes: list[str],
    estilo: str,
) -> str:
    """Prompt final de la escena: descripción + fichas fijas + estilo."""
    partes = [prompt_base.strip()]
    if fichas_personajes:
        partes.append(
            "Characters (keep the exact same face, age and clothes in every scene): "
            + "; ".join(fichas_personajes)
        )
    partes.append(estilo)
    partes.append("cinematic movie still, 16:9, no text, no watermark")
    return ", ".join(partes)


def generar_imagen(
    prompt: str,
    ruta_salida: str,
    ancho: int = ANCHO_DEFECTO,
    alto: int = ALTO_DEFECTO,
    modelo: str = "flux",
    semilla: int | None = None,
) -> str:
    """Genera una imagen con Pollinations y la guarda. Devuelve la ruta."""
    _respetar_espera()
    url = f"{URL_BASE}/{urllib.parse.quote(prompt)}"
    params = {
        "width": ancho,
        "height": alto,
        "model": modelo,
        "nologo": "true",
    }
    if semilla is not None:
        params["seed"] = semilla
    ultimo_error = None
    for intento in range(3):
        try:
            resp = requests.get(url, params=params, timeout=TIMEOUT_SEG)
        except requests.RequestException as e:
            ultimo_error = f"Error de red: {e}"
            time.sleep(10)
            continue
        if resp.status_code in (402, 429):
            espera = int(resp.headers.get("Retry-After", "60"))
            print(f"  [Pollinations] límite alcanzado, espero {espera}s y reintento...")
            time.sleep(min(max(espera, 5), 180))
            ultimo_error = f"HTTP {resp.status_code}: límite de Pollinations"
            continue
        if resp.status_code != 200:
            ultimo_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
            time.sleep(10)
            continue
        tipo = resp.headers.get("Content-Type", "")
        if "image" not in tipo:
            ultimo_error = f"La respuesta no es una imagen ({tipo}): {resp.text[:200]}"
            time.sleep(10)
            continue
        os.makedirs(os.path.dirname(ruta_salida) or ".", exist_ok=True)
        with open(ruta_salida, "wb") as f:
            f.write(resp.content)
        if os.path.getsize(ruta_salida) < 5000:
            ultimo_error = "Imagen demasiado pequeña, probablemente corrupta"
            time.sleep(5)
            continue
        return ruta_salida
    raise RuntimeError(f"No se pudo generar la imagen. {ultimo_error}")
