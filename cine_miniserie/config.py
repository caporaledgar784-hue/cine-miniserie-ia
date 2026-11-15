"""Carga de configuración: archivo config.yaml + variables de entorno.

Las claves de los servicios opcionales de movimiento real (fal.ai, Magic Hour,
FreeLLMAPI) SOLO se leen de variables de entorno o de un archivo .env local.
Nunca van en el código ni en config.yaml.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

try:
    import yaml
except ImportError:  # pragma: no cover - pyyaml está en requirements.txt
    yaml = None

VALORES_POR_DEFECTO = {
    "idea": "",
    "num_escenas": 5,
    "estilo": (
        "cinematográfico fotorrealista, luz cálida dramática, "
        "paleta dorada y madera oscura, encuadre de cine, 16:9"
    ),
    # cinematografico = zoom/pan lento sobre las imágenes (gratis, ilimitado)
    # real = clips de movimiento real con fal.ai / Magic Hour / FreeLLMAPI
    #        (opcional, necesita clave configurada)
    "movimiento": "cinematografico",
    "fundido_segundos": 1.0,
    "ancho": 1280,
    "alto": 720,
    "fps": 25,
    "velocidad_audio": "-5%",
    "portada": True,
    "semilla": 42,
    "salida": "mi-miniserie",
    "voces": {},
    "voz_narrador": "es-MX-DaliaNeural",
}


@dataclass
class Config:
    idea: str = ""
    num_escenas: int = 5
    estilo: str = VALORES_POR_DEFECTO["estilo"]
    movimiento: str = "cinematografico"
    fundido_segundos: float = 1.0
    ancho: int = 1280
    alto: int = 720
    fps: int = 25
    velocidad_audio: str = "-5%"
    portada: bool = True
    semilla: int = 42
    salida: str = "mi-miniserie"
    voces: dict = field(default_factory=dict)
    voz_narrador: str = "es-MX-DaliaNeural"

    @classmethod
    def desde_yaml(cls, ruta: str) -> "Config":
        """Lee un config.yaml. Si no existe, devuelve los valores por defecto."""
        datos = dict(VALORES_POR_DEFECTO)
        if ruta and os.path.exists(ruta):
            if yaml is None:
                raise RuntimeError(
                    "Falta PyYAML. Instala dependencias con: pip install -r requirements.txt"
                )
            with open(ruta, "r", encoding="utf-8") as f:
                cargado = yaml.safe_load(f) or {}
            datos.update(cargado)
        return cls(**{k: v for k, v in datos.items() if k in VALORES_POR_DEFECTO})

    def a_dict(self) -> dict:
        return {
            "idea": self.idea,
            "num_escenas": self.num_escenas,
            "estilo": self.estilo,
            "movimiento": self.movimiento,
            "fundido_segundos": self.fundido_segundos,
            "ancho": self.ancho,
            "alto": self.alto,
            "fps": self.fps,
            "velocidad_audio": self.velocidad_audio,
            "portada": self.portada,
            "semilla": self.semilla,
            "salida": self.salida,
            "voces": self.voces,
            "voz_narrador": self.voz_narrador,
        }


def claves_movimiento_real() -> dict:
    """Lee las claves opcionales SOLO de variables de entorno.

    Devuelve un dict con las que existan. Si está vacío, el movimiento real
    no está disponible y se usa el cinematográfico (gratis).
    """
    claves = {}
    for nombre in (
        "FAL_API_KEY",
        "MAGIC_HOUR_API_KEY",
        "FREELLMAPI_URL",
        "FREELLMAPI_KEY",
        "FAL_MODEL",
    ):
        valor = os.environ.get(nombre, "").strip()
        if valor:
            claves[nombre] = valor
    return claves


def cargar_env(ruta_env: str = ".env") -> None:
    """Carga variables de un archivo .env local (si existe) sin sobreescribir
    las que ya estén en el entorno. El .env nunca se versiona (.gitignore)."""
    if not os.path.exists(ruta_env):
        return
    with open(ruta_env, "r", encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            clave, valor = linea.split("=", 1)
            os.environ.setdefault(clave.strip(), valor.strip())
