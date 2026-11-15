"""Pruebas unitarias (solo biblioteca estándar). Corre con:
    python -m unittest discover -s tests -v
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cine_miniserie import guion as modulo_guion
from cine_miniserie import imagenes as modulo_imagenes
from cine_miniserie import personajes as modulo_personajes
from cine_miniserie.config import Config
from cine_miniserie.ensamblado import offsets_fundido


class TestFundidos(unittest.TestCase):
    def test_offsets_y_total(self):
        offsets, total = offsets_fundido([10, 10, 10], 1.0)
        self.assertEqual(offsets, [9.0, 18.0])
        self.assertEqual(total, 28.0)

    def test_una_sola_escena(self):
        offsets, total = offsets_fundido([12.5], 1.0)
        self.assertEqual(offsets, [])
        self.assertEqual(total, 12.5)

    def test_fundido_medio_segundo(self):
        offsets, total = offsets_fundido([6, 8, 7], 0.5)
        self.assertEqual(offsets, [5.5, 13.0])
        self.assertEqual(total, 20.0)


class TestPersonajes(unittest.TestCase):
    def test_ficha_fija(self):
        p = modulo_personajes.Personaje(
            nombre="Mariana", edad=34,
            descripcion_fisica="mexicana, pelo largo castaño oscuro, ojos cansados",
            ropa="blusa bordada sencilla y delantal",
            genero="femenino", rasgo="cuida a su madre",
        )
        ficha = p.ficha_texto()
        self.assertIn("Mariana, 34 años", ficha)
        self.assertIn("blusa bordada sencilla y delantal", ficha)
        self.assertIn("cuida a su madre", ficha)

    def test_voces_distintas(self):
        personajes = modulo_personajes.desde_json([
            {"nombre": "Mariana", "edad": 34, "genero": "femenino",
             "descripcion_fisica": "x", "ropa": "y"},
            {"nombre": "Valeria", "edad": 31, "genero": "femenino",
             "descripcion_fisica": "x", "ropa": "y"},
            {"nombre": "Ernesto", "edad": 68, "genero": "masculino",
             "descripcion_fisica": "x", "ropa": "y"},
        ])
        narrador = modulo_personajes.asignar_voces(personajes, "es-MX-DaliaNeural")
        voces = [p.voz for p in personajes]
        self.assertEqual(len(set(voces)), 3, "Cada personaje debe tener voz distinta")
        self.assertNotIn(narrador, voces, "El narrador no repite voz de personaje")


class TestImagenes(unittest.TestCase):
    def test_prompt_incluye_fichas_y_estilo(self):
        prompt = modulo_imagenes.construir_prompt_escena(
            "a woman opens a drawer",
            ["Mariana, 34 años, pelo largo castaño, viste blusa bordada"],
            "cinematográfico fotorrealista, 16:9",
        )
        self.assertIn("a woman opens a drawer", prompt)
        self.assertIn("Mariana, 34 años", prompt)
        self.assertIn("cinematográfico fotorrealista", prompt)
        self.assertIn("no text", prompt)


class TestGuion(unittest.TestCase):
    def _guion_valido(self):
        return {
            "titulo": "MI HERMANA SE QUEDÓ CON TODO",
            "personajes": [
                {"nombre": "Mariana", "edad": 34, "genero": "femenino",
                 "descripcion_fisica": "pelo largo castaño", "ropa": "blusa bordada"},
                {"nombre": "Valeria", "edad": 31, "genero": "femenino",
                 "descripcion_fisica": "rubia", "ropa": "blazer rojo"},
            ],
            "escenas": [
                {"numero": 1, "titulo": "El gancho", "prompt_imagen": "a notary office",
                 "lineas": [
                     {"tipo": "narracion", "texto": "Había una casa..."},
                     {"tipo": "dialogo", "personaje": "Mariana", "texto": "No es justo."},
                     {"tipo": "dialogo", "personaje": "Valeria", "texto": "La casa es mía."},
                 ]},
            ],
        }

    def test_guion_valido_sin_problemas(self):
        self.assertEqual(modulo_guion.validar_guion(self._guion_valido()), [])

    def test_dialogo_con_personaje_inexistente(self):
        guion = self._guion_valido()
        guion["escenas"][0]["lineas"][1]["personaje"] = "Alguien"
        problemas = modulo_guion.validar_guion(guion)
        self.assertTrue(any("Alguien" in p for p in problemas))

    def test_escena_sin_dialogos(self):
        guion = self._guion_valido()
        guion["escenas"][0]["lineas"] = [
            {"tipo": "narracion", "texto": "Solo narración."}
        ]
        problemas = modulo_guion.validar_guion(guion)
        self.assertTrue(any("diálogo" in p for p in problemas))

    def test_extraer_json_con_comas_finales(self):
        texto = '```json\n{"titulo": "X", "personajes": [], "escenas": [],}\n```'
        resultado = modulo_guion._extraer_json(texto)
        self.assertEqual(resultado["titulo"], "X")

    def test_extraer_json_con_texto_alrededor(self):
        texto = 'Claro, aquí está:\n{"titulo": "Y"} \nEspero que te guste.'
        resultado = modulo_guion._extraer_json(texto)
        self.assertEqual(resultado["titulo"], "Y")

    def test_extraer_json_con_salto_de_linea_en_texto(self):
        texto = '{"titulo": "Z", "texto": "primera línea\nsegunda línea"}'
        resultado = modulo_guion._extraer_json(texto)
        self.assertIn("segunda línea", resultado["texto"])


class TestConfig(unittest.TestCase):
    def test_valores_por_defecto(self):
        cfg = Config()
        self.assertEqual(cfg.num_escenas, 5)
        self.assertEqual(cfg.movimiento, "cinematografico")
        self.assertEqual(cfg.fundido_segundos, 1.0)

    def test_desde_yaml(self):
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
            f.write("idea: Una prueba\nnum_escenas: 3\nfundido_segundos: 0.5\n")
            ruta = f.name
        try:
            cfg = Config.desde_yaml(ruta)
            self.assertEqual(cfg.idea, "Una prueba")
            self.assertEqual(cfg.num_escenas, 3)
            self.assertEqual(cfg.fundido_segundos, 0.5)
        finally:
            os.remove(ruta)


if __name__ == "__main__":
    unittest.main()
