"""
Procesador Topográfico - App web (Streamlit).
Copia una captura de topografía en WhatsApp, pégala y obtén X, Y, COTA y ABS.
"""
import io
import shutil

import pandas as pd
import streamlit as st
from PIL import Image

from topo_parser import parsear

# ────────────────────────────────────────────────────────────────────────────
# Configuración
# ────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Procesador Topográfico",
    page_icon="📍",
    layout="centered",
    initial_sidebar_state="collapsed",
)

COLUMNAS = ["Ensayo", "X", "Y", "COTA", "ABS"]

st.markdown(
    """
    <style>
      .block-container { padding-top: 2.5rem; max-width: 820px; }
      div[data-testid="stDataFrame"] { border-radius: 10px; }
      .stButton>button, .stDownloadButton>button { border-radius: 8px; font-weight: 600; }
      footer { visibility: hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("📍 Procesador Topográfico")
st.caption("Copia la captura en WhatsApp → pégala aquí → obtén las coordenadas al instante.")


# ────────────────────────────────────────────────────────────────────────────
# OCR (Tesseract vía pytesseract — ligero, sin PyTorch)
# ────────────────────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def verificar_tesseract():
    import pytesseract

    ruta = shutil.which("tesseract")
    if ruta:
        pytesseract.pytesseract.tesseract_cmd = ruta
    try:
        pytesseract.get_tesseract_version()
        return True, None
    except Exception as e:  # noqa: BLE001
        return False, str(e)


ocr_disponible, ocr_error = verificar_tesseract()

if not ocr_disponible:
    st.error(f"No se pudo iniciar Tesseract OCR: {ocr_error}")
    st.info("Recarga la página en 1–2 minutos mientras Streamlit Cloud instala Tesseract.")
    st.stop()


def leer_imagen(img_pil: Image.Image) -> tuple[dict, str]:
    """Corre OCR sobre una imagen PIL. Devuelve (registro, texto_ocr_crudo)."""
    import pytesseract

    texto = pytesseract.image_to_string(img_pil.convert("RGB"), lang="spa+eng")
    return parsear(texto), texto


# ────────────────────────────────────────────────────────────────────────────
# Estado
# ────────────────────────────────────────────────────────────────────────────
if "registros" not in st.session_state:
    st.session_state.registros = []
if "ultimo_ocr_crudo" not in st.session_state:
    st.session_state.ultimo_ocr_crudo = ""


def agregar_registro(reg: dict):
    st.session_state.registros.append({c: reg.get(c, "") for c in COLUMNAS})


# ────────────────────────────────────────────────────────────────────────────
# Entrada: pegar imagen  +  subir archivo
# ────────────────────────────────────────────────────────────────────────────
col_pegar, col_subir = st.columns(2, gap="large")

with col_pegar:
    st.subheader("Pegar imagen")
    pegado = None
    try:
        from streamlit_paste_button import paste_image_button

        resultado = paste_image_button(
            label="📋 Pegar (Ctrl+V)",
            text_color="#ffffff",
            background_color="#2563eb",
            hover_background_color="#1d4ed8",
            errors="ignore",
        )
        pegado = getattr(resultado, "image_data", None)
    except Exception:  # noqa: BLE001
        st.info("Usa el botón de subir imagen de la derecha.")

    if pegado is not None:
        with st.spinner("Leyendo imagen…"):
            reg, texto_crudo = leer_imagen(pegado)
            agregar_registro(reg)
            st.session_state.ultimo_ocr_crudo = texto_crudo
        st.success(f"Añadido: {reg.get('Ensayo', '—')}")

with col_subir:
    st.subheader("Subir imagen")
    archivos = st.file_uploader(
        "Selecciona o arrastra imágenes",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )
    if archivos and st.button("Procesar imágenes subidas", use_container_width=True):
        with st.spinner("Leyendo imágenes…"):
            for archivo in archivos:
                reg, texto_crudo = leer_imagen(Image.open(archivo))
                agregar_registro(reg)
                st.session_state.ultimo_ocr_crudo = texto_crudo
        st.success(f"Procesadas {len(archivos)} imagen(es).")

if st.session_state.ultimo_ocr_crudo:
    with st.expander("🔍 Ver texto crudo del último OCR (para depurar un dato mal leído)"):
        st.text(st.session_state.ultimo_ocr_crudo)


# ────────────────────────────────────────────────────────────────────────────
# Resultados
# ────────────────────────────────────────────────────────────────────────────
st.divider()

if not st.session_state.registros:
    st.info("Aún no hay datos. Pega o sube una captura para empezar.")
    st.stop()

st.subheader("Resultados")
st.caption("Doble clic en una celda para corregir. Usa la última fila vacía para añadir manualmente.")

df = pd.DataFrame(st.session_state.registros, columns=COLUMNAS)
df_editado = st.data_editor(
    df,
    use_container_width=True,
    hide_index=False,
    num_rows="dynamic",
    key="editor",
)
st.session_state.registros = df_editado.to_dict("records")

# Métricas
m1, m2 = st.columns(2)
m1.metric("Registros", len(df_editado))
vacios = int((df_editado == "").sum().sum())
m2.metric("Campos vacíos", vacios)

# Descargas
st.write("")
d1, d2, d3 = st.columns(3)

with d1:
    st.download_button(
        "⬇️ CSV",
        df_editado.to_csv(index=False).encode("utf-8"),
        "coordenadas.csv",
        "text/csv",
        use_container_width=True,
    )

with d2:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df_editado.to_excel(writer, sheet_name="Coordenadas", index=False)
    st.download_button(
        "⬇️ Excel",
        buffer.getvalue(),
        "coordenadas.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

with d3:
    if st.button("🗑️ Limpiar todo", use_container_width=True):
        st.session_state.registros = []
        st.rerun()

st.divider()
st.caption("Procesador Topográfico · [GitHub](https://github.com/PardoJean/Coordenadas)")
