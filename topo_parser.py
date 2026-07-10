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

# Patrones tolerantes a errores típicos de OCR para cada tipo de ensayo
# (ej. "0" en vez de "O", o palabras que Tesseract confunde por completo).
# Basado en los errores observados en la app de escritorio original.
_PATRONES_TIPO = {
    "POZO": r"P[O0][ZS2][O0]|FES[O0]?|PES[O0]?|POZ|POS\b",
    "VDC": r"VDC|V[O0]C[D0]?|VUC|VBC|UDC|FER|PYR[O0]|T[O0]E",
    "DCP": r"DCP|D[O0]P",
    "TIS": r"TIS",
    "DCA": r"DCA",
}


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


def _region_codigo(up):
    """Recorta ~25 caracteres después de 'Código' (tolerante a OCR ruidoso)."""
    m = re.search(r"C[ÓO0][D0]IG[O0]", up)
    if not m:
        return None
    return up[m.end():m.end() + 25]


def extraer_ensayo(texto):
    """Extrae 'TIPO N' desde el campo Código, tolerando errores comunes de OCR
    (ej. 'P0Z0', 'POZ0', 'Voc' -> se normalizan a POZO/VDC/etc.)."""
    up = texto.upper()

    def _buscar_en(region):
        mejor = None  # (posición, tipo, texto_coincidente)
        for tipo, patron in _PATRONES_TIPO.items():
            m = re.search(patron, region)
            if m and (mejor is None or m.start() < mejor[0]):
                mejor = (m.start(), tipo, m)
        return mejor

    # 1) Preferir la región justo después de "Código"
    region = _region_codigo(up)
    resultado = _buscar_en(region) if region else None
    texto_busqueda = region

    # 2) Si no aparece "Código" o no hay match ahí, buscar en todo el texto
    if not resultado:
        resultado = _buscar_en(up)
        texto_busqueda = up

    if not resultado:
        return "SIN CLASIFICAR"

    _, tipo, m = resultado
    # Número justo después de la coincidencia (ignorando ceros a la izquierda)
    resto = texto_busqueda[m.end():m.end() + 10]
    mnum = re.match(r"\s*0*(\d{1,3})", resto)
    return f"{tipo} {int(mnum.group(1))}" if mnum else tipo


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


# Zona UTM por defecto (proyecto en Zamora Chinchipe, Ecuador -> zona 17 Sur).
ZONA_UTM_DEFECTO = 17


def utm_a_latlon(este, norte, zona=ZONA_UTM_DEFECTO, hemisferio_norte=False):
    """Convierte una coordenada UTM (Este=X, Norte=Y) a (latitud, longitud) en
    grados decimales, para poder ubicar el punto en un mapa. Devuelve
    (None, None) si los valores no son numéricos o caen fuera de rango."""
    try:
        e = float(str(este).replace(" ", "").replace(",", "."))
        n = float(str(norte).replace(" ", "").replace(",", "."))
    except (ValueError, TypeError):
        return None, None
    if e == 0 or n == 0:
        return None, None
    try:
        import utm
        lat, lon = utm.to_latlon(e, n, zona, northern=hemisferio_norte)
        return lat, lon
    except Exception:  # noqa: BLE001  (coordenada inválida para la zona, etc.)
        return None, None


COLUMNAS = ["Ensayo", "X", "Y", "COTA", "ABS"]

# Modos de segmentación de página (--psm) de Tesseract a probar, en orden.
# El modo por defecto (segmentación automática) suele fusionar el campo
# "Código" con elementos vecinos de la interfaz (flechas, iconos) y producir
# texto irreconocible; --psm 6 (bloque uniforme de texto) resultó mucho más
# fiable en pruebas con capturas reales de la app de topografía.
PSM_INTENTOS = (6, 4, 3, 11)


def _puntuar(reg):
    """Cuenta cuántos campos quedaron completos (Ensayo clasificado + datos no vacíos)."""
    puntos = 0
    for c in COLUMNAS:
        valor = reg.get(c, "")
        if c == "Ensayo":
            if valor and valor != "SIN CLASIFICAR":
                puntos += 1
        elif valor != "":
            puntos += 1
    return puntos


_PATRON_ETIQUETA_CODIGO = re.compile(r"C[óÓO0]d[i1]go", re.I)

# --psm para localizar la palabra "Código" dentro de la captura completa
# (necesitamos las coordenadas de la palabra, por eso se usa image_to_data).
_PSM_BUSCAR_CODIGO = (3, 4, 11, 12, 6)
# --psm para releer, ya recortado, solo el valor que está al lado de "Código".
_PSM_RECORTE_CODIGO = (11, 6, 7)


def _recortar_valor_codigo(rgb_img, pytesseract):
    """Ubica la palabra 'Código' en la captura (vía datos de posición de
    Tesseract) y devuelve un recorte de la zona inmediatamente a su derecha,
    donde está el valor (ej. 'DCP 1', 'VDC 5'). Devuelve None si no se
    encuentra la etiqueta con confianza suficiente."""
    for psm in _PSM_BUSCAR_CODIGO:
        datos = pytesseract.image_to_data(
            rgb_img, lang="spa+eng", config=f"--psm {psm}",
            output_type=pytesseract.Output.DICT,
        )
        for i, txt in enumerate(datos["text"]):
            if not _PATRON_ETIQUETA_CODIGO.search(txt or ""):
                continue
            try:
                conf = int(float(datos["conf"][i]))
            except (ValueError, TypeError):
                conf = -1
            if conf < 40:
                continue
            izq, arriba, ancho, alto = (
                datos["left"][i], datos["top"][i], datos["width"][i], datos["height"][i],
            )
            alto = min(alto, 60)  # descarta cajas anormalmente altas (ruido de OCR)
            relleno_y = max(12, int(alto * 0.35))
            x0 = min(izq + ancho + 12, rgb_img.width - 10)
            x1 = min(x0 + 380, rgb_img.width)
            y0 = max(arriba - relleno_y, 0)
            y1 = min(arriba + alto + relleno_y, rgb_img.height)
            if x1 - x0 < 20:
                continue
            return rgb_img.crop((x0, y0, x1, y1))
    return None


def _clasificar_por_recorte(rgb_img, pytesseract):
    """Segunda pasada dirigida solo al campo 'Código': lo recorta y lo vuelve
    a leer aislado del resto de la interfaz. El texto completo de la captura
    suele confundir a Tesseract (el valor de 'Código' se funde con iconos
    vecinos); aislado, se lee con mucha más fiabilidad."""
    recorte = _recortar_valor_codigo(rgb_img, pytesseract)
    if recorte is None:
        return None
    for psm in _PSM_RECORTE_CODIGO:
        texto = pytesseract.image_to_string(recorte, lang="spa+eng", config=f"--psm {psm}")
        ensayo = extraer_ensayo(texto)
        if ensayo != "SIN CLASIFICAR":
            return ensayo
    return None


def leer_imagen(img_pil):
    """Corre OCR (pytesseract) sobre una imagen PIL probando varios --psm y se
    queda con el resultado más completo. Si el 'Ensayo' no queda clasificado,
    hace una segunda pasada recortando y releyendo solo el campo 'Código'
    (ver _clasificar_por_recorte). Devuelve (registro, texto_ocr_crudo)."""
    import pytesseract

    rgb = img_pil.convert("RGB")
    mejor_reg, mejor_texto, mejor_puntos = None, "", -1
    for psm in PSM_INTENTOS:
        texto = pytesseract.image_to_string(rgb, lang="spa+eng", config=f"--psm {psm}")
        reg = parsear(texto)
        puntos = _puntuar(reg)
        if puntos > mejor_puntos:
            mejor_reg, mejor_texto, mejor_puntos = reg, texto, puntos
        if puntos == len(COLUMNAS):
            break  # ya se extrajeron todos los campos, no hace falta seguir probando

    if mejor_reg.get("Ensayo") == "SIN CLASIFICAR":
        ensayo_recorte = _clasificar_por_recorte(rgb, pytesseract)
        if ensayo_recorte:
            mejor_reg = {**mejor_reg, "Ensayo": ensayo_recorte}

    return mejor_reg, mejor_texto
