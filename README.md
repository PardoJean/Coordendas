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

## Versión web instantánea (online y offline, sin instalar nada)

Además de la app en Streamlit, hay una versión que corre **directamente en el
navegador** (sin servidor, sin Python) publicada con **GitHub Pages**:

**Link:** https://pardojean.github.io/Coordenadas/

- Ábrelo desde cualquier celular o computador, sin instalar nada.
- La primera vez que lo abres necesita internet (para cargar la página).
  Después de esa primera vez, **funciona sin internet** automáticamente: el
  propio navegador guarda todo en caché (es una PWA).
- El reconocimiento de texto (OCR) corre 100% dentro del navegador
  (Tesseract.js + WebAssembly) — tus imágenes nunca salen de tu dispositivo.
- El mapa de calles necesita internet; sin conexión se muestra una vista
  Este/Norte de los puntos que siempre funciona.
- Exporta a **CSV** (Excel lo abre directamente).

Para habilitarlo por primera vez en el repositorio: **Settings → Pages →
Source: "Deploy from a branch" → Branch: `main` / `docs`**. El código está en
la carpeta [`docs/`](docs/).

## Versión offline (Windows, sin internet)

Además de la web, hay una **app de escritorio** que funciona **sin conexión**:
el OCR en español va incluido, no hay que instalar nada.

- **Descarga:** ve a la pestaña [**Releases**](https://github.com/PardoJean/Coordenadas/releases),
  baja **`ProcesadorTopografico.exe`** y ábrelo con doble clic.
- Abre tus capturas, revisa/corrige la tabla, exporta a **Excel/CSV** y mira
  los puntos en un gráfico **Este/Norte** — todo sin internet.

El ejecutable lo genera automáticamente GitHub Actions
(`.github/workflows/build-windows.yml`) en un equipo Windows y lo publica en
Releases. Para generar una versión nueva: pestaña **Actions → "Compilar app
offline (Windows)" → Run workflow**, o haz push de una etiqueta `vX.Y.Z`.

## Ejecutar localmente

Requiere el binario de **Tesseract OCR** instalado en el sistema
(en Streamlit Cloud se instala solo, vía `packages.txt`).

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py     # versión web
python desktop_app.py              # versión de escritorio
```

## Estructura

```
streamlit_app.py     # Interfaz web (Streamlit)
desktop_app.py       # Interfaz de escritorio (Tkinter, offline)
topo_parser.py       # Lógica de extracción (X, Y, COTA, ABS, Ensayo) + UTM→lat/lon
docs/                # App 100% navegador (GitHub Pages, PWA online+offline)
tests/               # Pruebas del parser con capturas reales
requirements.txt     # Dependencias de la app web
packages.txt         # Librerías de sistema para Streamlit Cloud
.github/workflows/   # Compilación automática del .exe offline
src/                 # Versión de escritorio original (Tkinter + Tesseract)
```

## Pruebas

```bash
python tests/test_topo_parser.py
```

Verifica la extracción contra capturas reales y las reglas de negocio
(truncado a 2 decimales, formato de ABS, etc.).
