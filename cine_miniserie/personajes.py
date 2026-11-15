"""Ficha de personajes fija.

Cada personaje tiene nombre, edad, descripción física y ropa FIJAS. Esa misma
descripción se inyecta en el prompt de TODAS las imágenes donde aparece, para
que no cambie de cara ni de ropa de escena a escena.

También se le asigna una voz distinta a cada personaje (edge-tts, gratis),
para que los diálogos suenen a personas diferentes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Voces de edge-tts en español (gratuitas, sin clave). Se asignan distintas
# por personaje; si un día una voz deja de existir, edge-tts avisa y se cambia
# aquí o en config.yaml (voces: {Nombre: voz}).
VOCES_FEMENINAS = [
    "es-MX-DaliaNeural",
    "es-ES-ElviraNeural",
    "es-ES-AbrilNeural",
    "es-AR-ElenaNeural",
    "es-CO-SalomeNeural",
    "es-US-PalomaNeural",
]

VOCES_MASCULINAS = [
    "es-MX-JorgeNeural",
    "es-ES-AlvaroNeural",
    "es-AR-TomasNeural",
    "es-CO-GonzaloNeural",
    "es-US-AlonsoNeural",
]

VOZ_NARRADOR_DEFECTO = "es-MX-DaliaNeural"


@dataclass
class Personaje:
    nombre: str
    edad: int
    descripcion_fisica: str
    ropa: str
    genero: str = "femenino"  # femenino | masculino
    rasgo: str = ""
    voz: str = ""

    def ficha_texto(self) -> str:
        """Descripción fija que se inyecta en cada prompt de imagen."""
        texto = (
            f"{self.nombre}, {self.edad} años, {self.descripcion_fisica}, "
            f"viste {self.ropa}"
        )
        if self.rasgo:
            texto += f", {self.rasgo}"
        return texto


def desde_json(lista: list) -> list[Personaje]:
    """Convierte la lista de personajes del guion (JSON) en objetos."""
    personajes = []
    for item in lista:
        personajes.append(
            Personaje(
                nombre=str(item.get("nombre", "Personaje")).strip(),
                edad=int(item.get("edad", 30)),
                descripcion_fisica=str(item.get("descripcion_fisica", "")).strip(),
                ropa=str(item.get("ropa", "")).strip(),
                genero=str(item.get("genero", "femenino")).strip().lower(),
                rasgo=str(item.get("rasgo", "")).strip(),
            )
        )
    return personajes


def asignar_voces(
    personajes: list[Personaje],
    voz_narrador: str = VOZ_NARRADOR_DEFECTO,
    sobrescrituras: dict | None = None,
) -> str:
    """Asigna una voz distinta a cada personaje y devuelve la voz del narrador.

    Las voces fijadas en config.yaml (sobrescrituras) se respetan. El narrador
    nunca usa la misma voz que un personaje.
    """
    sobrescrituras = sobrescrituras or {}
    usadas = {voz_narrador}
    fem = [v for v in VOCES_FEMENINAS if v not in usadas]
    masc = [v for v in VOCES_MASCULINAS if v not in usadas]
    indice_f, indice_m = 0, 0
    for p in personajes:
        if p.nombre in sobrescrituras:
            p.voz = sobrescrituras[p.nombre]
            usadas.add(p.voz)
            continue
        if p.genero.startswith("m"):
            pool = masc
            if indice_m < len(pool):
                p.voz = pool[indice_m]
                indice_m += 1
            else:
                p.voz = pool[indice_m % len(pool)]
                indice_m += 1
        else:
            pool = fem
            if indice_f < len(pool):
                p.voz = pool[indice_f]
                indice_f += 1
            else:
                p.voz = pool[indice_f % len(pool)]
                indice_f += 1
        usadas.add(p.voz)
    return voz_narrador


def mapa_voces(personajes: list[Personaje], voz_narrador: str) -> dict:
    """Devuelve {nombre_personaje: voz} más la clave especial 'NARRADOR'."""
    mapa = {"NARRADOR": voz_narrador}
    for p in personajes:
        mapa[p.nombre] = p.voz
    return mapa
