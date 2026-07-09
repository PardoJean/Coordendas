"""Tests del parser topográfico contra ejemplos reales (capturas de WhatsApp)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from topo_parser import parsear, truncar_2, procesar_abs, extraer_ensayo

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
        ("C6digo > POZO1", "POZO 1"),        # "Código" y número pegados sin espacio
        ("Codigo > DOP 3", "DCP 3"),         # DCP mal leído
        ("sin ningun codigo reconocible aqui", "SIN CLASIFICAR"),
    ]
    for texto_ocr, esperado in casos_ensayo:
        got = extraer_ensayo(texto_ocr)
        estado = "OK " if got == esperado else "FALLA"
        if got != esperado:
            todo_ok = False
        print(f"  [{estado}] {texto_ocr!r}: esperado={esperado!r} obtenido={got!r}")

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

    print("\n" + ("TODOS LOS TESTS PASARON" if todo_ok else "HAY FALLAS"))
    return 0 if todo_ok else 1


if __name__ == "__main__":
    sys.exit(main())
