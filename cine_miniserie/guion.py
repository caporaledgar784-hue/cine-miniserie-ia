"""Generación del guion con Pollinations keyless (gratis, sin clave ni cuenta).

Se usa el endpoint compatible con OpenAI de text.pollinations.ai. El guion se
pide en JSON estricto, en DOS pasos para que cada respuesta sea corta y no se
corte a la mitad (los modelos gratuitos limitan la longitud de respuesta):
  1) título + personajes con ficha fija,
  2) escenas con diálogos (cada réplica con su personaje) y narración.

Las escenas son LARGAS: cada una dura lo que duren su diálogo y su
narración, no 5 segundos.

Límites de lo gratis (Pollinations keyless): una petición de texto por vez,
esperar 30 segundos entre llamadas. Si se pasa el límite responde 402 con
Retry-After; aquí se respeta y se reintenta.
"""

from __future__ import annotations

import json
import re
import time

import requests

URL_TEXTO = "https://text.pollinations.ai/openai/v1/chat/completions"
MODELOS = ["openai", "openai-fast"]
ESPERA_MINIMA_SEG = 30
TIMEOUT_SEG = 180
MAX_TOKENS = 4000

_ultima_llamada = 0.0


def _respetar_espera() -> None:
    global _ultima_llamada
    ahora = time.time()
    falta = ESPERA_MINIMA_SEG - (ahora - _ultima_llamada)
    if falta > 0:
        time.sleep(falta)
    _ultima_llamada = time.time()


def _llamar_pollinations(mensajes: list, temperatura: float = 0.8) -> str:
    """Una llamada al chat de Pollinations. Reintenta si hay límite (402/429)."""
    _respetar_espera()
    ultimo_error = None
    for intento in range(3):
        modelo = MODELOS[min(intento, len(MODELOS) - 1)]
        try:
            resp = requests.post(
                URL_TEXTO,
                json={
                    "model": modelo,
                    "messages": mensajes,
                    "temperature": temperatura,
                    "max_tokens": MAX_TOKENS,
                },
                timeout=TIMEOUT_SEG,
            )
        except requests.RequestException as e:
            ultimo_error = f"Error de red: {e}"
            time.sleep(10)
            continue
        if resp.status_code in (402, 429):
            espera = int(resp.headers.get("Retry-After", "45"))
            print(f"  [Pollinations] límite alcanzado, espero {espera}s y reintento...")
            time.sleep(min(max(espera, 5), 120))
            ultimo_error = f"HTTP {resp.status_code}: límite de Pollinations"
            continue
        if resp.status_code != 200:
            ultimo_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
            time.sleep(10)
            continue
        datos = resp.json()
        try:
            return datos["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            ultimo_error = f"Respuesta inesperada: {str(datos)[:200]}"
            time.sleep(5)
    raise RuntimeError(f"No se pudo generar el guion con Pollinations. {ultimo_error}")


def _reparar_json(texto: str) -> str:
    """Arreglos comunes del JSON que escriben los modelos gratuitos:
    comas finales antes de } o ], caracteres de control sueltos."""
    texto = re.sub(r",\s*([}\]])", r"\1", texto)
    texto = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", texto)
    return texto


def _extraer_json(texto: str) -> dict:
    """Saca el JSON aunque venga dentro de bloques ```json ... ``` y aunque
    tenga pequeños errores (comas finales, saltos de línea dentro de textos)."""
    texto = texto.strip()
    cercado = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", texto, re.DOTALL)
    if cercado:
        texto = cercado.group(1)
    inicio = texto.find("{")
    if inicio == -1:
        raise ValueError("La respuesta no contiene JSON.")
    candidato = texto[inicio:]
    intentos = [
        lambda t: json.loads(t),
        lambda t: json.loads(t, strict=False),
        lambda t: json.loads(_reparar_json(t)),
        lambda t: json.loads(_reparar_json(t), strict=False),
    ]
    ultimo_error = None
    for probar in intentos:
        try:
            return probar(candidato)
        except json.JSONDecodeError as e:
            ultimo_error = e
    try:
        objeto, _ = json.JSONDecoder().raw_decode(_reparar_json(candidato))
        return objeto
    except json.JSONDecodeError:
        raise ValueError(f"JSON inválido: {ultimo_error}") from None


PLANTILLA_PERSONAJES = """Eres un guionista de miniseries cinematográficas de drama familiar,
estilo telenovela, en español. La historia debe tener principio, desarrollo
y FINAL CERRADO.

IDEA: {idea}
ESTILO VISUAL: {estilo}

Crea el título y entre 3 y 5 personajes con nombre, edad, descripción física
DE UNA LÍNEA (cara, pelo, complexión) y ropa fija. Esas descripciones NO
cambian nunca en toda la miniserie.

Responde ÚNICAMENTE con este JSON, sin texto fuera de él, sin comas finales:
{{
  "titulo": "Título en mayúsculas, dramático, con el giro de la historia",
  "personajes": [
    {{"nombre": "Mariana", "edad": 34, "genero": "femenino",
     "descripcion_fisica": "mexicana, pelo largo castaño oscuro, ojos cansados",
     "ropa": "blusa bordada sencilla y delantal",
     "rasgo": "cuida a su madre desde hace 6 años"}}
  ]
}}"""

PLANTILLA_ESCENAS = """Eres un guionista de miniseries cinematográficas de drama familiar,
estilo telenovela, en español. Escribe las escenas COMPLETAS de la historia,
con principio, desarrollo y FINAL CERRADO (que no quede en continuará).

IDEA: {idea}
NÚMERO DE ESCENAS: {num_escenas}
TÍTULO: {titulo}
PERSONAJES (usa solo estos nombres): {personajes}

Reglas obligatorias:
- Cada escena es LARGA: dura lo que duren sus diálogos y su narración.
  Escribe diálogos REALES entre los personajes (cada réplica con su
  personaje), no solo narración. Entre 4 y 8 líneas por escena, mínimo
  3 réplicas de diálogo. Frases cortas, de una línea cada una.
- La narración (voz en off) solo abre o cierra escenas, no sustituye diálogos.
- El prompt_imagen de cada escena describe la escena completa en inglés,
  estilo cinematográfico, e incluye a los personajes que salen en ella.

Responde ÚNICAMENTE con este JSON, sin texto fuera de él, sin comas finales:
{{
  "escenas": [
    {{"numero": 1, "titulo": "El gancho",
     "descripcion_visual": "Qué se ve en la escena, en español",
     "prompt_imagen": "cinematic photorealistic scene in English, ...",
     "personajes_en_escena": ["Mariana"],
     "lineas": [
       {{"tipo": "narracion", "texto": "Había una casa donde..."}},
       {{"tipo": "dialogo", "personaje": "Mariana", "texto": "¡No te atrevas!"}}
     ]}}
  ]
}}"""


def validar_personajes(datos: dict) -> list[str]:
    problemas = []
    if not datos.get("titulo"):
        problemas.append("falta el título")
    personajes = datos.get("personajes") or []
    if len(personajes) < 2:
        problemas.append("se necesitan al menos 2 personajes")
    for p in personajes:
        if not p.get("nombre"):
            problemas.append("un personaje no tiene nombre")
        if not p.get("descripcion_fisica") or not p.get("ropa"):
            problemas.append(f"el personaje {p.get('nombre')} no tiene ficha completa")
    return problemas


def validar_escenas(datos: dict, nombres: set) -> list[str]:
    problemas = []
    escenas = datos.get("escenas") or []
    if not escenas:
        problemas.append("no hay escenas")
    for e in escenas:
        lineas = e.get("lineas") or []
        if not lineas:
            problemas.append(f"la escena {e.get('numero')} no tiene líneas")
        dialogos = [l for l in lineas if l.get("tipo") == "dialogo"]
        if len(dialogos) < 2:
            problemas.append(
                f"la escena {e.get('numero')} tiene menos de 2 réplicas de diálogo"
            )
        for l in dialogos:
            if l.get("personaje") not in nombres:
                problemas.append(
                    f"la escena {e.get('numero')} usa un personaje no definido: "
                    f"{l.get('personaje')}"
                )
        if not e.get("prompt_imagen"):
            problemas.append(f"la escena {e.get('numero')} no tiene prompt_imagen")
    return problemas


def validar_guion(guion: dict) -> list[str]:
    """Valida un guion completo (personajes + escenas)."""
    problemas = validar_personajes(guion)
    nombres = {p.get("nombre") for p in guion.get("personajes", []) if p.get("nombre")}
    return problemas + validar_escenas(guion, nombres)


def _pedir_json(prompt: str, validador, etiqueta: str) -> dict:
    """Pide un JSON a Pollinations con hasta 3 intentos. En cada reintento se
    pide una versión más corta, porque los modelos gratuitos cortan las
    respuestas largas a la mitad."""
    mensajes = [
        {"role": "system", "content": "Responde solo con JSON válido, sin explicaciones."},
        {"role": "user", "content": prompt},
    ]
    texto = ""
    datos = None
    problemas = ["sin intentar"]
    for intento in range(3):
        if intento > 0:
            print(f"  [{etiqueta}] intento {intento + 1}/3, pido versión más corta...")
            mensajes.append({"role": "assistant", "content": texto})
            mensajes.append(
                {
                    "role": "user",
                    "content": (
                        "Tu respuesta anterior tenía estos problemas: "
                        + "; ".join(problemas)
                        + ". Devuelve el JSON COMPLETO corregido y MÁS CORTO "
                        "(frases de una línea, sin adornos), solo JSON válido, "
                        "sin comas finales, sin texto fuera del JSON."
                    ),
                }
            )
        texto = _llamar_pollinations(mensajes)
        try:
            datos = _extraer_json(texto)
            problemas = validador(datos)
        except (ValueError, json.JSONDecodeError) as e:
            datos, problemas = None, [f"JSON inválido: {e}"]
        if not problemas:
            return datos
        print(f"  [{etiqueta}] problemas: {'; '.join(problemas)}")
    raise RuntimeError(
        f"No se pudo obtener {etiqueta} válido tras 3 intentos: "
        + "; ".join(problemas)
        + ". Vuelve a correr el comando: es reanudable y no pierde lo hecho."
    )


def generar_guion(idea: str, num_escenas: int, estilo: str) -> dict:
    """Genera el guion completo en dos pasos (personajes, luego escenas)."""
    print("  [Guion] paso 1/2: título y personajes...")
    base = _pedir_json(
        PLANTILLA_PERSONAJES.format(idea=idea, estilo=estilo),
        validar_personajes,
        "Personajes",
    )
    nombres = [p["nombre"] for p in base["personajes"]]
    resumen = "; ".join(
        f"{p['nombre']} ({p.get('edad', '')} años, {p.get('descripcion_fisica', '')})"
        for p in base["personajes"]
    )
    print("  [Guion] paso 2/2: escenas con diálogos...")
    escenas = _pedir_json(
        PLANTILLA_ESCENAS.format(
            idea=idea,
            num_escenas=num_escenas,
            titulo=base["titulo"],
            personajes=", ".join(nombres) + ". " + resumen,
        ),
        lambda d: validar_escenas(d, set(nombres)),
        "Escenas",
    )
    guion = {"titulo": base["titulo"], "personajes": base["personajes"],
             "escenas": sorted(escenas["escenas"], key=lambda e: e.get("numero", 0))}
    return guion
