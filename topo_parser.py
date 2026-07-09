"""
topo_parser.py
Lógica de extracción de datos topográficos a partir del texto OCR.
Sin dependencias de Streamlit/OpenCV -> se puede testear con Python puro.

Reglas de negocio:
  - Ensayo:  se toma de "Código" (ej. "DCP 1", "VDC 4").
  - X:       valor de la fila que dice "E" (Este).
  - Y:       valor de la fila que dice "N" (Norte).
  - COTA:    valor de "Elevación" / "Elev." / "Cota".
  - ABS:     de "Est:K-0+218.161" -> primer signo + número (sin el 0) -> "-218.16".
  - Todos los números se truncan a 2 decimales SIN redondear.
"""
import re
import math

TIPOS = ["POZO", "VDC", "DCP", "TIS", "DCA"]


def truncar_2(valor):
    """Trunca a 2 decimales sin redondear. Devuelve '' si no es número."""
    if valor is None or valor == "":
        return ""
    try:
        v = float(str(valor).replace(" ", "").replace(",", "."))
    except (ValueError, TypeError):
        return ""
    truncado = math.trunc(v * 100) / 100.0
    return f"{truncado:.2f}"


def _num_limpio(texto):
    """Extrae el primer número de un texto y lo normaliza (un solo punto decimal)."""
    if not texto:
        return None
    m = re.search(r"[+-]?\d[\d\s.,]*\d|\d", texto)
    if not m:
        return None
    crudo = m.group(0).replace(" ", "").replace(",", ".")
    if crudo.count(".") > 1:  # 1.234.567 -> el último punto es decimal
        partes = crudo.split(".")
        crudo = "".join(partes[:-1]) + "." + partes[-1]
    return crudo


def procesar_abs(crudo):
    """
    'K-0+218.161' -> '-218.16'   (primer signo, se omite el 0 y el segundo signo)
    'K0+154.895'  -> '154.89'
    """
    if not crudo:
        return ""
    s = str(crudo).upper()
    m = re.search(r"([+-]?)\s*0\s*[+-]\s*(\d+(?:[.,]\d+)?)", s)
    if m:
        signo = m.group(1)
        numero = truncar_2(m.group(2))
        return f"{signo}{numero}" if numero else ""
    # Respaldo: un número suelto
    n = _num_limpio(s)
    return truncar_2(n) if n else ""


def extraer_ensayo(texto):
    """Extrae 'TIPO N' desde el campo Código (o desde el texto si no aparece 'Código')."""
    up = texto.upper()
    patron_tipo = "|".join(TIPOS)
    # 1) Preferir lo que está junto a "Código"
    m = re.search(rf"C[ÓO]DIGO\D{{0,15}}({patron_tipo})\s*0*(\d+)?", up)
    # 2) Si no, cualquier tipo conocido del texto
    if not m:
        m = re.search(rf"\b({patron_tipo})\b\s*0*(\d+)?", up)
    if m:
        tipo = m.group(1)
        num = m.group(2)
        return f"{tipo} {int(num)}" if num else tipo
    return "SIN CLASIFICAR"


def extraer_coordenadas(tokens):
    """
    tokens: lista de textos detectados por el OCR (o un string con saltos de línea).
    Devuelve dict con X, Y, COTA, ABS ya truncados.
    """
    if isinstance(tokens, str):
        tokens = tokens.split("\n")
    tokens = [t.strip() for t in tokens if t and t.strip()]
    full = " ".join(tokens)
    up = full.upper()

    res = {"X": "", "Y": "", "COTA": "", "ABS": ""}

    # ---- X (E) y Y (N) buscando la etiqueta ----
    etiquetas_e = {"E", "E:", "ESTE", "ESTE:"}
    etiquetas_n = {"N", "N:", "NORTE", "NORTE:"}
    for i, tok in enumerate(tokens):
        tu = tok.upper().strip()
        # Etiqueta y número en el mismo token: "E 780720.633"
        me = re.match(r"^E[\s:.\-]+([+-]?\d[\d.,\s]*)$", tu)
        if me and not res["X"]:
            res["X"] = _num_limpio(me.group(1))
        elif tu in etiquetas_e and not res["X"] and i + 1 < len(tokens):
            res["X"] = _num_limpio(tokens[i + 1]) or ""

        mn = re.match(r"^N[\s:.\-]+([+-]?\d[\d.,\s]*)$", tu)
        if mn and not res["Y"]:
            res["Y"] = _num_limpio(mn.group(1))
        elif tu in etiquetas_n and not res["Y"] and i + 1 < len(tokens):
            res["Y"] = _num_limpio(tokens[i + 1]) or ""

    # ---- Respaldo por magnitud (UTM: Norte = 7 dígitos con 9; Este = 6 dígitos) ----
    if not res["X"] or not res["Y"]:
        for crudo in re.findall(r"\d[\d\s.,]*\d", full):
            c = _num_limpio(crudo)
            if not c:
                continue
            entero = c.split(".")[0].lstrip("+-")
            if not res["Y"] and len(entero) == 7 and entero.startswith("9"):
                res["Y"] = c
            elif not res["X"] and len(entero) == 6:
                res["X"] = c

    # ---- COTA / Elevación ----
    mc = re.search(r"(?:ELEVACI[ÓO]N|ELEV|COTA)[^\d+-]{0,6}([+-]?\d+(?:[.,]\d+)?)", up)
    if mc:
        res["COTA"] = _num_limpio(mc.group(1))

    # ---- ABS (Est:K-0+valor) ----
    ma = re.search(r"EST[\s:.]*K\s*([+-]?\s*0\s*[+-]\s*\d+(?:[.,]\d+)?)", up)
    if not ma:
        ma = re.search(r"K\s*([+-]?\s*0\s*[+-]\s*\d+(?:[.,]\d+)?)", up)
    if ma:
        res["ABS"] = procesar_abs(ma.group(1))

    # ---- Truncar X, Y, COTA a 2 decimales ----
    for k in ("X", "Y", "COTA"):
        res[k] = truncar_2(res[k])

    return res


def parsear(tokens):
    """Devuelve el registro completo {Ensayo, X, Y, COTA, ABS}."""
    texto = "\n".join(tokens) if not isinstance(tokens, str) else tokens
    coords = extraer_coordenadas(tokens)
    return {
        "Ensayo": extraer_ensayo(texto),
        "X": coords["X"],
        "Y": coords["Y"],
        "COTA": coords["COTA"],
        "ABS": coords["ABS"],
    }
