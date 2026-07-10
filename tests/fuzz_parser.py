"""
fuzz_parser.py
Prueba de robustez por mutación (fuzzing) para topo_parser.py.

Idea: a partir de capturas "doradas" (con su resultado correcto ya
verificado), se generan muchas variaciones agregando el mismo TIPO de ruido
que produce Tesseract en la vida real (letras sueltas que parecen una
etiqueta "E"/"N", un caracter espurio metido entre el tipo de ensayo y su
número, tokens basura de íconos, etc.) y se exige que el resultado siga
siendo el correcto. Así se atrapan bugs de esta familia (como los dos
corregidos a partir de capturas reales de producción) antes de que aparezcan
en una captura real.

No cambia el contenido informativo (los dígitos reales de Ensayo/X/Y/COTA/
ABS) — solo agrega ruido alrededor, así que el resultado esperado no cambia.

Uso: python tests/fuzz_parser.py [--trials N] [--seed S]
"""
import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from topo_parser import parsear

# ---- Capturas doradas (mismas que tests/test_topo_parser.py) ----
CASOS_DORADOS = [
    ("Captura 1 (DCP 1)", [
        "Líneas", "eje 905", "1.250", "Nombre", "-218.161", "Código", "DCP 1",
        "Dist:1181.302m", "Est:K-0+218.161", "Cruz: -1181.302m", "Relleno: 118.285m",
        "Elev.: 786.715m", "N", "9603591.641", "Elevación", "786.715", "E", "780720.633",
        "Distancia 2D", "0.035", "Distancia base", "685.889", "Elev.", "0.012",
    ], {"Ensayo": "DCP 1", "X": "780720.63", "Y": "9603591.64", "COTA": "786.71", "ABS": "-218.16"}),

    ("Captura 2 (VDC 4)", [
        "Líneas", "EJE 905", "1.250", "Nombre", "0.000", "Código", "VDC 4",
        "Dist:889.772m", "Est:K-0+154.895", "Cruz: -876.186m", "Relleno: 79.613m",
        "Elev.: 825.387m", "N", "9603295.217", "Distancia 2D", "0.010", "E", "780816.712",
        "Elevación", "825.387", "Distancia base", "667.181",
    ], {"Ensayo": "VDC 4", "X": "780816.71", "Y": "9603295.21", "COTA": "825.38", "ABS": "-154.89"}),

    ("Captura 3 (POZO 1)", [
        "Líneas", "EJE 905", "1.250", "Nombre", "0.000", "Código", "POZO 1",
        "Dist:960.203m", "Est:K-0+155.907", "Cruz: -947.461m", "Relleno: 83.001m",
        "En: -155.907m", "Elev.: 821.999m", "N", "9603365.959", "Distancia 2D", "0.005",
        "E", "780807.953", "Elevación", "821.999", "Distancia base", "645.261",
    ], {"Ensayo": "POZO 1", "X": "780807.95", "Y": "9603365.95", "COTA": "821.99", "ABS": "-155.90"}),
]

TOKENS_BASURA_ICONO = ["AR", "LJ", "«", "»", "O", "o", "A", "a", ".", "-", "()", "[]", "?", "*"]
LETRAS_ETIQUETA_ESPURIA = ["e", "E", "n", "N"]


def _insertar(tokens, indice, token):
    tokens.insert(max(0, min(indice, len(tokens))), token)


def mutar(tokens, rng):
    """Aplica una combinación aleatoria de ruido tipo-OCR a una copia de tokens."""
    t = list(tokens)

    # 1) Insertar 1-3 tokens basura de "íconos" en posiciones aleatorias.
    for _ in range(rng.randint(1, 3)):
        _insertar(t, rng.randint(0, len(t)), rng.choice(TOKENS_BASURA_ICONO))

    # 2) Insertar UNA etiqueta "E"/"N" espuria (letra suelta) seguida de un
    #    número corto e implausible como coordenada (esto es exactamente el
    #    bug real: un ícono mal leído como "e" con un valor sin relación al
    #    lado, como la barra de estado del celular). Se evita pegarla justo
    #    al lado de una "E"/"N" real: dos etiquetas reales seguidas no es un
    #    patrón que Tesseract produzca en la práctica, y left la ambigüedad
    #    resultante no tiene una respuesta correcta única.
    if rng.random() < 0.6:
        etiquetas_reales = {"E", "N", "E:", "N:", "ESTE", "NORTE", "ESTE:", "NORTE:"}
        posiciones_validas = [
            p for p in range(len(t) + 1)
            if (p == 0 or t[p - 1].upper().strip() not in etiquetas_reales)
            and (p == len(t) or t[p].upper().strip() not in etiquetas_reales)
        ]
        if posiciones_validas:
            pos = rng.choice(posiciones_validas)
            _insertar(t, pos, str(rng.randint(0, 9999)))
            _insertar(t, pos, rng.choice(LETRAS_ETIQUETA_ESPURIA))

    # 3) Meter un caracter espurio entre el tipo de ensayo y su número en el
    #    token "Código" (ej. "DCP 1" -> "DCP·1"), simulando que el OCR leyó
    #    mal el espacio como un caracter random.
    for i, tok in enumerate(t):
        if tok == "Código" and i + 1 < len(t):
            valor = t[i + 1]
            partes = valor.split(" ", 1)
            if len(partes) == 2 and rng.random() < 0.7:
                ruido = rng.choice(["·", "S", "|", "_", "»"]) * rng.randint(1, 2)
                t[i + 1] = f"{partes[0]}{ruido}{partes[1]}"
            break

    # 4) Reordenar un poco los tokens de basura de íconos entre sí (no debería
    #    importar el orden de cosas que no coinciden con ningún patrón).
    indices_basura = [i for i, tok in enumerate(t) if tok in TOKENS_BASURA_ICONO]
    if len(indices_basura) >= 2:
        valores = [t[i] for i in indices_basura]
        rng.shuffle(valores)
        for i, v in zip(indices_basura, valores):
            t[i] = v

    return t


def _es_falla_segura(esperado, obtenido):
    """Con ruido de OCR suficientemente denso, a veces no hay forma de saber
    con certeza cuál número pertenece a cuál campo -> es aceptable que el
    campo quede vacío (se nota en la tabla y se corrige a mano). Lo que NO es
    aceptable nunca es insertar un valor equivocado sin que se note."""
    for campo, val_esperado in esperado.items():
        val_obtenido = obtenido.get(campo)
        if val_obtenido != val_esperado and val_obtenido not in ("", "SIN CLASIFICAR"):
            return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=500, help="mutaciones por caso dorado")
    ap.add_argument("--seed", type=int, default=42, help="semilla (reproducible)")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    total = 0
    fallas_inseguras = []
    fallas_seguras = 0

    for nombre, tokens, esperado in CASOS_DORADOS:
        for prueba in range(args.trials):
            total += 1
            mutados = mutar(tokens, rng)
            resultado = parsear(mutados)
            if resultado == esperado:
                continue
            if _es_falla_segura(esperado, resultado):
                fallas_seguras += 1
            else:
                fallas_inseguras.append((nombre, prueba, mutados, esperado, resultado))
                if len(fallas_inseguras) >= 20:  # no inundar la salida
                    break

    print(f"Casos dorados: {len(CASOS_DORADOS)}  ·  Mutaciones por caso: {args.trials}  ·  Total: {total}")
    print(f"Fallas seguras (campo vacío, sin dato equivocado): {fallas_seguras}")

    if not fallas_inseguras:
        print("SIN FALLAS INSEGURAS: ninguna mutación insertó un valor incorrecto sin avisar.")
        return 0

    print(f"\n{len(fallas_inseguras)} FALLA(S) INSEGURA(S) — valor incorrecto sin avisar (mostrando hasta 20):\n")
    for nombre, prueba, mutados, esperado, obtenido in fallas_inseguras:
        print(f"-- {nombre} (mutación #{prueba}) --")
        print(f"  tokens: {mutados}")
        print(f"  esperado: {esperado}")
        print(f"  obtenido: {obtenido}\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
