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
    initial_sidebar_state="expanded"
)

st.title("📍 Procesador Topográfico OCR")
st.markdown("Extrae datos topográficos de imágenes usando OCR y genera Excel listo para usar.")

# Cargar OCR con EasyOCR (más ligero que PaddleOCR)
@st.cache_resource
def cargar_easyocr():
    """Carga EasyOCR de forma segura."""
    try:
        import easyocr
        import warnings
        warnings.filterwarnings('ignore')

        st.info("⏳ Inicializando modelo OCR (primera vez puede tomar 1-2 minutos)...")
        reader = easyocr.Reader(['es', 'en'], gpu=False)
        return reader, True, None
    except ImportError as e:
        return None, False, f"EasyOCR no instalado: {str(e)}"
    except Exception as e:
        return None, False, f"Error cargando EasyOCR: {str(e)}"

ocr, ocr_disponible, ocr_error = cargar_easyocr()

# Mostrar estado del OCR
if not ocr_disponible:
    with st.warning("⚠️ OCR no disponible"):
        st.error(f"Error: {ocr_error}")
        st.info("Intenta recargando la página en 1-2 minutos.")

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuración")
    st.info("Sube imágenes de topografía (.jpg, .png, .webp) para procesar automáticamente.")

# Inicializar sesión
if "datos_procesados" not in st.session_state:
    st.session_state.datos_procesados = []

# Funciones simples de parsing sin dependencias
def extraer_tipo_ensayo(texto):
    """Extrae el tipo de ensayo (POZO, VDC, DCP, TIS, DCA)."""
    tipos = ["POZO", "VDC", "DCP", "TIS", "DCA"]
    for tipo in tipos:
        if tipo in texto.upper():
            return tipo
    return "SIN CLASIFICAR"

def extraer_numero(texto):
    """Extrae el número del ensayo."""
    numeros = re.findall(r'\d+', texto)
    if numeros:
        try:
            return int(numeros[0])
        except:
            return 0
    return 0

def limpiar_numero(texto):
    """Limpia espacios y caracteres especiales de números."""
    if not texto:
        return ""
    return re.sub(r'[\s,]', '', texto)

def truncar_decimales(valor_str, decimales=2):
    """Trunca un número a N decimales sin redondear."""
    if not valor_str:
        return ""
    try:
        # Limpiar el string
        valor_str = valor_str.replace(',', '.')
        valor = float(valor_str)
        # Truncar sin redondear
        factor = 10 ** decimales
        valor_truncado = int(valor * factor) / factor
        return str(valor_truncado)
    except:
        return valor_str

def extraer_coordenadas(texto):
    """Extrae X, Y, COTA, ABS del texto OCR con precisión."""
    resultado = {"X": "", "Y": "", "COTA": "", "ABS": ""}

    # Convertir a mayúsculas para búsqueda
    texto_upper = texto.upper()
    lineas = texto.split('\n')

    # Buscar X (donde dice "E") - busca línea que empieza con E seguida de números
    for linea in lineas:
        linea_limpia = linea.strip()
        x_match = re.match(r'^E\s+(-?\d+[\.,]?\d*)', linea_limpia)
        if x_match:
            resultado["X"] = limpiar_numero(x_match.group(1))
            break

    # Si no encuentra con E al inicio, buscar patrón más flexible
    if not resultado["X"]:
        x_match = re.search(r'\bE\s+(-?\d{6,7}[\.,]?\d*)', texto_upper)
        if x_match:
            resultado["X"] = limpiar_numero(x_match.group(1))

    # Buscar Y (donde dice "N") - busca línea que empieza con N seguida de números
    for linea in lineas:
        linea_limpia = linea.strip()
        y_match = re.match(r'^N\s+(-?\d+[\.,]?\d*)', linea_limpia)
        if y_match:
            resultado["Y"] = limpiar_numero(y_match.group(1))
            break

    # Si no encuentra con N al inicio, buscar patrón más flexible
    if not resultado["Y"]:
        y_match = re.search(r'\bN\s+(-?\d{6,7}[\.,]?\d*)', texto_upper)
        if y_match:
            resultado["Y"] = limpiar_numero(y_match.group(1))

    # Buscar COTA/ELEVACIÓN - número con signo negativo o positivo
    cota_patterns = [
        r'(?:COTA|ELEV|ELEVACIÓN|ELEVATION|ELE[Vv]\.?|ELEY|ELEV\.)\s*[:\.]?\s*(-?\d+[\.,]?\d*)',
        r'CRUZ\s*[:\.]?\s*(-?\d+[\.,]?\d*)',  # También busca en "Cruz"
    ]
    for pattern in cota_patterns:
        cota_match = re.search(pattern, texto_upper)
        if cota_match:
            resultado["COTA"] = limpiar_numero(cota_match.group(1))
            break

    # Buscar ABS (Estación) - Est:K-0+valor o K0+valor
    abs_patterns = [
        r'EST\s*[:\.]?\s*K\s*-?\s*0\s*\+\s*(-?\d+[\.,]?\d*)',  # Est:K-0+218.161
        r'K\s*-?\s*0\s*\+\s*(-?\d+[\.,]?\d*)',  # K-0+valor o K0+valor
        r'(?:ABS|STATION|STA)\s*[:\.]?\s*(-?\d+[\.,]?\d*)',
    ]
    for pattern in abs_patterns:
        abs_match = re.search(pattern, texto_upper)
        if abs_match:
            resultado["ABS"] = limpiar_numero(abs_match.group(1))
            break

    # Aplicar truncado a 2 decimales sin redondear
    for key in resultado:
        if resultado[key]:
            resultado[key] = truncar_decimales(resultado[key], decimales=2)

    return resultado

# Carga de imágenes
st.subheader("1️⃣ Cargar Imágenes")
imagenes_subidas = st.file_uploader(
    "Selecciona imágenes de topografía",
    type=["jpg", "jpeg", "png", "webp"],
    accept_multiple_files=True,
    help="Puedes seleccionar varias imágenes a la vez"
)

# Botones
col1, col2 = st.columns(2)

with col1:
    procesar_btn = st.button("▶ Procesar Imágenes", type="primary", use_container_width=True)

with col2:
    limpiar_btn = st.button("🗑️ Limpiar Todo", use_container_width=True)

if limpiar_btn:
    st.session_state.datos_procesados = []
    st.rerun()

# Procesar imágenes
if procesar_btn and imagenes_subidas:
    if not ocr_disponible:
        st.error(f"❌ OCR no está disponible. Razón: {ocr_error}\n\nIntenta recargando la página en 1-2 minutos.")
    else:
        with st.spinner("⏳ Procesando imágenes con OCR..."):
            try:
                datos_procesados = []
                errores = []

                for idx, imagen_archivo in enumerate(imagenes_subidas, 1):
                    try:
                        # Leer imagen
                        pil_img = Image.open(imagen_archivo)
                        img_array = np.array(pil_img)

                        # Procesar OCR con EasyOCR
                        resultados = ocr.readtext(img_array)

                        # Extraer texto de resultados de EasyOCR
                        if resultados:
                            texto_ocr = "\n".join([resultado[1] for resultado in resultados])
                        else:
                            texto_ocr = ""

                        if not texto_ocr:
                            errores.append(f"No se extrajo texto de {imagen_archivo.name}")
                            continue

                        # Parsear datos
                        tipo = extraer_tipo_ensayo(texto_ocr)
                        numero = extraer_numero(texto_ocr)
                        coords = extraer_coordenadas(texto_ocr)

                        registro = {
                            "Ensayo": f"{tipo} {numero}".strip() if numero > 0 else tipo,
                            "X": coords["X"],
                            "Y": coords["Y"],
                            "COTA": coords["COTA"],
                            "ABS": coords["ABS"],
                            "Imagen": imagen_archivo.name
                        }

                        datos_procesados.append(registro)

                    except Exception as e:
                        errores.append(f"Error en {imagen_archivo.name}: {str(e)}")

                # Ordenar registros
                if datos_procesados:
                    # Convertir a DataFrame para ordenar
                    df_temp = pd.DataFrame(datos_procesados)
                    df_temp = df_temp.sort_values("Ensayo")
                    datos_procesados = df_temp.to_dict('records')

                    st.session_state.datos_procesados = datos_procesados
                    st.success(f"✅ Se procesaron {len(datos_procesados)} imágenes correctamente")

                    if errores:
                        with st.warning(f"⚠️ {len(errores)} advertencia(s)"):
                            for error in errores:
                                st.text(error)
                else:
                    st.error("❌ No se pudo procesar ninguna imagen")
                    for error in errores:
                        st.error(error)

            except Exception as e:
                st.error(f"❌ Error: {str(e)}")

# Mostrar y editar datos
if st.session_state.datos_procesados:
    st.subheader("2️⃣ Vista Previa y Edición")

    # DataFrame editable
    df_editada = st.data_editor(
        pd.DataFrame(st.session_state.datos_procesados),
        use_container_width=True,
        hide_index=False,
        num_rows="dynamic"
    )

    # Actualizar datos
    st.session_state.datos_procesados = df_editada.to_dict('records')

    # Estadísticas
    st.subheader("📊 Estadísticas")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total de Registros", len(df_editada))
    with col2:
        tipos = df_editada["Ensayo"].nunique() if "Ensayo" in df_editada.columns else 0
        st.metric("Tipos de Ensayo", tipos)
    with col3:
        vacios = df_editada.isna().sum().sum()
        st.metric("Campos Vacíos", vacios)
    with col4:
        st.metric("Archivos Procesados", len(st.session_state.datos_procesados))

    # Descargar
    st.subheader("3️⃣ Descargar Resultados")

    col1, col2 = st.columns(2)

    with col1:
        # Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_editada.to_excel(writer, sheet_name='Coordenadas', index=False)

        excel_data = output.getvalue()
        st.download_button(
            label="📥 Descargar Excel",
            data=excel_data,
            file_name="resultado.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

    with col2:
        # CSV
        csv_data = df_editada.to_csv(index=False)
        st.download_button(
            label="📥 Descargar CSV",
            data=csv_data,
            file_name="resultado.csv",
            mime="text/csv",
            use_container_width=True
        )

# Footer
st.divider()
st.markdown("""
**Procesador Topográfico v3.0** | [GitHub](https://github.com/PardoJean/Coordenadas)

- ✅ OCR automático con PaddleOCR
- ✅ Edición manual de datos
- ✅ Exportación a Excel y CSV
- ✅ Funciona 100% en el navegador
""")
