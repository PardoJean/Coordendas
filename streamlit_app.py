"""
Procesador Topográfico - App web (Streamlit).
Copia una captura de topografía en WhatsApp, pégala y obtén X, Y, COTA y ABS,
con visualización de los puntos sobre un mapa.
"""
import io
import shutil

import pandas as pd
import streamlit as st
from PIL import Image

from topo_parser import (
    DATUM_DEFECTO,
    DATUMS,
    ZONA_UTM_DEFECTO,
    TIPOS,
    SIMBOLOGIA,
    _SIMBOLOGIA_SIN,
    leer_imagen,
    ordenar_registros,
    extraer_tipo_numero,
    utm_a_latlon,
)

# ────────────────────────────────────────────────────────────────────────────
# Configuración
# ────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Procesador Topográfico",
    page_icon="📍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

COLUMNAS = ["Ensayo", "X", "Y", "COTA", "ABS"]

st.markdown(
    """
    <style>
      .block-container { padding-top: 2rem; max-width: 1200px; }

      /* Encabezado con degradado */
      .block-container { padding-top: 2rem; max-width: 1200px; }
      .cabecera {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 18px;
        padding: 1.6rem 1.9rem;
        color: #fff;
        box-shadow: 0 10px 30px rgba(0, 0, 0, .2);
        margin-bottom: 1.6rem;
      }
      .cabecera h1 { margin: 0; font-size: 1.9rem; font-weight: 700; letter-spacing: -.5px; text-shadow: 2px 2px 4px rgba(0,0,0,0.3); }
      .cabecera p  { margin: .35rem 0 0; opacity: .92; font-size: 1rem; }

      .tarjeta {
        background: #fff;
        border: 1px solid rgba(2, 6, 23, .08);
        border-radius: 18px;
        padding: 1.1rem 1.2rem 1.2rem;
        height: 100%;
        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
      }
      .tarjeta h3 { margin: 0 0 .6rem; font-size: 1.05rem; font-weight: 700; color: #1a1a2e; }

      div[data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; }
      .stButton>button, .stDownloadButton>button {
        border-radius: 9px; font-weight: 600;
      }
      div[data-testid="stMetric"] {
        background: var(--secondary-background-color, #f8fafc);
        border: 1px solid rgba(2, 6, 23, .06);
        border-radius: 12px; padding: .6rem .9rem;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="cabecera">
      <h1>📍 Procesador Topográfico</h1>
      <p>Copia la captura en WhatsApp → pégala aquí → obtén las coordenadas y ubícalas en el mapa.</p>
    </div>
    """,
    unsafe_allow_html=True,
)


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
    st.markdown('<div class="tarjeta"><h3>📋 Pegar imagen</h3>', unsafe_allow_html=True)
    pegado = None
    try:
        from streamlit_paste_button import paste_image_button

        resultado = paste_image_button(
            label="Pegar (Ctrl+V)",
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
            try:
                reg, texto_crudo = leer_imagen(pegado)
            except Exception as e:  # noqa: BLE001
                st.error(f"No se pudo leer la imagen pegada: {e}")
            else:
                agregar_registro(reg)
                st.session_state.ultimo_ocr_crudo = texto_crudo
                st.success(f"Añadido: {reg.get('Ensayo', '—')}")
    st.markdown("</div>", unsafe_allow_html=True)

with col_subir:
    st.markdown('<div class="tarjeta"><h3>⬆️ Subir imagen</h3>', unsafe_allow_html=True)
    archivos = st.file_uploader(
        "Selecciona o arrastra imágenes",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )
    if archivos and st.button("Procesar imágenes subidas", use_container_width=True):
        errores = []
        with st.spinner("Leyendo imágenes…"):
            for archivo in archivos:
                try:
                    reg, texto_crudo = leer_imagen(Image.open(archivo))
                except Exception as e:  # noqa: BLE001
                    errores.append(f"{archivo.name}: {e}")
                    continue
                agregar_registro(reg)
                st.session_state.ultimo_ocr_crudo = texto_crudo
        procesadas = len(archivos) - len(errores)
        if procesadas:
            st.success(f"Procesadas {procesadas} imagen(es).")
        for err in errores:
            st.error(f"No se pudo leer {err}")
    st.markdown("</div>", unsafe_allow_html=True)

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

df = pd.DataFrame(ordenar_registros(st.session_state.registros), columns=COLUMNAS)
df_editado = st.data_editor(
    df,
    use_container_width=True,
    hide_index=False,
    num_rows="dynamic",
    key="editor",
)
st.session_state.registros = df_editado.to_dict("records")

# Métricas
m1, m2, m3 = st.columns(3)
m1.metric("Registros", len(df_editado))
vacios = int((df_editado == "").sum().sum())
m2.metric("Campos vacíos", vacios)


# ────────────────────────────────────────────────────────────────────────────
# Mapa de ubicación (UTM -> lat/lon)
# ────────────────────────────────────────────────────────────────────────────
def construir_puntos(df_datos: pd.DataFrame, zona: int, datum: str) -> pd.DataFrame:
    """Convierte X (Este) / Y (Norte) a lat/lon y devuelve solo los válidos."""
    filas = []
    for _, fila in df_datos.iterrows():
        lat, lon = utm_a_latlon(
            fila.get("X", ""), fila.get("Y", ""), zona=zona, datum=datum
        )
        if lat is None or lon is None:
            continue
        filas.append({
            "Ensayo": fila.get("Ensayo", "") or "—",
            "X": fila.get("X", ""),
            "Y": fila.get("Y", ""),
            "COTA": fila.get("COTA", ""),
            "lat": float(lat),
            "lon": float(lon),
        })
    return pd.DataFrame(filas)


st.markdown("### 🗺️ Mapa de ubicación")
cfg1, cfg2, cfg3 = st.columns(3)
datum = cfg1.selectbox(
    "Datum de las coordenadas",
    options=list(DATUMS),
    index=list(DATUMS).index(DATUM_DEFECTO),
    help="Las capturas de topografía en Ecuador suelen estar en PSAD56. Se "
         "transforma a WGS84 para ubicarlas correctamente sobre el mapa.",
)
zona = cfg2.number_input(
    "Zona UTM (Ecuacorriente / Mirador = 17 Sur)",
    min_value=1, max_value=60, value=ZONA_UTM_DEFECTO, step=1,
    help="Todos los puntos se convierten de UTM (hemisferio Sur) a latitud/longitud usando esta zona.",
)
capas_visibles = cfg3.multiselect(
    "Capas visibles",
    options=TIPOS + ["SIN CLASIFICAR"],
    default=TIPOS + ["SIN CLASIFICAR"],
    help="Selecciona qué tipos de ensayo mostrar en el mapa.",
)

df_mapa = construir_puntos(df_editado, int(zona), datum)
m3.metric("Puntos en el mapa", len(df_mapa))

if df_mapa.empty:
    st.info("Aún no hay coordenadas X/Y válidas para ubicar en el mapa.")
else:
    import pydeck as pdk

    df_mapa["_tipo"], _ = zip(*df_mapa["Ensayo"].apply(extraer_tipo_numero))
    df_filtrado = df_mapa[df_mapa["_tipo"].isin(capas_visibles)]

    capas = []
    for tipo in TIPOS + ["SIN CLASIFICAR"]:
        s = df_filtrado[df_filtrado["_tipo"] == tipo]
        if s.empty:
            continue
        simb = SIMBOLOGIA.get(tipo) or _SIMBOLOGIA_SIN
        r, g, b = simb["color"]
        capas.append(pdk.Layer(
            "ScatterplotLayer",
            data=s,
            get_position=["lon", "lat"],
            get_fill_color=[r, g, b, 220],
            get_radius=simb["radio"],
            radius_min_pixels=5,
            radius_max_pixels=18,
            stroked=True,
            get_line_color=[255, 255, 255],
            line_width_min_pixels=2,
            pickable=True,
        ))

    if not df_filtrado.empty:
        vista = pdk.ViewState(
            latitude=float(df_filtrado["lat"].mean()),
            longitude=float(df_filtrado["lon"].mean()),
            zoom=15,
            pitch=0,
        )
    else:
        vista = pdk.ViewState(latitude=0, longitude=0, zoom=2)

    st.pydeck_chart(
        pdk.Deck(
            layers=capas,
            initial_view_state=vista,
            map_style="road",
            tooltip={"text": "{Ensayo}\nX: {X}\nY: {Y}\nCOTA: {COTA}"},
        ),
        use_container_width=True,
    )

    simb = SIMBOLOGIA
    items = ""
    for t in TIPOS + ["SIN CLASIFICAR"]:
        c = simb.get(t) or _SIMBOLOGIA_SIN
        r, g, b = c["color"]
        items += f'<span class="item"><span class="color" style="background:rgb({r},{g},{b})"></span>{t}</span>'
    st.markdown(f'<div class="leyenda-mapa">{items}</div>', unsafe_allow_html=True)


# ────────────────────────────────────────────────────────────────────────────
# Descargas
# ────────────────────────────────────────────────────────────────────────────
st.divider()
d1, d2 = st.columns(2)

with d1:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df_editado.to_excel(writer, sheet_name="Coordenadas", index=False)
    st.download_button(
        "⬇️ Descargar Excel",
        buffer.getvalue(),
        "coordenadas.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

with d2:
    if st.button("🗑️ Limpiar todo", use_container_width=True):
        st.session_state.registros = []
        st.rerun()

st.divider()
st.caption("Versión 1.0 · © 2026 · Todos los derechos reservados · [GitHub](https://github.com/PardoJean/Coordenadas)")
