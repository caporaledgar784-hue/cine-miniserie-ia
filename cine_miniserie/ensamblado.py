"""Ensamblado final: las escenas se unen SIN que se vean los cortes.

Video: fundidos cruzados (ffmpeg xfade) entre escena y escena.
Audio: fundido cruzado de audio (acrossfade) para que la narración y los
diálogos sigan de corrido. El resultado es UN solo video, como una película.

Opcional: portada con el título al inicio (3 s), unida con el mismo fundido.
"""

from __future__ import annotations

import os
import subprocess

# Fuentes que se buscan, en orden. En Windows suele estar arial.ttf.
FUENTES_POSIBLES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]


def _buscar_fuente() -> str | None:
    for ruta in FUENTES_POSIBLES:
        if os.path.exists(ruta):
            return ruta
    return None


def offsets_fundido(duraciones: list[float], fundido: float) -> tuple[list[float], float]:
    """Offsets de cada xfade y duración total del video unido.

    Ejemplo: duraciones [10, 10, 10], fundido 1 -> offsets [9, 18], total 28.
    """
    offsets = []
    acumulado = 0.0
    for i, d in enumerate(duraciones[:-1]):
        acumulado += d
        offsets.append(acumulado - fundido * (i + 1))
    total = sum(duraciones) - fundido * max(len(duraciones) - 1, 0)
    return offsets, total


def duracion_video(ruta: str) -> float:
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", ruta,
    ]
    resultado = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return float(resultado.stdout.strip())
    except ValueError:
        return 0.0


def crear_portada(
    titulo: str,
    subtitulo: str,
    salida: str,
    duracion: float = 3.0,
    ancho: int = 1280,
    alto: int = 720,
    fps: int = 25,
) -> str | None:
    """Portada negra con el título en dorado. Devuelve None si no hay fuente."""
    fuente = _buscar_fuente()
    if not fuente:
        print("  [Portada] no encontré fuente; se omite la portada.")
        return None
    titulo = titulo.replace(":", " -").replace("'", "")
    subtitulo = subtitulo.replace(":", " -").replace("'", "")
    filtro = (
        f"drawtext=fontfile={fuente}:text='{titulo}':fontsize=64:"
        f"fontcolor=gold:x=(w-text_w)/2:y=(h-text_h)/2-40,"
        f"drawtext=fontfile={fuente}:text='{subtitulo}':fontsize=32:"
        f"fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2+60,"
        f"fade=t=in:st=0:d=0.8,fade=t=out:st={duracion - 0.8}:d=0.8"
    )
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi", "-i",
        f"color=c=black:s={ancho}x{alto}:r={fps}:d={duracion}",
        "-vf", filtro,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps),
        "-an", salida,
    ]
    resultado = subprocess.run(cmd, capture_output=True, text=True)
    if resultado.returncode != 0:
        print(f"  [Portada] no se pudo crear: {resultado.stderr[-300:]}")
        return None
    return salida


def _audio_silencio(ruta: str, duracion: float) -> str:
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi", "-i",
        "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-t", str(duracion), "-c:a", "aac", "-b:a", "128k", ruta,
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return ruta


def ensamblar(
    segmentos_video: list[str],
    audios_escena: list[str],
    salida: str,
    fundido: float = 1.0,
    titulo: str = "",
    subtitulo: str = "Una miniserie creada con Cine Miniserie IA",
    fps: int = 25,
) -> dict:
    """Une los segmentos con xfade + acrossfade y guarda el video final.

    segmentos_video y audios_escena van en el mismo orden (uno por escena).
    Si se pide portada, se añade como primera escena con audio en silencio.
    Devuelve {"ruta": ..., "duracion_seg": ..., "num_escenas": ...}.
    """
    if len(segmentos_video) != len(audios_escena):
        raise ValueError("El número de videos y de audios no coincide.")
    if not segmentos_video:
        raise ValueError("No hay escenas para ensamblar.")

    videos = list(segmentos_video)
    audios = list(audios_escena)
    duraciones = [duracion_video(v) for v in videos]
    if any(d <= 0 for d in duraciones):
        raise RuntimeError("Un segmento de video salió con duración 0.")

    carpeta_tmp = os.path.dirname(salida) or "."
    if titulo:
        portada = crear_portada(titulo, subtitulo, os.path.join(carpeta_tmp, "portada.mp4"))
        if portada:
            silencio = _audio_silencio(os.path.join(carpeta_tmp, "silencio_portada.m4a"), 3.0)
            videos = [portada] + videos
            audios = [silencio] + audios
            duraciones = [3.0] + duraciones

    if fundido > 0:
        fundido = min(fundido, min(duraciones) / 2.0)
    offsets, total = offsets_fundido(duraciones, fundido)

    entradas = []
    for v in videos:
        entradas += ["-i", v]
    for a in audios:
        entradas += ["-i", a]

    filtros = []
    # Video: cadena de xfade
    n = len(videos)
    if n == 1:
        filtros.append("[0:v]format=yuv420p[vout]")
        etiqueta_video = "[vout]"
    else:
        filtros.append(f"[0:v][1:v]xfade=transition=fade:duration={fundido}:offset={offsets[0]}[v1]")
        for i in range(2, n):
            filtros.append(
                f"[v{i - 1}][{i}:v]xfade=transition=fade:duration={fundido}"
                f":offset={offsets[i - 1]}[v{i}]"
            )
        etiqueta_video = f"[v{n - 1}]"
    # Audio: normalizar y cadena de acrossfade
    for i in range(len(audios)):
        filtros.append(f"[{n + i}:a]aresample=44100,aformat=channel_layouts=stereo[a{i}in]")
    if len(audios) == 1:
        filtros.append("[a0in]anull[aout]")
        etiqueta_audio = "[aout]"
    else:
        filtros.append(f"[a0in][a1in]acrossfade=d={fundido}:c1=tri:c2=tri[a1]")
        for i in range(2, len(audios)):
            filtros.append(f"[a{i - 1}][a{i}in]acrossfade=d={fundido}:c1=tri:c2=tri[a{i}]")
        etiqueta_audio = f"[a{len(audios) - 1}]"

    cmd = [
        "ffmpeg", "-y",
        *entradas,
        "-filter_complex", ";".join(filtros),
        "-map", etiqueta_video, "-map", etiqueta_audio,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps),
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        salida,
    ]
    resultado = subprocess.run(cmd, capture_output=True, text=True)
    if resultado.returncode != 0:
        raise RuntimeError(f"El ensamblado falló: {resultado.stderr.strip()[-800:]}")
    duracion_final = duracion_video(salida)
    return {
        "ruta": salida,
        "duracion_seg": round(duracion_final, 2),
        "duracion_esperada_seg": round(total, 2),
        "num_escenas": len(segmentos_video),
    }
