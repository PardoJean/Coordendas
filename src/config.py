"""Configuración centralizada del sistema."""
import os
import re
import tempfile
from pathlib import Path
import logging

# ── Logging ───────────────────────────────────────────────────────────────
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

# ── Rutas ───────────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).parent.parent.resolve()
# Usamos carpeta temporal para salida (se limpia automáticamente)
OUTPUT_DIR = Path(tempfile.gettempdir()) / "procesador_topografico"

# ── Extensiones soportadas ────────────────────────────────────────────────
SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}

# ── Prioridad de tipos de ensayo ──────────────────────────────────────────
TIPOS_ORDEN = {
    "POZO": 1,
    "VDC": 2,
    "DCP": 3,
    "TIS": 4,
    "DCA": 5
}

# ── Mapeo normalizado de códigos (por si el OCR introduce variaciones) ──
MAPA_CODIGOS = {
    "POZO": "POZO", "Pozo": "POZO", "pozo": "POZO",
    "Fes": "POZO", "Feso": "POZO", "Pes": "POZO", "Peso": "POZO",
    "Poz": "POZO", "Pos": "POZO", "P0Z0": "POZO", "P0ZO": "POZO", "POZ0": "POZO",
    "VDC": "VDC", "Vdc": "VDC", "vdc": "VDC",
    "Voc": "VDC", "voc": "VDC", "VOC": "VDC",
    "Vuc": "VDC", "VBC": "VDC", "UDC": "VDC",
    "FER": "VDC", "Fer": "VDC", "fer": "VDC",
    "Pyro": "VDC", "pyro": "VDC", "PYRO": "VDC",
    "DCP": "DCP", "Dcp": "DCP", "dcp": "DCP", "DOP": "DCP",
    "TIS": "TIS", "Tis": "TIS", "tis": "TIS",
    "DCA": "DCA", "Dca": "DCA", "dca": "DCA",
}

# Correcciones para errores típicos del OCR
# e.g. 'Fes' → 'Pozo', 'Pyro' → 'VDC'
CORRECCIONES_OCR_CODIGO = {
    # Pozo common misreads
    "Fes": "POZO", "Feso": "POZO", "Pes": "POZO", "Peso": "POZO",
    "Poz": "POZO", "Pos": "POZO", "Pozo": "POZO",
    "P0Z0": "POZO", "P0ZO": "POZO", "POZ0": "POZO",
    # Nuevos errores OCR encontrados
    "eyzeins": "POZO", "Peyzeins": "POZO",
    "Peyzein": "POZO", "Peyzelvan": "POZO", "Peyzelvans": "POZO",
    "Mey4": "POZO", "Mey4e": "POZO", "Mey4ewae": "POZO", "Mey4ewae": "POZO",
    "Mev": "POZO",
    # VDC common misreads
    "PYRO": "VDC", "Pyro": "VDC", "pyro": "VDC",
    "Voc": "VDC", "voc": "VDC", "VOC": "VDC",
    "Vocd": "VDC", "vocd": "VDC",
    "Vuc": "VDC", "vuc": "VDC",
    "VBC": "VDC", "vbc": "VDC",
    "FER": "VDC", "Fer": "VDC", "fer": "VDC",
    "toe": "VDC", "TOE": "VDC", "Toe": "VDC",
    "UDC": "VDC", "Udc": "VDC",
    "VDC": "VDC", "vdc": "VDC", "VdC": "VDC",
    # DCP
    "DCP": "DCP", "dcp": "DCP", "DOP": "DCP", "DcP": "DCP",
    # TIS
    "TIS": "TIS", "tis": "TIS", "Tis": "TIS",
    # DCA
    "DCA": "DCA", "dca": "DCA", "Dca": "DCA",
}

# ── Columnas y encabezados ────────────────────────────────────────────────
COLUMNAS = ["Ensayo", "X", "Y", "COTA", "ABS"]
COLUMNAS_EXCEL = ["Ensayo", "X", "Y", "COTA\n(Si Aplica)", "ABS\n(Si Aplica)"]

# ── Patrones de extracción ─────────────────────────────────────────────────
PATRONES = {
    # --- Ensayo / Código (solo tipo, sin número) --------------------------------
    "tipo_ensayo": re.compile(
        r"\b(POZO|VDC|DCP|TIS|DCA)\b", 
        re.IGNORECASE
    ),
    "codigo_completo": re.compile(
        r"[CcCó][óo]?digo\s*[:>]?\s*([A-Za-z]+\s*\d{0,3})"  # Código > Pozo 1, Codigo > VDC 2
    ),
    "codigo_alt": re.compile(
        r"[Cc]ode\s*[:>]?\s*([A-Za-z]+\s*\d{0,3})"  # Code > VDC 1
    ),
    "ensayo_suelto": re.compile(
        r"\b(POZO|VDC|DCP|TIS|DCA)\s*(\d{0,3})\b",
        re.IGNORECASE
    ),
    "ensayo_suelto_generico": re.compile(
        r"\b([A-Za-z]{1,4})\s*(\d{0,3})\b"  # Captura cualquier combinación tipo Abc 123
    ),

    # --- Coordenada X (Este) ---------------------------------------------
    "x_e": re.compile(
        r"^\s*E\s+([+-]?\d{1,3}(?:[\s,]?\d{3})*(?:\.\d+)?)\s*$",
        re.MULTILINE
    ),
    "x_este": re.compile(
        r"Este\s*[:\.]?\s*([+-]?\d{1,3}(?:[\s,]?\d{3})*(?:\.\d+)?)",
        re.IGNORECASE
    ),
    # Patrón de respaldo: busca números con formato de coordenada UTM Este (~6 dígitos)
    "x_utmp": re.compile(
        r"(?:^|\s)([+-]?\d{6}(?:\.\d+)?)(?:\s|$)",
        re.MULTILINE
    ),

    # --- Coordenada Y (Norte) ----------------------------------------------
    "y_n": re.compile(
        r"^\s*N\s+([+-]?\d{1,3}(?:[\s,]?\d{3})*(?:\.\d+)?)\s*$",
        re.MULTILINE
    ),
    "y_norte": re.compile(
        r"Norte\s*[:\.]?\s*([+-]?\d{1,3}(?:[\s,]?\d{3})*(?:\.\d+)?)",
        re.IGNORECASE
    ),
    # Patrón de respaldo
    "y_utmp": re.compile(
        r"(?:^|\s)([+-]?\d{7}(?:\.\d+)?)(?:\s|$)",
        re.MULTILINE
    ),

    # --- Cota / Elevación -------------------------------------------------
    "cota_elevacion": re.compile(
        r"(?:Eleva(?:ción|tion|tion)|Elev\.?|Cota)\s*[:\.]?\s*([+-]?\d{1,3}(?:[\s,]?\d{3})*(?:\.\d+)?)",
        re.IGNORECASE
    ),
    "cota_suelta": re.compile(
        r"([+-]?\d{1,3}(?:[\s,a-zA-Z]+\d{3})*(?:\.\d+)?)\s*m\b"
    ),

    # --- ABS / Estación ----------------------------------------------------
    "abs_k0": re.compile(
        r"K0\+(\d+(?:\.\d+)?)",
        re.IGNORECASE
    ),
    "abs_sta": re.compile(
        r"(?:Sta|Est|Station)[:\s]+([+-]?\d{1,3}(?:[\s,]?\d{3})*(?:\.\d+)?)",
        re.IGNORECASE
    ),
    "abs_point": re.compile(
        r"Point\s*(?:ID\s+)?([+-]?\d{1,3}(?:[\s,]?\d{3})*(?:\.\d+)?)",
        re.IGNORECASE
    ),
    "abs_linea": re.compile(
        r"^\s*([+-]?\d{1,3}(?:[\s,]?\d{3})*(?:\.\d+)?)\s*$",
        re.MULTILINE
    ),

    # --- Patrones de fallback / genericos usados por el parser ---
    "tipo_fallback": re.compile(
        r'\b(POZO|Pozo|pozo|VDC|Vdc|vdc|Voc|voc|VOC|Vuc|VBC|UDC|FER|Fer|fer|Pyro|pyro|PYRO'
        r'|DCP|Dcp|dcp|DOP'
        r'|TIS|Tis|tis'
        r'|DCA|Dca|dca'
        r'|Fes|Feso|Pes|Peso|Poz|Pos|P0Z0|P0ZO|POZ0)\b',
        re.IGNORECASE
    ),
    "x_fallback": re.compile(r'\b(\d{6}(?:\.\d+)?)\b'),
    "y_fallback": re.compile(r'\b(9\d{6}(?:\.\d+)?)\b'),
    "cota_fallback": re.compile(
        r'(?:Eleva|Cota|Elev|Eley|Eley\.?)[\s:\.\-]*([+-]?\d{1,3}(?:[\s,]?\d{3})*(?:\.\d+)?)',
        re.IGNORECASE
    ),
    "abs_fallback": re.compile(
        r'[Kk]0?\+([+-]?\d+(?:\.\d+)?)|(?:Sta|Est|Station)[:\s]+([+-]?\d{1,3}(?:[\s,]?\d{3})*(?:\.\d+)?)',
        re.IGNORECASE
    ),
}

# ── Configuración del OCR ─────────────────────────────────────────────────
TESSERACT_CMDS = [
    'tesseract',
    r'C:\Program Files\Tesseract-OCR\tesseract.exe',
    r'C:\Users\%USERNAME%\AppData\Local\Tesseract-OCR\tesseract.exe',
]

# ── Umbral para warnings de confianza OCR ─────────────────────────────────
UMBRAL_CONFIANZA = 50  # %
