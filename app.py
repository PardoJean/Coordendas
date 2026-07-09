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

# Cargar OCR
@st.cache_resource
def cargar_paddle_ocr():
    """Carga PaddleOCR de forma segura."""
    try:
        from paddleocr import PaddleOCR
        ocr = PaddleOCR(use_angle_cls=True, lang='es')
        return ocr, True
    except Exception as e:
        st.error(f"❌ Error cargando PaddleOCR: {str(e)}")
        return None, False

ocr, ocr_disponible = cargar_paddle_ocr()

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

def extraer_coordenadas(texto):
    """Extrae X, Y, COTA, ABS del texto OCR."""
    resultado = {"X": "", "Y": "", "COTA": "", "ABS": ""}

    # Buscar X (Este)
    x_match = re.search(r'[EE](?:ste)?\s*[:\.]?\s*([0-9,.\s]+)', texto, re.IGNORECASE)
    if x_match:
        resultado["X"] = x_match.group(1).strip()

    # Buscar Y (Norte)
    y_match = re.search(r'[NN](?:orte)?\s*[:\.]?\s*([0-9,.\s]+)', texto, re.IGNORECASE)
    if y_match:
        resultado["Y"] = y_match.group(1).strip()

    # Buscar COTA
    cota_match = re.search(r'(?:Cota|Elev|Elevación)\s*[:\.]?\s*([0-9,.\s]+)', texto, re.IGNORECASE)
    if cota_match:
        resultado["COTA"] = cota_match.group(1).strip()

    # Buscar ABS
    abs_match = re.search(r'(?:K0\+|ABS|Sta)\s*[:\.]?\s*([0-9,.\s]+)', texto, re.IGNORECASE)
    if abs_match:
        resultado["ABS"] = abs_match.group(1).strip()

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
        st.error("❌ OCR no está disponible. Por favor, intenta más tarde.")
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

                        # Procesar OCR
                        resultado_ocr = ocr.ocr(img_array, cls=True)

                        # Extraer texto
                        if resultado_ocr:
                            texto_ocr = "\n".join([line[0][1] for line in resultado_ocr if line])
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
