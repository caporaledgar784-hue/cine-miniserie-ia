"""Audio de diálogos y narración con edge-tts (gratis, sin clave ni cuenta).

Cada personaje tiene su propia voz (ver personajes.py) y el narrador otra
distinta, para que los diálogos suenen a personas diferentes. Cada escena se
graba línea por línea y se une con pequeñas pausas entre réplicas, como en
una película. La duración del audio de la escena define cuánto dura la escena
en el video final.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys

PAUSA_ENTRE_LINEAS_SEG = 0.4


def _ruta_edge_tts() -> str:
    """El comando edge-tts del mismo entorno virtual que ejecuta este
    programa (si existe ahí); si no, el de la PATH del sistema."""
    candidato = os.path.join(os.path.dirname(sys.executable), "edge-tts")
    if os.path.exists(candidato):
        return candidato
    return "edge-tts"


def _sintetizar_biblioteca(texto: str, voz: str, ruta: str, velocidad: str) -> None:
    import edge_tts

    async def _main():
        comunicador = edge_tts.Communicate(texto, voz, rate=velocidad)
        await comunicador.save(ruta)

    asyncio.run(_main())


def _sintetizar_cli(texto: str, voz: str, ruta: str, velocidad: str) -> None:
    """Respaldo: usa el comando edge-tts si la biblioteca no está disponible."""
    archivo_texto = ruta + ".txt"
    with open(archivo_texto, "w", encoding="utf-8") as f:
        f.write(texto)
    try:
        cmd = [
            _ruta_edge_tts(),
            "--voice", voz,
            "--file", archivo_texto,
            "--write-media", ruta,
            f"--rate={velocidad}",
        ]
        resultado = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    finally:
        if os.path.exists(archivo_texto):
            os.remove(archivo_texto)
    if (
        resultado.returncode != 0
        or not os.path.exists(ruta)
        or os.path.getsize(ruta) == 0
    ):
        raise RuntimeError(f"edge-tts falló: {resultado.stderr[:300]}")


# Acentos de gTTS según la voz edge-tts pedida, para que el respaldo también
# suene distinto por personaje. Factores de tono (rubberband) por variante.
_TLD_POR_VOZ = {
    "es-MX": "com.mx",
    "es-ES": "es",
    "es-AR": "com.ar",
    "es-CO": "com.co",
    "es-US": "us",
    "es-CL": "cl",
    "es-PE": "com.pe",
}
_FACTORES_TONO = [1.0, 0.93, 1.07, 0.89, 1.12]


def _sintetizar_gtts(texto: str, voz: str, ruta: str) -> None:
    """Último respaldo: gTTS (Google, gratis, sin clave). La voz es única,
    así que se varía el acento (tld) y el tono (rubberband) por personaje.
    Prueba varios dominios de Google por si uno falla o tarda (cada intento
    con timeout de 15 s, para no colgarse nunca)."""
    import zlib

    from gtts import gTTS

    tld_preferido = "com.mx"
    for prefijo, valor in _TLD_POR_VOZ.items():
        if voz.startswith(prefijo):
            tld_preferido = valor
            break
    tlds = [tld_preferido, "com", "com.mx", "es"]
    tlds = list(dict.fromkeys(tlds))
    variante = zlib.crc32(voz.encode("utf-8")) % len(_FACTORES_TONO)
    factor = _FACTORES_TONO[variante]
    temporal = ruta + ".gtts.mp3"
    ultimo_error = None
    for tld in tlds:
        try:
            # timeout=15: sin él, una conexión atascada cuelga para siempre.
            gTTS(texto, lang="es", tld=tld, timeout=15).save(temporal)
            break
        except Exception as e:
            ultimo_error = e
            if os.path.exists(temporal):
                os.remove(temporal)
            continue
    else:
        raise RuntimeError(f"gTTS falló en todos los dominios: {ultimo_error}")
    if factor == 1.0:
        os.replace(temporal, ruta)
        return
    cmd = [
        "ffmpeg", "-y", "-i", temporal,
        "-af", f"rubberband=pitch={factor}",
        "-c:a", "libmp3lame", "-q:a", "4", ruta,
    ]
    resultado = subprocess.run(cmd, capture_output=True, text=True)
    os.remove(temporal)
    if resultado.returncode != 0 or not os.path.exists(ruta):
        raise RuntimeError(f"gTTS falló: {resultado.stderr[-300:]}")


def sintetizar_linea(texto: str, voz: str, ruta: str, velocidad: str = "-5%") -> str:
    """Sintetiza una línea de diálogo o narración. Devuelve la ruta del mp3.

    Cadena de respaldos (todos gratis, sin clave):
    1) biblioteca edge-tts, 2) comando edge-tts, 3) gTTS (acento + tono
    distintos por personaje). Si todo falla, lanza RuntimeError.
    """
    texto = " ".join(texto.split())
    if not texto:
        raise ValueError("Texto vacío para sintetizar.")
    os.makedirs(os.path.dirname(ruta) or ".", exist_ok=True)
    errores = []
    try:
        _sintetizar_biblioteca(texto, voz, ruta, velocidad)
    except Exception as e:
        errores.append(f"biblioteca edge-tts: {e}")
        try:
            _sintetizar_cli(texto, voz, ruta, velocidad)
        except Exception as e2:
            errores.append(f"comando edge-tts: {e2}")
            print(
                "  [Audio] edge-tts no disponible; uso gTTS como respaldo "
                "(voz menos natural, pero funciona)."
            )
            _sintetizar_gtts(texto, voz, ruta)
    if not os.path.exists(ruta) or os.path.getsize(ruta) == 0:
        raise RuntimeError(
            "No se generó audio para: " + texto[:60] + " | " + " | ".join(errores)
        )
    return ruta


def _crear_silencio(ruta: str, segundos: float = PAUSA_ENTRE_LINEAS_SEG) -> str:
    if os.path.exists(ruta):
        return ruta
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi", "-i",
        f"anullsrc=channel_layout=mono:sample_rate=24000",
        "-t", str(segundos), "-c:a", "libmp3lame", "-q:a", "4", ruta,
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return ruta


def duracion_audio(ruta: str) -> float:
    """Duración en segundos de un audio, medida con ffprobe."""
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", ruta,
    ]
    resultado = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return float(resultado.stdout.strip())
    except ValueError:
        return 0.0


def audio_escena(
    lineas: list,
    mapa_voces: dict,
    carpeta: str,
    prefijo: str,
    velocidad: str = "-5%",
) -> tuple[str, float]:
    """Genera el audio completo de una escena (diálogos + narración con sus
    voces) y lo devuelve como (ruta_mp3, duración_en_segundos)."""
    os.makedirs(carpeta, exist_ok=True)
    silencio = _crear_silencio(os.path.join(carpeta, "silencio.mp3"))
    archivos = []
    for i, linea in enumerate(lineas):
        tipo = linea.get("tipo", "narracion")
        if tipo == "dialogo":
            voz = mapa_voces.get(linea.get("personaje"), mapa_voces["NARRADOR"])
        else:
            voz = mapa_voces["NARRADOR"]
        ruta_linea = os.path.join(carpeta, f"{prefijo}_linea{i + 1:02d}.mp3")
        # Se regenera si no existe o quedó en 0 bytes (un intento cortado).
        if not os.path.exists(ruta_linea) or os.path.getsize(ruta_linea) == 0:
            sintetizar_linea(linea.get("texto", ""), voz, ruta_linea, velocidad)
        archivos.append(ruta_linea)
        archivos.append(silencio)
    lista = os.path.join(carpeta, f"{prefijo}_lista.txt")
    with open(lista, "w", encoding="utf-8") as f:
        for a in archivos:
            f.write(f"file '{os.path.abspath(a)}'\n")
    salida = os.path.join(carpeta, f"{prefijo}.mp3")
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lista,
        "-c:a", "libmp3lame", "-q:a", "4", salida,
    ]
    resultado = subprocess.run(cmd, capture_output=True, text=True)
    if resultado.returncode != 0:
        raise RuntimeError(f"No se pudo unir el audio de la escena: {resultado.stderr[-500:]}")
    return salida, duracion_audio(salida)


def estimar_duracion(texto: str) -> float:
    """Estimación de duración si no hay audio (aprox. 13 caracteres/segundo
    en español narrado). Mínimo 6 segundos por escena."""
    return max(6.0, len(texto) / 13.0)
