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

# Prioridad de ordenamiento de tipos de ensayo (menor = primero).
TIPOS_ORDEN = {"POZO": 1, "VDC": 2, "DCP": 3, "TIS": 4, "DCA": 5}

# Simbología por tipo: color RGB + radio en píxeles + marcador matplotlib.
SIMBOLOGIA = {
    "POZO": {"color": (220, 38, 38), "radio": 8, "marcador": "o"},
    "VDC":  {"color": (37, 99, 235), "radio": 7, "marcador": "^"},
    "DCP":  {"color": (22, 163, 74), "radio": 6, "marcador": "s"},
    "TIS":  {"color": (202, 138, 4), "radio": 7, "marcador": "D"},
    "DCA":  {"color": (147, 51, 234), "radio": 8, "marcador": "*"},
}
_SIMBOLOGIA_SIN = {"color": (107, 114, 128), "radio": 6, "marcador": "o"}


def extraer_tipo_numero(ensayo):
    """Separa 'POZO 1' → ('POZO', 1), 'SIN CLASIFICAR' → ('SIN', 0)."""
    if not ensayo:
        return "SIN CLASIFICAR", 0
    m = re.match(r"([A-Za-z]+)\s*(\d*)", ensayo.strip())
    if m:
        tipo = m.group(1).upper()
        try:
            num = int(m.group(2)) if m.group(2) else 0
        except ValueError:
            num = 0
        return tipo, num
    return "SIN CLASIFICAR", 0


def ordenar_registros(registros):
    """Ordena por prioridad de tipo (POZO<VDC<DCP<TIS<DCA) y número ascendente."""
    def _clave(r):
        tipo, num = extraer_tipo_numero(r.get("Ensayo", ""))
        pri = TIPOS_ORDEN.get(tipo, 99)
        return (pri, num)
    return sorted(registros, key=_clave)


def simbologia_para(ensayo):
    """Devuelve color, radio, marcador para el tipo de ensayo."""
    tipo, _ = extraer_tipo_numero(ensayo)
    return SIMBOLOGIA.get(tipo) or _SIMBOLOGIA_SIN

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
    # Número justo después de la coincidencia (ignorando ceros a la izquierda).
    # Se toleran 1-3 caracteres de ruido de OCR entre el tipo y el número
    # (ej. "VDCS5" -> el OCR mete una "S" espuria entre "VDC" y "5").
    resto = texto_busqueda[m.end():m.end() + 10]
    mnum = re.match(r"[^\d]{0,3}0*(\d{1,3})", resto)
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

    def _parece_coordenada_utm(valor):
        """Una 'E'/'N' sueltas de un solo caracter son un imán para ruido de
        OCR (iconos, letras mal leídas de otra parte de la pantalla). Antes
        de aceptar el número que las sigue como coordenada, exige que tenga
        pinta de UTM real (parte entera larga)."""
        if not valor:
            return False
        entero = valor.split(".")[0].lstrip("+-")
        return len(entero) >= 5

    def _buscar_valor_cercano(tokens, desde, ventana=1):
        """Busca, en los siguientes `ventana` tokens, el primero que tenga
        pinta de coordenada UTM real. Tolera que se haya colado un token de
        ruido justo entre la etiqueta ('E'/'N') y su valor real, pero se
        detiene apenas aparece OTRA etiqueta E/N: cruzarla significaría
        robarle el valor al campo siguiente."""
        for j in range(desde, min(desde + ventana, len(tokens))):
            tu_j = tokens[j].upper().strip()
            if tu_j in etiquetas_e or tu_j in etiquetas_n:
                break
            candidato = _num_limpio(tokens[j]) or ""
            if _parece_coordenada_utm(candidato):
                return candidato
        return ""

    for i, tok in enumerate(tokens):
        tu = tok.upper().strip()
        # Etiqueta y número en el mismo token: "E 780720.633"
        me = re.match(r"^E[\s:.\-]+([+-]?\d[\d.,\s]*)$", tu)
        if me and not res["X"]:
            res["X"] = _num_limpio(me.group(1))
        elif tu in etiquetas_e and not res["X"] and i + 1 < len(tokens):
            candidato = _buscar_valor_cercano(tokens, i + 1)
            if candidato:
                res["X"] = candidato

        mn = re.match(r"^N[\s:.\-]+([+-]?\d[\d.,\s]*)$", tu)
        if mn and not res["Y"]:
            res["Y"] = _num_limpio(mn.group(1))
        elif tu in etiquetas_n and not res["Y"] and i + 1 < len(tokens):
            candidato = _buscar_valor_cercano(tokens, i + 1)
            if candidato:
                res["Y"] = candidato

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
# Datum por defecto de las capturas de topografía en Ecuador.
DATUM_DEFECTO = "PSAD56"
DATUMS = ("PSAD56", "WGS84")


def _epsg_utm(zona, hemisferio_norte, datum):
    """Código EPSG del sistema UTM de origen según zona, hemisferio y datum.

    Los equipos de topografía en Ecuador suelen entregar coordenadas en
    PSAD56 (datum sudamericano provisional 1956), que difiere de WGS84 —el
    datum de los mapas web— en varios cientos de metros. Usar el EPSG correcto
    permite que pyproj aplique la transformación de datum al pasar a lat/lon."""
    zona = int(zona)
    if str(datum).upper().startswith("WGS"):
        return 32600 + zona if hemisferio_norte else 32700 + zona
    # PSAD56 (zonas de Ecuador/Perú): norte 24800+zona, sur 24860+zona.
    return 24800 + zona if hemisferio_norte else 24860 + zona


def _transformador(epsg_origen):
    """Devuelve (y cachea) el Transformer de EPSG origen a WGS84 lat/lon."""
    import functools
    from pyproj import Transformer

    @functools.lru_cache(maxsize=None)
    def _cache(codigo):
        return Transformer.from_crs(f"EPSG:{codigo}", "EPSG:4326", always_xy=True)

    _transformador._cache = getattr(_transformador, "_cache", _cache)
    return _transformador._cache(epsg_origen)


def utm_a_latlon(este, norte, zona=ZONA_UTM_DEFECTO, hemisferio_norte=False,
                 datum=DATUM_DEFECTO):
    """Convierte una coordenada UTM (Este=X, Norte=Y) a (latitud, longitud) en
    grados decimales WGS84, para ubicar el punto en un mapa. Aplica la
    transformación de datum correspondiente (PSAD56 por defecto, como entregan
    los equipos en Ecuador). Devuelve (None, None) si los valores no son
    numéricos o la transformación falla."""
    try:
        e = float(str(este).replace(" ", "").replace(",", "."))
        n = float(str(norte).replace(" ", "").replace(",", "."))
    except (ValueError, TypeError):
        return None, None
    if e == 0 or n == 0:
        return None, None
    try:
        epsg = _epsg_utm(zona, hemisferio_norte, datum)
        lon, lat = _transformador(epsg).transform(e, n)
        if lat != lat or lon != lon:  # NaN -> fuera de rango para esa zona/datum
            return None, None
        return lat, lon
    except Exception:  # noqa: BLE001  (EPSG desconocido, coordenada inválida, etc.)
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
