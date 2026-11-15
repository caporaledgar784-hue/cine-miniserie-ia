# 🎬 Cine Miniserie IA

**Convierte una idea en una miniserie cinematográfica completa, 100 % gratis,
como una película.**

Tú escribes la idea. La herramienta escribe el guion con diálogos, crea a los
personajes, genera las imágenes, graba las voces (una distinta por personaje)
y une todo en **un solo video final, sin que se vean los cortes**.

## Lo que hace diferente a esta herramienta

| Lo que pediste | Cómo lo cumple |
|---|---|
| Escenas cinematográficas **largas** | Cada escena dura lo que dura su diálogo y su narración, no 5 segundos. |
| **Gente** incluida | Personajes con nombre, edad, cara y ropa fijas. La misma ficha se inyecta en el prompt de todas las imágenes para que no cambien de escena a escena. |
| Los personajes se **mueven y dialogan** | El guion tiene réplicas de diálogo por personaje (no solo narración) y cada uno tiene su propia voz en el audio. |
| Miniserie **concreta y consistente** | Historia completa con final cerrado, un solo video final. |
| **Sin cortes visibles** | Las escenas se unen con fundidos cruzados de video (`xfade`) y de audio (`acrossfade`). Todo junto, como una película. |
| **100 % gratis** | Guion e imágenes con Pollinations sin clave, voces con edge-tts sin clave. Sin cuentas, sin tarjetas. |

## Cómo funciona

```
idea → guion (Pollinations) → imágenes (Pollinations, 1 por vez)
     → audio por personaje (edge-tts) → segmentos con zoom/pan (ffmpeg)
     → video final con fundidos cruzados (ffmpeg)
```

1. **Guion**: Pollinations escribe el guion en JSON: título, personajes con
   ficha fija y escenas con diálogos y narración.
2. **Imágenes**: una imagen cinematográfica por escena, con la ficha de los
   personajes que salen en ella.
3. **Audio**: cada réplica se graba con la voz de su personaje; la narración
   con voz de narrador. El audio de la escena marca cuánto dura la escena.
4. **Video**: cada escena se mueve con zoom/pan lento (efecto Ken Burns).
   Opcionalmente, clips de movimiento real (ver abajo).
5. **Ensamblado**: fundido cruzado de 1 s entre escenas (video y audio) y
   portada con el título. Sale `final/miniserie.mp4`.

## Instalación en Windows (paso a paso)

### 1. Instala Python 3.10 o más nuevo

Descárgalo de [python.org/downloads](https://www.python.org/downloads/) y en
el instalador marca **"Add Python to PATH"**. Comprueba en la terminal
(`cmd` o PowerShell):

```bat
python --version
```

### 2. Instala ffmpeg

Opción fácil con winget (ya viene en Windows 10/11):

```bat
winget install Gyan.FFmpeg
```

Cierra y vuelve a abrir la terminal. Comprueba:

```bat
ffmpeg -version
```

Si no tienes winget, descarga ffmpeg de
[gyan.dev/ffmpeg/builds](https://www.gyan.dev/ffmpeg/builds/)
(`ffmpeg-release-essentials.zip`), descomprímelo y agrega la carpeta `bin` al
PATH de Windows.

### 3. Descarga este repositorio

```bat
git clone https://github.com/TU-USUARIO/cine-miniserie-ia.git
cd cine-miniserie-ia
```

O descarga el ZIP desde GitHub y descomprímelo.

### 4. Instala las dependencias de Python

```bat
pip install -r requirements.txt
```

## Uso

### La forma rápida: desde una idea

```bat
python -m cine_miniserie crear --idea "En un rancho de Jalisco, Don Ernesto, el dueño, se disfraza de peón para descubrir cómo tratan a sus trabajadores..." --escenas 5 --salida ./mi-miniserie
```

### Con un archivo de idea

```bat
python -m cine_miniserie crear --idea-archivo ejemplo_idea.txt --salida ./mi-miniserie
```

### Con archivo de configuración (recomendado)

```bat
copy config.ejemplo.yaml config.yaml
notepad config.yaml
python -m cine_miniserie crear --config config.yaml
```

### Ver el avance de un proyecto

```bat
python -m cine_miniserie estado --proyecto ./mi-miniserie
```

### Reanudar si se corta

El comando `crear` es **reanudable**: si se corta la luz, el internet o
Pollinations te pone límite, vuelve a correr el mismo comando y sigue donde se
quedó, sin repetir las imágenes ni los audios ya hechos. El avance se guarda
en `proyecto.json` dentro de la carpeta del proyecto.

## Estructura del proyecto generado

```
mi-miniserie/
├── proyecto.json      # guion, personajes y avance (para reanudar)
├── imagenes/          # una imagen por escena
├── audio/             # diálogos y narración por escena
├── video/             # un segmento por escena
└── final/
    └── miniserie.mp4  # el video final, sin cortes
```

## Movimiento real (opcional, no gratis ilimitado)

Por defecto las escenas se mueven con zoom/pan cinematográfico: **gratis e
ilimitado**, y es lo que usa la herramienta si no configuras nada.

Si quieres clips con movimiento real (personajes caminando, gestos), la
herramienta ya trae el código preparado para tres proveedores. Necesitas
configurar la clave en un archivo `.env` (copia `.env.ejemplo` a `.env`):

| Proveedor | Qué es | Costo real |
|---|---|---|
| **Magic Hour** | API de video (Veo, Kling, MiniMax, LTX, Wan) | Registro gratis sin tarjeta; con los créditos del registro salen ~3 clips de 5 s a 480p. Después, menos de 1 clip al día gratis. |
| **fal.ai** | API de video por segundos | Sin plan gratis. MiniMax H3 Max Turbo ≈ $0.025/s → un video de 20 escenas de 5 s ≈ $2.50. |
| **FreeLLMAPI** | Tu propio servidor (programa en tu PC) | Gratis el programa; el video depende de las claves de proveedor que le pongas. |

Uso:

```bat
python -m cine_miniserie crear --config config.yaml --movimiento real --proveedor magic-hour
```

Si el proveedor falla o no hay clave, la herramienta avisa y usa el
movimiento cinematográfico, para que nunca te quedes sin video.

> ⚠️ **Honestidad ante todo**: hoy no existe ninguna opción gratuita e
> ilimitada que genere movimiento real para un video de 20 escenas de forma
> automática. Las opciones gratis son para probar (pocos clips) o muy lentas
> (modelos abiertos como Wan 2.2 tardan días y necesitan tarjeta gráfica).
> Por eso el movimiento cinematográfico es el modo por defecto: siempre
> funciona y no cuesta nada.

## Límites reales de lo gratis

- **Pollinations keyless**: una imagen por vez, esperando 45 s entre
  llamadas; una petición de texto por vez, esperando 30 s. Si te pasas,
  responde 402 y la herramienta espera y reintenta sola. Las imágenes se
  generan a 768×432 y ffmpeg las escala a 1280×720. Puede aparecer una
  pequeña marca; se pide `nologo=true`.
- **edge-tts**: gratis y sin clave, pero necesita internet. Las voces pueden
  cambiar con el tiempo; si una voz deja de existir, edge-tts avisa y se
  cambia en `config.yaml` (opción `voces`). Si la red bloquea el servicio de
  voz de Microsoft (algunos proxies lo hacen), la herramienta usa **gTTS**
  automáticamente como respaldo: también gratis y sin clave, con acento y
  tono distintos por personaje, aunque con voz menos natural.
- **Una miniserie de 5 escenas tarda** unos 5–8 minutos en generarse
  (la mayoría es la espera entre imágenes). Una de 20 escenas, unos 20–25
  minutos. Por eso el comando es reanudable.
- **La consistencia de personajes** depende del modelo de imágenes: la ficha
  fija ayuda mucho, pero no es perfecta. Si un personaje sale distinto en
  una escena, borra esa imagen y vuelve a correr el comando: la regenera.

## Desarrollo y pruebas

```bat
python -m unittest discover -s tests -v
python -m py_compile cine_miniserie/*.py
```

## Licencia

MIT — úsalo, modifícalo y compártelo libremente. Ver `LICENSE`.
