"""Tests del parser topográfico contra ejemplos reales (capturas de WhatsApp)."""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from topo_parser import (
    parsear,
    truncar_2,
    procesar_abs,
    extraer_ensayo,
    extraer_coordenadas,
    leer_imagen,
)

# ---- Tokens tal como EasyOCR los devuelve (celda por celda) ----

# Captura 1: Código DCP 1
TOKENS_1 = [
    "Líneas", "eje 905", "1.250",
    "Nombre", "-218.161", "Código", "DCP 1",
    "Dist:1181.302m", "Est:K-0+218.161",
    "Cruz: -1181.302m", "Relleno: 118.285m", "Elev.: 786.715m",
    "N", "9603591.641", "Elevación", "786.715",
    "E", "780720.633", "Distancia 2D", "0.035",
    "Distancia base", "685.889", "Elev.", "0.012",
]

# Captura 2: Código VDC 4
TOKENS_2 = [
    "Líneas", "EJE 905", "1.250",
    "Nombre", "0.000", "Código", "VDC 4",
    "Dist:889.772m", "Est:K-0+154.895",
    "Cruz: -876.186m", "Relleno: 79.613m", "Elev.: 825.387m",
    "N", "9603295.217", "Distancia 2D", "0.010",
    "E", "780816.712", "Elevación", "825.387",
    "Distancia base", "667.181",
]


def _check(nombre, tokens, esperado):
    r = parsear(tokens)
    ok = True
    print(f"\n== {nombre} ==")
    for k, v in esperado.items():
        got = r.get(k)
        estado = "OK " if got == v else "FALLA"
        if got != v:
            ok = False
        print(f"  [{estado}] {k}: esperado={v!r}  obtenido={got!r}")
    return ok


def main():
    todo_ok = True

    todo_ok &= _check("Captura 1 (DCP 1)", TOKENS_1, {
        "Ensayo": "DCP 1",
        "X": "780720.63",
        "Y": "9603591.64",
        "COTA": "786.71",
        "ABS": "-218.16",
    })

    todo_ok &= _check("Captura 2 (VDC 4)", TOKENS_2, {
        "Ensayo": "VDC 4",
        "X": "780816.71",
        "Y": "9603295.21",
        "COTA": "825.38",
        "ABS": "-154.89",
    })

    # Simula la salida de pytesseract: cada FILA visual queda en una sola
    # línea de texto, mezclando ambas columnas (izq. y der. de la pantalla).
    TOKENS_TESSERACT_STYLE = [
        "Líneas > eje 905          1.250",
        "Nombre  -218.161   Código > DCP 1",
        "Dist:1181.302m  Est:K-0+218.161",
        "Cruz: -1181.302m   Relleno: 118.285m",
        "N   9603591.641   Elevación   786.715",
        "E   780720.633   Distancia 2D   0.035",
        "Distancia base   685.889   Elev.   0.012",
    ]
    todo_ok &= _check("Estilo pytesseract (líneas mezcladas)", TOKENS_TESSERACT_STYLE, {
        "Ensayo": "DCP 1",
        "X": "780720.63",
        "Y": "9603591.64",
        "COTA": "786.71",
        "ABS": "-218.16",
    })

    # Captura 3: Código POZO 1 (el caso real que falló - Ensayo salía "SIN CLASIFICAR")
    TOKENS_3 = [
        "Líneas", "EJE 905", "1.250",
        "Nombre", "0.000", "Código", "POZO 1",
        "Dist:960.203m", "Est:K-0+155.907",
        "Cruz: -947.461m", "Relleno: 83.001m",
        "En: -155.907m", "Elev.: 821.999m",
        "N", "9603365.959", "Distancia 2D", "0.005",
        "E", "780807.953", "Elevación", "821.999",
        "Distancia base", "645.261",
    ]
    todo_ok &= _check("Captura 3 (POZO 1)", TOKENS_3, {
        "Ensayo": "POZO 1",
        "X": "780807.95",
        "Y": "9603365.95",
        "COTA": "821.99",
        "ABS": "-155.90",
    })

    # ---- Ruido de OCR típico en el campo "Código" ----
    print("\n== Ensayo con ruido de OCR ==")
    casos_ensayo = [
        ("Código > P0Z0 1", "POZO 1"),       # 0 en vez de O
        ("Código > POZ0 1", "POZO 1"),
        ("Código: Voc 4", "VDC 4"),          # VDC mal leído
        ("NTC 0.000 (LPH VCD3 Y", "VDC 3"),   # OCR transpuso C y D (VCD en vez de VDC)
        ("C6digo > POZO1", "POZO 1"),        # "Código" y número pegados sin espacio
        ("Codigo > DOP 3", "DCP 3"),         # DCP mal leído
        ("sin ningun codigo reconocible aqui", "SIN CLASIFICAR"),
        ("Nombre 0.000 (MA VDCS9 Y", "VDC 9"),  # ruido entre el tipo y el número ("S" espuria)
    ]
    for texto_ocr, esperado in casos_ensayo:
        got = extraer_ensayo(texto_ocr)
        estado = "OK " if got == esperado else "FALLA"
        if got != esperado:
            todo_ok = False
        print(f"  [{estado}] {texto_ocr!r}: esperado={esperado!r} obtenido={got!r}")

    # ---- Ruido de OCR: una "e"/"n" sueltas no deben robar la coordenada ----
    # Caso reportado: un caracter suelto ("e") en algún ícono de la interfaz
    # se confunde con la etiqueta "E" y toma un valor sin relación (ej. de la
    # barra de estado) antes de llegar a la "E" real más abajo en la imagen.
    print("\n== Coordenadas con ruido de OCR (etiqueta E/N espuria) ==")
    TOKENS_RUIDO = [
        "H:0,011",       # ruido de la barra de estado (no es una coordenada)
        "e",             # caracter suelto que NO debe tomarse como "E"
        "H:0,011",       # el número que sigue tampoco es una coordenada real
        "N",             # "N" espuria (ej. un ícono), número corto -> se ignora
        "12",
        "algo de relleno",
        "N",             # la "N" real
        "9111111.11",
        "algo mas",
        "E",             # la "E" real
        "711111.11",
    ]
    coords_ruido = extraer_coordenadas(TOKENS_RUIDO)
    ok = True
    esperado_ruido = {"X": "711111.11", "Y": "9111111.11"}
    for k, v in esperado_ruido.items():
        got = coords_ruido.get(k)
        estado = "OK " if got == v else "FALLA"
        if got != v:
            ok = False
        print(f"  [{estado}] {k}: esperado={v!r}  obtenido={got!r}")
    todo_ok &= ok

    # ---- Casos unitarios de reglas ----
    print("\n== Reglas unitarias ==")
    casos = [
        ("truncar sin redondear 786.719", truncar_2("786.719"), "786.71"),
        ("truncar negativo -218.169", truncar_2("-218.169"), "-218.16"),
        ("abs K-0+218.161", procesar_abs("K-0+218.161"), "-218.16"),
        ("abs K0+154.895 (sin primer signo)", procesar_abs("K0+154.895"), "154.89"),
        ("abs con espacios K - 0 + 99.999", procesar_abs("K - 0 + 99.999"), "-99.99"),
    ]
    for nombre, got, esp in casos:
        estado = "OK " if got == esp else "FALLA"
        if got != esp:
            todo_ok = False
        print(f"  [{estado}] {nombre}: esperado={esp!r} obtenido={got!r}")

    # ---- ABS con OCR dañado (simula errores reales en VDC 3/4) ----
    print("\n== ABS con ruido de OCR ==")
    # Caso A: "Est:" leído como "E5t:" (5 en vez de S, t minúscula)
    got_a = extraer_coordenadas(["E5t: K-0+218.161"])
    ok_a = got_a.get("ABS") == "-218.16"
    todo_ok &= ok_a
    print(f"  [{ 'OK ' if ok_a else 'FALLA'}] E5t:K-0+218.161: esperado='-218.16' obtenido={got_a.get('ABS')!r}")

    # Caso B: OCR separó Est y K en diferentes tokens
    got_b = extraer_coordenadas(["algo", "Est", "K", "-0+", "218.161", "mas"])
    ok_b = got_b.get("ABS") == "-218.16"
    todo_ok &= ok_b
    print(f"  [{ 'OK ' if ok_b else 'FALLA'}] Est/K separado: esperado='-218.16' obtenido={got_b.get('ABS')!r}")

    # Caso C: "Est:" dañado y sin "K-0+" (solo número firmado)
    got_c = extraer_coordenadas(["E5t:", "-218.161"])
    ok_c = got_c.get("ABS") == "-218.16"
    todo_ok &= ok_c
    print(f"  [{ 'OK ' if ok_c else 'FALLA'}] E5t + número directo: esperado='-218.16' obtenido={got_c.get('ABS')!r}")

    # Caso D: "Est:" con K leído como "<"
    got_d = extraer_coordenadas(["Est:< -0+ 154.895"])
    ok_d = got_d.get("ABS") == "-154.89"
    todo_ok &= ok_d
    print(f"  [{ 'OK ' if ok_d else 'FALLA'}] Est:< -0+ 154.895: esperado='-154.89' obtenido={got_d.get('ABS')!r}")

    # Caso E: ABS positivo sin signo, solo K0+
    got_e = extraer_coordenadas(["E5T: K0+ 40.883"])
    ok_e = got_e.get("ABS") == "40.88"
    todo_ok &= ok_e
    print(f"  [{ 'OK ' if ok_e else 'FALLA'}] E5T: K0+ 40.883: esperado='40.88' obtenido={got_e.get('ABS')!r}")

    # Caso F: ABS con km>0 (K1+177.600 -> 1177.60)
    got_f = extraer_coordenadas(["Dist:1249.300m Est:K1+177.600"])
    ok_f = got_f.get("ABS") == "1177.60"
    todo_ok &= ok_f
    print(f"  [{ 'OK ' if ok_f else 'FALLA'}] K1+177.600: esperado='1177.60' obtenido={got_f.get('ABS')!r}")

    # Caso G: ABS con km>0 sin regression (K0+381.265 -> 381.26)
    got_g = extraer_coordenadas(["Dist:1303.502m Est:K0+381.265"])
    ok_g = got_g.get("ABS") == "381.26"
    todo_ok &= ok_g
    print(f"  [{ 'OK ' if ok_g else 'FALLA'}] K0+381.265: esperado='381.26' obtenido={got_g.get('ABS')!r}")

    # Casos reportados: con el modo de OCR por defecto (--psm automático), el
    # campo "Código" se fusiona con elementos vecinos de la interfaz y
    # Tesseract lo lee como texto irreconocible ("PIE", "NULES"...), dando
    # siempre "SIN CLASIFICAR". leer_imagen() prueba varios --psm sobre toda
    # la imagen y, si aun así no clasifica, hace una segunda pasada
    # recortando y releyendo solo el campo "Código" aislado del resto.
    if shutil.which("tesseract"):
        print("\n== OCR extremo a extremo (capturas reales) ==")
        from PIL import Image

        assets_dir = Path(__file__).parent.parent / "assets"
        casos_imagen = [
            ("WhatsApp Image 2026-07-01 at 5.01.34 PM.jpeg",
             {"Ensayo": "DCP 1", "X": "780739.88", "Y": "9603614.20",
              "COTA": "787.39", "ABS": "-196.57"}),
            ("WhatsApp Image 2026-07-10 at 5.01.00 PM - VDC 5.png",
             {"Ensayo": "VDC 5", "X": "781013.33", "Y": "9603298.24",
              "COTA": "838.95", "ABS": "40.88"}),
            ("WhatsApp Image - VDC 4 (2).jpg",
             {"Ensayo": "VDC 4", "X": "780816.71", "Y": "9603295.21",
              "COTA": "825.38", "ABS": "-154.89"}),
            ("WhatsApp Image - DCP 1 (2).jpg",
             {"Ensayo": "DCP 1", "X": "780720.63", "Y": "9603591.64",
              "COTA": "786.71", "ABS": "-218.16"}),
        ]
        for nombre_archivo, esperado in casos_imagen:
            reg, _texto = leer_imagen(Image.open(assets_dir / nombre_archivo))
            ok = True
            print(f"  -- {nombre_archivo} --")
            for k, v in esperado.items():
                got = reg.get(k)
                estado = "OK " if got == v else "FALLA"
                if got != v:
                    ok = False
                print(f"    [{estado}] {k}: esperado={v!r}  obtenido={got!r}")
            todo_ok &= ok
    else:
        print("\n(Se omite el test de OCR extremo a extremo: Tesseract no está instalado)")

    # ---- Conversión UTM -> lat/lon con datum (para el mapa) ----
    try:
        import pyproj  # noqa: F401
        from topo_parser import utm_a_latlon

        print("\n== Conversión UTM -> lat/lon (punto real, zona 17 Sur) ==")
        este, norte = "780816.71", "9603295.21"
        # PSAD56 (datum de las capturas) debe caer ~446 m distinto de WGS84.
        lat_p, lon_p = utm_a_latlon(este, norte, datum="PSAD56")
        lat_w, lon_w = utm_a_latlon(este, norte, datum="WGS84")
        casos_geo = [
            ("PSAD56 lat ~ -3.5889", abs(lat_p - (-3.5889)) < 1e-3, True),
            ("PSAD56 lon ~ -78.4745", abs(lon_p - (-78.4745)) < 1e-3, True),
            ("WGS84  lat ~ -3.5856", abs(lat_w - (-3.5856)) < 1e-3, True),
            ("PSAD56 != WGS84 (hay cambio de datum)", abs(lat_p - lat_w) > 1e-4, True),
            ("vacío -> None", utm_a_latlon("", norte) == (None, None), True),
            ("texto -> None", utm_a_latlon("abc", "xyz") == (None, None), True),
        ]
        for nombre, got, esp in casos_geo:
            estado = "OK " if got == esp else "FALLA"
            if got != esp:
                todo_ok = False
            print(f"  [{estado}] {nombre}")
    except ImportError:
        print("\n(Se omite el test de conversión geográfica: pyproj no está instalado)")

    print("\n" + ("TODOS LOS TESTS PASARON" if todo_ok else "HAY FALLAS"))
    return 0 if todo_ok else 1


if __name__ == "__main__":
    sys.exit(main())
