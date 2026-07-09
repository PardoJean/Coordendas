"""Procesador Topográfico - Versión Web con Streamlit (Standalone)"""
import streamlit as st
import pandas as pd
import io
import numpy as np
from PIL import Image
import re

# Configurar página
st.set_page_config(
    page_title="Procesador Topográfico",
    page_icon="📍",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.title("📍 Procesador Topográfico OCR")

# Cargar OCR con EasyOCR
@st.cache_resource
def cargar_easyocr():
    """Carga EasyOCR de forma segura."""
    try:
        import easyocr
        import warnings
        warnings.filterwarnings('ignore')
        reader = easyocr.Reader(['es', 'en'], gpu=False)
        return reader, True, None
    except ImportError as e:
        return None, False, f"EasyOCR no instalado: {str(e)}"
    except Exception as e:
        return None, False, f"Error cargando EasyOCR: {str(e)}"

ocr, ocr_disponible, ocr_error = cargar_easyocr()

if not ocr_disponible:
    st.error(f"❌ OCR no disponible: {ocr_error}")
    st.info("Intenta recargando la página en 1-2 minutos.")
    st.stop()

# Inicializar sesión
if "datos_procesados" not in st.session_state:
    st.session_state.datos_procesados = []

# ===== FUNCIONES DE PARSING =====

def truncar_decimales(valor_str, decimales=2):
    """Trunca un número a N decimales sin redondear."""
    if not valor_str:
        return ""
    try:
        valor_str = valor_str.replace(',', '.')
        valor = float(valor_str)
        factor = 10 ** decimales
        valor_truncado = int(valor * factor) / factor
        return str(valor_truncado)
    except:
        return valor_str

def procesar_abs(abs_str):
    """Procesa ABS: primer signo + número sin 0 + 2 decimales."""
    if not abs_str:
        return ""
    primer_signo = ""
    if abs_str[0] in ['-', '+']:
        primer_signo = abs_str[0]
        abs_str = abs_str[1:]
    match = re.search(r'0\s*[+-]\s*(\d+[\.,]?\d*)', abs_str)
    if match:
        numero = match.group(1).replace(',', '.')
        numero_limpio = truncar_decimales(numero, decimales=2)
        return f"{primer_signo}{numero_limpio}"
    return abs_str

def extraer_ensayo_completo(texto):
    """Extrae tipo y número del ensayo donde dice 'Código'."""
    texto_upper = texto.upper()
    codigo_match = re.search(r'C[ÓO]DIGO\s*[>\:]?\s*([A-Z]+)\s*(\d+)?', texto_upper)
    if codigo_match:
        tipo = codigo_match.group(1).strip()
        numero = codigo_match.group(2) if codigo_match.group(2) else ""
        tipos_validos = ["POZO", "VDC", "DCP", "TIS", "DCA"]
        for tipo_valido in tipos_validos:
            if tipo_valido in tipo:
                if numero:
                    return f"{tipo_valido} {numero}"
                else:
                    return tipo_valido
    tipos = ["POZO", "VDC", "DCP", "TIS", "DCA"]
    for tipo in tipos:
        if tipo in texto_upper:
            tipo_match = re.search(f'{tipo}\\s*(\\d+)?', texto_upper)
            if tipo_match and tipo_match.group(1):
                return f"{tipo} {tipo_match.group(1)}"
            else:
                return tipo
    return "SIN CLASIFICAR"

def extraer_coordenadas(texto):
    """Extrae X, Y, COTA, ABS del texto OCR."""
    resultado = {"X": "", "Y": "", "COTA": "", "ABS": ""}
    texto_upper = texto.upper()
    lineas = texto.split('\n')

    # Buscar X (donde dice "E")
    for linea in lineas:
        linea_limpia = linea.strip()
        x_match = re.match(r'^E\s+(-?\d+[\.,]?\d*)', linea_limpia)
        if x_match:
            resultado["X"] = x_match.group(1).replace(',', '.')
            break

    # Buscar Y (donde dice "N")
    for linea in lineas:
        linea_limpia = linea.strip()
        y_match = re.match(r'^N\s+(-?\d+[\.,]?\d*)', linea_limpia)
        if y_match:
            resultado["Y"] = y_match.group(1).replace(',', '.')
            break

    # Buscar COTA
    cota_patterns = [
        r'(?:COTA|ELEV|ELEVACIÓN|ELEVATION|ELE[Vv]\.?|ELEY|ELEV\.)\s*[:\.]?\s*(-?\d+[\.,]?\d*)',
        r'CRUZ\s*[:\.]?\s*(-?\d+[\.,]?\d*)',
    ]
    for pattern in cota_patterns:
        cota_match = re.search(pattern, texto_upper)
        if cota_match:
            resultado["COTA"] = cota_match.group(1).replace(',', '.')
            break

    # Buscar ABS
    abs_patterns = [
        r'EST\s*[:\.]?\s*K\s*([-+]?\s*0\s*[+-]\s*\d+[\.,]?\d*)',
        r'K\s*([-+]?\s*0\s*[+-]\s*\d+[\.,]?\d*)',
        r'(?:ABS|STATION|STA)\s*[:\.]?\s*(-?\d+[\.,]?\d*)',
    ]
    for pattern in abs_patterns:
        abs_match = re.search(pattern, texto_upper)
        if abs_match:
            abs_valor = abs_match.group(1)
            abs_valor = re.sub(r'\s+', '', abs_valor)
            resultado["ABS"] = abs_valor
            break

    # Procesar ABS
    if resultado["ABS"]:
        resultado["ABS"] = procesar_abs(resultado["ABS"])

    # Truncar a 2 decimales
    for key in ["X", "Y", "COTA"]:
        if resultado[key]:
            resultado[key] = truncar_decimales(resultado[key], decimales=2)

    return resultado

# ===== INTERFAZ PRINCIPAL =====

st.write("**Copia imagen desde WhatsApp y pégala aquí:**")

# Área de carga
imagenes_subidas = st.file_uploader(
    "Pega imagen aquí (Ctrl+V) o selecciona",
    type=["jpg", "jpeg", "png", "webp"],
    accept_multiple_files=True,
    label_visibility="collapsed"
)

# Botón Procesar
if imagenes_subidas:
    if st.button("▶ PROCESAR", type="primary", use_container_width=True):
        if not ocr_disponible:
            st.error("❌ OCR no disponible")
        else:
            with st.spinner("Procesando..."):
                try:
                    datos_procesados = []
                    errores = []

                    for imagen_archivo in imagenes_subidas:
                        try:
                            pil_img = Image.open(imagen_archivo)
                            img_array = np.array(pil_img)

                            resultados = ocr.readtext(img_array)

                            if resultados:
                                texto_ocr = "\n".join([resultado[1] for resultado in resultados])
                            else:
                                texto_ocr = ""

                            if not texto_ocr:
                                errores.append(f"No se extrajo texto de {imagen_archivo.name}")
                                continue

                            ensayo = extraer_ensayo_completo(texto_ocr)
                            coords = extraer_coordenadas(texto_ocr)

                            registro = {
                                "Ensayo": ensayo,
                                "X": coords["X"],
                                "Y": coords["Y"],
                                "COTA": coords["COTA"],
                                "ABS": coords["ABS"]
                            }

                            datos_procesados.append(registro)

                        except Exception as e:
                            errores.append(f"Error en {imagen_archivo.name}: {str(e)}")

                    if datos_procesados:
                        df = pd.DataFrame(datos_procesados)
                        st.session_state.datos_procesados = datos_procesados

                        st.success(f"✅ {len(datos_procesados)} imagen(es) procesada(s)")

                        # Tabla de resultados
                        st.dataframe(df, use_container_width=True, hide_index=True)

                        # Descargar
                        col1, col2 = st.columns(2)
                        with col1:
                            csv = df.to_csv(index=False)
                            st.download_button("📥 CSV", csv, "coordenadas.csv", "text/csv", use_container_width=True)
                        with col2:
                            output = io.BytesIO()
                            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                                df.to_excel(writer, sheet_name='Coordenadas', index=False)
                            st.download_button("📥 Excel", output.getvalue(), "coordenadas.xlsx",
                                             "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                             use_container_width=True)

                        if errores:
                            st.warning(f"⚠️ {len(errores)} error(es)")
                            for error in errores:
                                st.text(error)
                    else:
                        st.error("❌ No se procesó ninguna imagen")

                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")

# Footer
st.divider()
st.caption("📍 Procesador Topográfico | [GitHub](https://github.com/PardoJean/Coordenadas)")
