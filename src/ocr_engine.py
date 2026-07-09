"""
ocr_engine.py
Módulo de preprocesamiento de imagen y extracción OCR robusta.
"""
import cv2
import numpy as np
import pytesseract
import subprocess
import os
import logging
from pathlib import Path
from src.config import TESSERACT_CMDS, UMBRAL_CONFIANZA

logger = logging.getLogger(__name__)


def encontrar_tesseract():
    """Busca el ejecutable de Tesseract en el sistema."""
    # 1. Verificar variable de entorno PYTESSERACT_CMD
    env_path = os.environ.get('PYTESSERACT_CMD')
    if env_path and Path(env_path).exists():
        return env_path
    
    # 2. Verificar en variables de entorno PATH
    for cmd in ['tesseract', 'tesseract.exe']:
        from shutil import which
        path = which(cmd)
        if path:
            return path
    
    # 3. Buscar en rutas comunes de Windows
    import platform
    if platform.system() == 'Windows':
        rutas_comunes = [
            r'C:\Program Files\Tesseract-OCR\tesseract.exe',
            r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
            r'C:\Users\{}\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'.format(os.environ.get('USERNAME', '')),
            r'C:\Users\{}\AppData\Local\Tesseract-OCR\tesseract.exe'.format(os.environ.get('USERNAME', '')),
        ]
        for ruta in rutas_comunes:
            if Path(ruta).exists():
                return ruta
    
    # 4. Verificar archivo de configuración local
    config_local = Path("tesseract_path.txt")
    if config_local.exists():
        ruta = config_local.read_text().strip()
        if Path(ruta).exists():
            return ruta
    
    return None


def configurar_tesseract():
    """Configura la ruta a Tesseract si se encuentra."""
    tesseract_path = encontrar_tesseract()
    if tesseract_path:
        pytesseract.pytesseract.tesseract_cmd = tesseract_path
        logger.info(f"Tesseract configurado en: {tesseract_path}")
        return True
    else:
        logger.error("No se pudo encontrar Tesseract OCR. Por favor, instálalo.")
        return False


def preprocesar_imagen(imagen_bgr):
    """
    Pipeline de preprocesamiento configurable para mejorar el OCR.
    Aplica: escala de grises, ajuste de contraste, nitidez, binarización.
    Incluye recortes estratégicos para la tabla de coordenadas.
    """
    # Convertir a escala de grises si es necesario
    if len(imagen_bgr.shape) == 3:
        gray = cv2.cvtColor(imagen_bgr, cv2.COLOR_BGR2GRAY)
    else:
        gray = imagen_bgr

    alto, ancho = gray.shape[:2]

    # Corrección de contraste (CLAHE) para mejorar contraste local
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)

    # Aumentar nitidez (unsharp mask)
    gaussian = cv2.GaussianBlur(gray, (0, 0), 3.0)
    sharpened = cv2.addWeighted(gray, 1.5, gaussian, -0.5, 0)

    # Binarización adaptativa para dos umbrales diferentes
    binary_inv = cv2.adaptiveThreshold(
        sharpened, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 11, 2
    )
    binary = cv2.adaptiveThreshold(
        sharpened, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 11, 2
    )

    # ── Región inferior: tabla de coordenadas ──────────────────────────
    region_tabla = sharpened[int(alto * 0.75):, :]
    region_tabla_upscaled = cv2.resize(region_tabla, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    clahe_tabla = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4, 4))
    region_tabla_upscaled = clahe_tabla.apply(region_tabla_upscaled)

    # ── Región superior: código del ensayo (header) ────────────────────
    # El título de tipo "Código > Pozo 2" suele estar en la parte superior
    region_header = sharpened[:int(alto * 0.25), :]
    header_h, header_w = region_header.shape
    
    # Si el fondo es oscuro, invertir para texto blanco sobre negro -> negro sobre blanco
    region_header_gray = region_header
    mean_pix = int(region_header_gray.mean())
    if mean_pix < 128:  # fondo oscuro
        region_header_gray = cv2.bitwise_not(region_header_gray)
    
    header_upscaled = cv2.resize(region_header_gray, None, fx=6, fy=6, interpolation=cv2.INTER_CUBIC)
    clahe_header = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8))
    header_upscaled = clahe_header.apply(header_upscaled)
    _, header_thresh = cv2.threshold(header_upscaled, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    return gray, region_tabla_upscaled, binary_inv, header_upscaled, header_thresh


def ejecutar_ocr(imagen_bgr):
    """Ejecuta el OCR sobre una imagen y devuelve el texto extraído."""
    if not configurar_tesseract():
        return "", 0.0

    gray, region_tabla, binary_inv, header_upscaled, header_thresh = preprocesar_imagen(imagen_bgr)

    configs = ['--psm 11 -l spa+eng',
               '--psm 6 -l spa+eng',
               '--psm 4 -l spa+eng']
    cfg_header = '--psm 6 -l spa+eng'

    # ── Extraer texto del HEADER (código tipo Pozo / VDC) ──
    textos_header = set()
    for h in (header_upscaled, header_thresh, gray[:gray.shape[0]//3, :]):
        try:
            th = pytesseract.image_to_string(h, config=cfg_header)
            textos_header.add(th)
        except Exception as e:
            logger.warning(f"Header OCR: {e}")

    # ── Extraer texto de las demás regiones ──
    mejor_texto = ""
    mejor_conf = 0.0
    for img in (gray, region_tabla, binary_inv):
        for cfg in configs:
            try:
                data = pytesseract.image_to_data(img, config=cfg, output_type=pytesseract.Output.DICT)
                confs = [int(c) for c in data['conf'] if int(c) > -1]
                avg_conf = sum(confs) / len(confs) if confs else 0
                texto = pytesseract.image_to_string(img, config=cfg)
                if len(texto) > len(mejor_texto) or (len(texto) == len(mejor_texto) and avg_conf > mejor_conf):
                    mejor_texto = texto
                    mejor_conf = avg_conf
            except Exception as e:
                logger.warning(f"Error OCR: {e}")
                continue

    # Concatenando header + cuerpo (header primero para priorizar códigos)
    texto_final = "\n".join(textos_header) + "\n" + mejor_texto
    return texto_final, mejor_conf
