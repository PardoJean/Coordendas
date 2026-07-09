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
def extraer_ensayo_completo(texto):
    """Extrae tipo y número del ensayo donde dice 'Código'."""
    texto_upper = texto.upper()

    # Buscar donde dice "Código" y captura lo que viene después
    codigo_match = re.search(r'C[ÓO]DIGO\s*[>\:]?\s*([A-Z]+)\s*(\d+)?', texto_upper)
    if codigo_match:
        tipo = codigo_match.group(1).strip()
        numero = codigo_match.group(2) if codigo_match.group(2) else ""

        # Validar que el tipo sea uno de los conocidos
        tipos_validos = ["POZO", "VDC", "DCP", "TIS", "DCA"]
        for tipo_valido in tipos_validos:
            if tipo_valido in tipo:
                if numero:
                    return f"{tipo_valido} {numero}"
                else:
                    return tipo_valido

    # Fallback: buscar tipos en el texto si no encuentra "Código"
    tipos = ["POZO", "VDC", "DCP", "TIS", "DCA"]
    for tipo in tipos:
        if tipo in texto_upper:
            # Buscar número cerca del tipo
            tipo_match = re.search(f'{tipo}\\s*(\\d+)?', texto_upper)
            if tipo_match and tipo_match.group(1):
                return f"{tipo} {tipo_match.group(1)}"
            else:
                return tipo

    return "SIN CLASIFICAR"

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

def procesar_abs(abs_str):
    """Procesa ABS: primer signo + número sin 0 + 2 decimales.
    Ej: -0+218.161 -> -218.16"""
    if not abs_str:
        return ""

    # Extraer primer signo (- o +)
    primer_signo = ""
    if abs_str[0] in ['-', '+']:
        primer_signo = abs_str[0]
        abs_str = abs_str[1:]

    # Buscar el número después del primer 0
    match = re.search(r'0\s*[+-]\s*(\d+[\.,]?\d*)', abs_str)
    if match:
        numero = match.group(1).replace(',', '.')
        # Truncar a 2 decimales
        numero_limpio = truncar_decimales(numero, decimales=2)
        return f"{primer_signo}{numero_limpio}"

    return abs_str

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

    # Buscar ABS (Estación) - Est:K-0+valor o K0+valor (capturar primer signo + valor)
    abs_patterns = [
        r'EST\s*[:\.]?\s*K\s*([-+]?\s*0\s*[+-]\s*\d+[\.,]?\d*)',  # Est:K-0+218.161 captura -0+218.161
        r'K\s*([-+]?\s*0\s*[+-]\s*\d+[\.,]?\d*)',  # K-0+valor captura -0+valor
        r'(?:ABS|STATION|STA)\s*[:\.]?\s*(-?\d+[\.,]?\d*)',
    ]
    for pattern in abs_patterns:
        abs_match = re.search(pattern, texto_upper)
        if abs_match:
            abs_valor = abs_match.group(1)
            # Limpiar espacios pero mantener signos
            abs_valor = re.sub(r'\s+', '', abs_valor)
            resultado["ABS"] = abs_valor
            break

    # Procesar ABS especialmente (primer signo + número sin 0)
    if resultado["ABS"]:
        resultado["ABS"] = procesar_abs(resultado["ABS"])

    # Aplicar truncado a 2 decimales sin redondear (para X, Y, COTA)
    for key in ["X", "Y", "COTA"]:
        if resultado[key]:
            resultado[key] = truncar_decimales(resultado[key], decimales=2)

    return resultado

# Tabs para dos formas de entrada
tab1, tab2 = st.tabs(["📸 Procesar Imágenes", "📋 Pegar Coordenadas"])

# TAB 1: Carga de imágenes
with tab1:
    st.subheader("1️⃣ Cargar o Arrastrar Imágenes")
    st.info("💡 Puedes arrastrar imágenes directamente aquí o seleccionar del explorador")

    imagenes_subidas = st.file_uploader(
        "Selecciona imágenes de topografía",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
        help="Arrastra imágenes aquí o haz clic para seleccionar"
    )

# TAB 2: Pegar coordenadas
with tab2:
    st.subheader("📋 Pegar Coordenadas Directamente")
    st.info("Pega el texto con las coordenadas de la foto (E:, N:, Cota:, Est:, etc.)")

    texto_coordenadas = st.text_area(
        "Pega las coordenadas aquí",
        height=150,
        placeholder="Ejemplo:\nCódigo: VDC 4\nE 780720.633\nN 9603295.217\nElev: 825.387\nEst:K-0+154.895"
    )

    procesar_texto_btn = st.button("✓ Procesar Coordenadas del Texto", type="primary")

    if procesar_texto_btn and texto_coordenadas:
        try:
            ensayo = extraer_ensayo_completo(texto_coordenadas)
            coords = extraer_coordenadas(texto_coordenadas)

            # Mostrar resultado en tabla
            resultado_df = pd.DataFrame([{
                "Ensayo": ensayo,
                "X": coords["X"],
                "Y": coords["Y"],
                "COTA": coords["COTA"],
                "ABS": coords["ABS"]
            }])

            st.success("✅ Coordenadas extraídas:")
            st.dataframe(resultado_df, use_container_width=True)

            # Opción de descargar
            col1, col2 = st.columns(2)
            with col1:
                csv_data = resultado_df.to_csv(index=False)
                st.download_button(
                    "📥 Descargar CSV",
                    csv_data,
                    "coordenadas.csv",
                    "text/csv",
                    use_container_width=True
                )
            with col2:
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    resultado_df.to_excel(writer, sheet_name='Coordenadas', index=False)
                st.download_button(
                    "📥 Descargar Excel",
                    output.getvalue(),
                    "coordenadas.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )

        except Exception as e:
            st.error(f"❌ Error: {str(e)}")

    # Botones dentro del tab1
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
                            ensayo = extraer_ensayo_completo(texto_ocr)
                            coords = extraer_coordenadas(texto_ocr)

                            registro = {
                                "Ensayo": ensayo,
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
