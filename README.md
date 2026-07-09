# 📍 Procesador Topográfico

Aplicación web que lee capturas de topografía (las que se envían por WhatsApp),
extrae automáticamente con OCR los datos y genera una tabla lista para exportar a Excel/CSV.

**App en línea:** copia la captura en WhatsApp, pégala en la página y obtén al instante:

| Campo | De dónde sale |
|-------|---------------|
| **Ensayo** | El campo **Código** (ej. `DCP 1`, `VDC 4`) |
| **X** | La fila que dice **E** (Este) |
| **Y** | La fila que dice **N** (Norte) |
| **COTA** | **Elevación / Elev. / Cota** |
| **ABS** | **Est:K-0+218.161** → `-218.16` |

Todos los números se truncan a **2 decimales sin redondear**.

## Uso rápido (en línea)

1. Abre el enlace de la app.
2. En WhatsApp, **copia** la captura (o guárdala).
3. En la página, pulsa **📋 Pegar (Ctrl+V)** — o sube el archivo.
4. Revisa/corrige la tabla y descarga **Excel** o **CSV**.

## Ejecutar localmente

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Estructura

```
streamlit_app.py     # Interfaz web (Streamlit)
topo_parser.py       # Lógica de extracción (X, Y, COTA, ABS, Ensayo)
tests/               # Pruebas del parser con capturas reales
requirements.txt     # Dependencias de la app web
packages.txt         # Librerías de sistema para Streamlit Cloud
src/                  # Versión de escritorio original (Tkinter + Tesseract)
```

## Pruebas

```bash
python tests/test_topo_parser.py
```

Verifica la extracción contra capturas reales y las reglas de negocio
(truncado a 2 decimales, formato de ABS, etc.).
