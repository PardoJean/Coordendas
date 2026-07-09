# validators.py
"""Validación y normalización de datos extraídos."""
import re
from typing import Optional


def limpiar_decimal(valor: str) -> Optional[float]:
    """
    Normaliza una cadena a número float, manejando puntos, comas y espacios.
    Retorna None si no es convertible.
    """
    if not valor:
        return None
    # Reemplazar todo no dígito/símbolo por espacio vacío, dejando solo punto, coma, signo
    limpio = re.sub(r'[^0-9.,\-+]', '', valor.strip())
    if not limpio:
        return None

    # Manejar múltiples puntos/decimales: si hay más de un separador, el último es el decimal
    partes = re.split(r'[.,]', limpio)
    if len(partes) > 2:
        # Ej: "1.234.567,89" -> "1234567.89"
        try:
            entero = ''.join(partes[:-1])
            decimal = partes[-1]
            return float(f"{entero}.{decimal}")
        except ValueError:
            return None
    else:
        try:
            return float(limpio.replace(',', '.'))
        except ValueError:
            return None


def normalizar_ensayo(texto: str) -> str:
    """
    Normaliza un texto detectado como 'Ensayo', aplicando mapeo y limpieza.
    """
    from src.config import MAPA_CODIGOS
    if not texto:
        return ""
    texto = texto.strip()
    # Buscar en mapeo exacto
    if texto in MAPA_CODIGOS:
        return MAPA_CODIGOS[texto]
    # Intentar con case-insensitive
    for key, val in MAPA_CODIGOS.items():
        if texto.lower() == key.lower():
            return val
    return texto.upper()


def extraer_tipo_numero(ensayo: str) -> tuple:
    """
    Separa el tipo del ensayo y su número.
    Ej: 'POZO 2' -> ('POZO', 2), 'TIS' -> ('TIS', 0)
    """
    if not ensayo:
        return "NO_CLASIFICADO", 0
    match = re.match(r"([A-Za-z]+)\s*(\d*)", ensayo.strip())
    if match:
        tipo = match.group(1).upper()
        num_str = match.group(2)
        try:
            num = int(num_str) if num_str else 0
        except ValueError:
            num = 0
        return tipo, num
    return "NO_CLASIFICADO", 0


def validar_numericos(registro: dict) -> list:
    """
    Valida que X, Y, COTA y ABS sean numéricos si existen.
    Retorna lista de mensajes de advertencia.
    """
    campos = ['X', 'Y', 'COTA', 'ABS']
    warnings = []
    for campo in campos:
        valor = registro.get(campo)
        if valor is not None and valor != "" and not isinstance(valor, (int, float)):
            warnings.append(f"'{campo}' no es numérico: {valor}")
    return warnings
