"""Procesador Topográfico - Versión Web con Streamlit"""
import streamlit as st
import pandas as pd
import io
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.resolve()))

from src import ocr_engine
from src import parser_topografia
from src import excel_writer
from src import validators
from src import sorter
from src.config import COLUMNAS

# Configurar página
st.set_page_config(
    page_title="Procesador Topográfico",
    page_icon="📍",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📍 Procesador Topográfico OCR")
st.markdown("Extrae datos topográficos de imágenes usando OCR y genera Excel listo para usar.")

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuración")
    st.info("Sube imágenes de topografía (.jpg, .png, .webp) para procesar automáticamente.")

# Inicializar sesión
if "datos_procesados" not in st.session_state:
    st.session_state.datos_procesados = []
if "imagenes_cargadas" not in st.session_state:
    st.session_state.imagenes_cargadas = []

# Carga de imágenes
st.subheader("1️⃣ Cargar Imágenes")
imagenes_subidas = st.file_uploader(
    "Selecciona imágenes de topografía",
    type=["jpg", "jpeg", "png", "webp"],
    accept_multiple_files=True,
    help="Puedes seleccionar varias imágenes a la vez"
)

# Botón para procesar
col1, col2 = st.columns(2)

with col1:
    procesar_btn = st.button("▶ Procesar Imágenes", type="primary", use_container_width=True)

with col2:
    limpiar_btn = st.button("🗑️ Limpiar Todo", use_container_width=True)

if limpiar_btn:
    st.session_state.datos_procesados = []
    st.session_state.imagenes_cargadas = []
    st.rerun()

# Procesar imágenes
if procesar_btn and imagenes_subidas:
    with st.spinner("⏳ Procesando imágenes con OCR..."):
        try:
            # Configurar OCR
            ocr_engine.configurar_tesseract()

            datos_procesados = []
            errores = []

            # Procesar cada imagen
            for idx, imagen_archivo in enumerate(imagenes_subidas, 1):
                try:
                    # Leer imagen
                    from PIL import Image
                    import cv2
                    import numpy as np

                    pil_img = Image.open(imagen_archivo)
                    img_cv = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

                    # Procesar OCR
                    texto_ocr = ocr_engine.extraer_texto_robusto(img_cv)

                    # Parsear datos
                    registro = parser_topografia.parsear_topografia(texto_ocr)

                    # Validar
                    registro = validators.validar_registro(registro)
                    registro["imagen"] = imagen_archivo.name

                    datos_procesados.append(registro)

                except Exception as e:
                    errores.append(f"Error en {imagen_archivo.name}: {str(e)}")

            # Ordenar registros
            if datos_procesados:
                datos_procesados = sorter.ordenar_registros(datos_procesados)
                st.session_state.datos_procesados = datos_procesados

                st.success(f"✅ Se procesaron {len(datos_procesados)} imágenes correctamente")

                if errores:
                    with st.warning(f"⚠️ {len(errores)} error(es) detectado(s)"):
                        for error in errores:
                            st.text(error)
            else:
                st.error("❌ No se pudo procesar ninguna imagen")
                for error in errores:
                    st.error(error)

        except Exception as e:
            st.error(f"❌ Error al configurar OCR: {str(e)}")
            st.info("Asegúrate de que Tesseract OCR esté instalado en tu sistema")

# Mostrar y editar datos
if st.session_state.datos_procesados:
    st.subheader("2️⃣ Vista Previa y Edición")

    # Convertir a DataFrame
    df = pd.DataFrame(st.session_state.datos_procesados)

    # Remover columna "imagen" de la vista editable
    columnas_editar = [col for col in COLUMNAS if col in df.columns]

    # Editor editable
    st.info("💡 Puedes editar cualquier celda directamente en la tabla")

    df_editada = st.data_editor(
        df[columnas_editar],
        use_container_width=True,
        hide_index=False,
        num_rows="dynamic"
    )

    # Actualizar datos procesados
    st.session_state.datos_procesados = df_editada.to_dict('records')

    # Mostrar estadísticas
    st.subheader("📊 Estadísticas")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total de Registros", len(df_editada))
    with col2:
        ensayos = df_editada["Ensayo"].nunique() if "Ensayo" in df_editada.columns else 0
        st.metric("Tipos de Ensayo", ensayos)
    with col3:
        vacios = df_editada.isna().sum().sum()
        st.metric("Campos Vacíos", vacios)
    with col4:
        st.metric("Imágenes Procesadas", len(imagenes_subidas) if imagenes_subidas else 0)

    # Descargar resultados
    st.subheader("3️⃣ Descargar Resultados")

    col1, col2 = st.columns(2)

    with col1:
        # Descargar como Excel
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
        # Descargar como CSV
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
**Procesador Topográfico v3.0** | [GitHub](https://github.com/PardoJean/Coordendas)

Características:
- ✅ OCR automático con Tesseract
- ✅ Parsing inteligente de coordenadas
- ✅ Edición manual de datos
- ✅ Exportación a Excel y CSV
- ✅ Funciona 100% en el navegador
""")
