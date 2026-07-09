# sorter.py
"""Lógica de ordenamiento robusto para registros de topografía."""
from src.config import TIPOS_ORDEN
from src.validators import extraer_tipo_numero


def ordenar_registros(registros: list) -> list:
    """
    Ordena la lista de registros según las reglas:
    1. Prioridad de tipo (POZO > VDC > DCP > TIS > DCA > NO_CLASIFICADO).
    2. Número ascendente dentro del mismo tipo.
    """
    def clave_orden(reg):
        tipo, num = extraer_tipo_numero(reg.get("Ensayo", ""))
        pri = TIPOS_ORDEN.get(tipo, 99)  # Si no está clasificado, va al final
        return (pri, num)

    return sorted(registros, key=clave_orden)


def generar_nombre_ordenado(idx: int, ensayo: str, extension: str = ".jpg") -> str:
    """Genera el nombre de archivo ordenado: 001_POZO_1.jpg"""
    # Limpiar nombre para filesystem
    nombre_seguro = ensayo.replace(" ", "_").replace("/", "_").replace("\\", "_")
    return f"{idx:03d}_{nombre_seguro}{extension.lower()}"
