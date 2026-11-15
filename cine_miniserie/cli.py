"""Interfaz de línea de comandos (en español).

Uso:
  python -m cine_miniserie crear --idea "Una historia..." --escenas 5 --salida ./mi-miniserie
  python -m cine_miniserie crear --config config.yaml
  python -m cine_miniserie crear --idea-archivo ejemplo_idea.txt
  python -m cine_miniserie estado --proyecto ./mi-miniserie

El comando `crear` es reanudable: si se corta (por ejemplo, por el límite de
Pollinations), vuelve a correrlo y sigue donde se quedó, sin repetir lo hecho.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from . import audio as modulo_audio
from . import ensamblado as modulo_ensamblado
from . import guion as modulo_guion
from . import imagenes as modulo_imagenes
from . import personajes as modulo_personajes
from . import video as modulo_video
from .config import Config, cargar_env, claves_movimiento_real


def cargar_estado(carpeta: str) -> dict:
    ruta = os.path.join(carpeta, "proyecto.json")
    if os.path.exists(ruta):
        with open(ruta, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"escenas": []}


def guardar_estado(carpeta: str, estado: dict) -> None:
    os.makedirs(carpeta, exist_ok=True)
    ruta = os.path.join(carpeta, "proyecto.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=2)


def _asegurar_carpetas(carpeta: str) -> dict:
    rutas = {
        "imagenes": os.path.join(carpeta, "imagenes"),
        "audio": os.path.join(carpeta, "audio"),
        "video": os.path.join(carpeta, "video"),
        "final": os.path.join(carpeta, "final"),
    }
    for r in rutas.values():
        os.makedirs(r, exist_ok=True)
    return rutas


def paso_guion(cfg: Config, estado: dict) -> dict:
    if estado.get("guion"):
        print("[1/5] Guion: ya existe, lo reutilizo.")
        return estado["guion"]
    print(f"[1/5] Guion: escribiendo {cfg.num_escenas} escenas con Pollinations (gratis)...")
    guion = modulo_guion.generar_guion(cfg.idea, cfg.num_escenas, cfg.estilo)
    estado["guion"] = guion
    personajes = modulo_personajes.desde_json(guion["personajes"])
    modulo_personajes.asignar_voces(personajes, cfg.voz_narrador, cfg.voces)
    estado["personajes"] = [p.__dict__ for p in personajes]
    estado["voz_narrador"] = cfg.voz_narrador
    print(f"      Título: {guion['titulo']}")
    print(f"      Personajes: {', '.join(p.nombre for p in personajes)}")
    return guion


def paso_imagenes(cfg: Config, estado: dict, rutas: dict) -> None:
    guion = estado["guion"]
    personajes = [modulo_personajes.Personaje(**p) for p in estado["personajes"]]
    por_nombre = {p.nombre: p for p in personajes}
    for escena in guion["escenas"]:
        num = escena["numero"]
        entrada = next((e for e in estado["escenas"] if e["numero"] == num), None)
        if entrada is None:
            entrada = {"numero": num, "titulo": escena.get("titulo", "")}
            estado["escenas"].append(entrada)
        if entrada.get("imagen") and os.path.exists(
            os.path.join(rutas["imagenes"], os.path.basename(entrada["imagen"]))
        ):
            print(f"[2/5] Escena {num}: imagen ya existe, la reutilizo.")
            continue
        fichas = [
            por_nombre[n].ficha_texto()
            for n in escena.get("personajes_en_escena", [])
            if n in por_nombre
        ]
        prompt = modulo_imagenes.construir_prompt_escena(
            escena["prompt_imagen"], fichas, cfg.estilo
        )
        ruta = os.path.join(rutas["imagenes"], f"escena{num:02d}.jpg")
        print(f"[2/5] Escena {num}: generando imagen (Pollinations, gratis)...")
        modulo_imagenes.generar_imagen(
            prompt, ruta, semilla=cfg.semilla + num
        )
        entrada["imagen"] = ruta


def paso_audio(cfg: Config, estado: dict, rutas: dict) -> None:
    guion = estado["guion"]
    personajes = [modulo_personajes.Personaje(**p) for p in estado["personajes"]]
    mapa = modulo_personajes.mapa_voces(personajes, estado.get("voz_narrador", cfg.voz_narrador))
    for escena in guion["escenas"]:
        num = escena["numero"]
        entrada = next(e for e in estado["escenas"] if e["numero"] == num)
        ruta_audio = os.path.join(rutas["audio"], f"escena{num:02d}.mp3")
        if entrada.get("audio") and os.path.exists(ruta_audio):
            print(f"[3/5] Escena {num}: audio ya existe, lo reutilizo.")
            continue
        print(f"[3/5] Escena {num}: grabando diálogos y narración (edge-tts, gratis)...")
        _, duracion = modulo_audio.audio_escena(
            escena["lineas"], mapa, rutas["audio"], f"escena{num:02d}",
            velocidad=cfg.velocidad_audio,
        )
        entrada["audio"] = ruta_audio
        entrada["duracion_audio"] = round(duracion, 2)
        print(f"      Duración de la escena: {duracion:.1f} s")


def paso_video(cfg: Config, estado: dict, rutas: dict, proveedor: str) -> None:
    guion = estado["guion"]
    for escena in guion["escenas"]:
        num = escena["numero"]
        entrada = next(e for e in estado["escenas"] if e["numero"] == num)
        ruta_video = os.path.join(rutas["video"], f"escena{num:02d}.mp4")
        if entrada.get("video") and os.path.exists(ruta_video):
            print(f"[4/5] Escena {num}: video ya existe, lo reutilizo.")
            continue
        duracion = entrada.get("duracion_audio") or modulo_audio.estimar_duracion(
            " ".join(l.get("texto", "") for l in escena["lineas"])
        )
        direccion = "acercar" if num % 2 == 1 else "alejar"
        print(f"[4/5] Escena {num}: creando segmento de {duracion:.1f} s ({cfg.movimiento})...")
        modulo_video.segmento_escena(
            entrada["imagen"],
            escena.get("prompt_imagen", ""),
            duracion,
            ruta_video,
            movimiento=cfg.movimiento,
            proveedor=proveedor,
            direccion=direccion,
            fps=cfg.fps,
            ancho=cfg.ancho,
            alto=cfg.alto,
        )
        entrada["video"] = ruta_video


def paso_ensamblar(cfg: Config, estado: dict, rutas: dict) -> dict:
    escenas = sorted(estado["escenas"], key=lambda e: e["numero"])
    videos = [e["video"] for e in escenas]
    audios = [e["audio"] for e in escenas]
    salida = os.path.join(rutas["final"], "miniserie.mp4")
    print("[5/5] Ensamblando el video final con fundidos cruzados (sin cortes)...")
    resultado = modulo_ensamblado.ensamblar(
        videos,
        audios,
        salida,
        fundido=cfg.fundido_segundos,
        titulo=estado["guion"].get("titulo", ""),
        fps=cfg.fps,
    )
    estado["final"] = resultado
    return resultado


def cmd_crear(args) -> int:
    cargar_env()
    cfg = Config.desde_yaml(args.config) if args.config else Config()
    if args.idea:
        cfg.idea = args.idea
    if args.idea_archivo:
        with open(args.idea_archivo, "r", encoding="utf-8") as f:
            cfg.idea = f.read().strip()
    if args.escenas:
        cfg.num_escenas = args.escenas
    if args.salida:
        cfg.salida = args.salida
    if args.movimiento:
        cfg.movimiento = args.movimiento
    if not cfg.idea:
        print("Falta la idea. Usa --idea \"...\" o --config config.yaml con una idea.")
        return 2
    if cfg.movimiento == "real":
        claves = claves_movimiento_real()
        if not claves:
            print(
                "Movimiento real pedido, pero no hay ninguna clave configurada.\n"
                "Configura FAL_API_KEY, MAGIC_HOUR_API_KEY o FREELLMAPI_KEY en un .env\n"
                "o usa --movimiento cinematografico (gratis, siempre funciona)."
            )
            return 2
    carpeta = cfg.salida
    rutas = _asegurar_carpetas(carpeta)
    estado = cargar_estado(carpeta)
    estado["config"] = cfg.a_dict()
    guardar_estado(carpeta, estado)

    print(f"\n=== {estado.get('guion', {}).get('titulo') or 'Nueva miniserie'} ===")
    print(f"Idea: {cfg.idea[:120]}")
    print(f"Escenas: {cfg.num_escenas} | Movimiento: {cfg.movimiento} | Salida: {carpeta}\n")

    paso_guion(cfg, estado)
    guardar_estado(carpeta, estado)
    paso_imagenes(cfg, estado, rutas)
    guardar_estado(carpeta, estado)
    paso_audio(cfg, estado, rutas)
    guardar_estado(carpeta, estado)
    paso_video(cfg, estado, rutas, args.proveedor)
    guardar_estado(carpeta, estado)
    resultado = paso_ensamblar(cfg, estado, rutas)
    guardar_estado(carpeta, estado)

    minutos = resultado["duracion_seg"] / 60
    print("\n¡Listo! Tu miniserie está en:")
    print(f"  {resultado['ruta']}")
    print(f"  Duración: {resultado['duracion_seg']} s ({minutos:.1f} min), "
          f"{resultado['num_escenas']} escenas, un solo video, sin cortes.")
    return 0


def cmd_estado(args) -> int:
    estado = cargar_estado(args.proyecto)
    if not estado.get("guion"):
        print("Ese proyecto aún no tiene guion. Corre: python -m cine_miniserie crear ...")
        return 1
    print(f"Título: {estado['guion'].get('titulo')}")
    for e in sorted(estado["escenas"], key=lambda x: x["numero"]):
        marcas = []
        marcas.append("imagen ✓" if e.get("imagen") else "imagen ✗")
        marcas.append("audio ✓" if e.get("audio") else "audio ✗")
        marcas.append("video ✓" if e.get("video") else "video ✗")
        print(f"  Escena {e['numero']}: {e.get('titulo', '')} — {', '.join(marcas)}")
    if estado.get("final"):
        print(f"Video final: {estado['final']['ruta']} "
              f"({estado['final']['duracion_seg']} s)")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="cine-miniserie",
        description="Convierte una idea en una miniserie cinematográfica completa, gratis.",
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    p_crear = sub.add_parser("crear", help="Crea una miniserie completa desde una idea.")
    p_crear.add_argument("--idea", help="La idea de la miniserie, entre comillas.")
    p_crear.add_argument("--idea-archivo", help="Archivo .txt con la idea.")
    p_crear.add_argument("--config", help="Archivo config.yaml con los ajustes.")
    p_crear.add_argument("--escenas", type=int, help="Número de escenas (por defecto 5).")
    p_crear.add_argument("--salida", help="Carpeta del proyecto (por defecto mi-miniserie).")
    p_crear.add_argument(
        "--movimiento", choices=["cinematografico", "real"],
        help="cinematografico (gratis) o real (necesita clave configurada).",
    )
    p_crear.add_argument(
        "--proveedor", default="magic-hour",
        choices=["magic-hour", "fal", "freellmapi"],
        help="Proveedor de clips reales (solo con --movimiento real).",
    )
    p_crear.set_defaults(func=cmd_crear)

    p_estado = sub.add_parser("estado", help="Muestra el avance de un proyecto.")
    p_estado.add_argument("--proyecto", required=True, help="Carpeta del proyecto.")
    p_estado.set_defaults(func=cmd_estado)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
