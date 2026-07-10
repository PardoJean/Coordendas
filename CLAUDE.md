# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Qué es esto

Procesador Topográfico: lee capturas de pantalla de una app de topografía (las que se envían por WhatsApp), extrae con OCR los campos **Ensayo, X, Y, COTA, ABS** y los deja listos para exportar a Excel/CSV o ubicar en un mapa. Existen **tres implementaciones que corren la misma lógica de negocio** en plataformas distintas — ver "Arquitectura" abajo, es la parte no obvia de este repo.

## Comandos

```bash
# Instalar dependencias (Python)
pip install -r requirements.txt

# Correr la app web (Streamlit)
streamlit run streamlit_app.py

# Correr la app de escritorio (Tkinter, offline)
python desktop_app.py

# Tests del parser Python (lógica de negocio + 4 capturas reales de extremo a extremo con Tesseract)
python tests/test_topo_parser.py

# Tests del parser JS (misma batería, para docs/js/parser.js)
node tests/test_parser_js.js

# Fuzzing de robustez (genera mutaciones de ruido de OCR sobre casos dorados)
python tests/fuzz_parser.py --trials 1000 [--seed 42]
node tests/fuzz_parser_js.js 1000 [seed]

# Servir docs/ localmente para probar la versión GitHub Pages
cd docs && python3 -m http.server 8000
```

No hay build/lint configurado (ni linter, ni bundler, ni package.json — el JS de `docs/` es vanilla, cargado directo por `<script>` tags, sin transpilar). Los "tests" son scripts ejecutables directos, no un test runner (pytest/jest).

## Arquitectura

### La misma lógica vive en dos lenguajes, deliberadamente en sincronía

- **`topo_parser.py`** es la implementación de referencia (Python). La usan `streamlit_app.py` (app web en Streamlit Cloud) y `desktop_app.py` (app de escritorio Tkinter, offline).
- **`docs/js/parser.js`** + **`docs/js/geo.js`** son un **puerto manual** de esa misma lógica a JavaScript, para la versión que corre 100% en el navegador (`docs/`, publicada con GitHub Pages, sin backend). No hay generación de código: cualquier cambio a las reglas de negocio en `topo_parser.py` debe replicarse a mano en `parser.js`/`geo.js`, y viceversa.
- Por eso existen **dos suites de test paralelas** con los mismos casos dorados: `tests/test_topo_parser.py` (Python) y `tests/test_parser_js.js` (Node, carga `docs/js/*.js` con `require()` simulando `window` como global). Igual con el fuzzer: `tests/fuzz_parser.py` y `tests/fuzz_parser_js.js`. Al tocar una regla de extracción, corre y actualiza ambos lados.

### Reglas de negocio (en `topo_parser.py` / `parser.js`)

- **Ensayo**: se extrae del campo "Código" de la captura (ej. `DCP 1`, `VDC 4`). Los tipos válidos son `POZO, VDC, DCP, TIS, DCA`, cada uno con un patrón regex tolerante a errores típicos de OCR (`P0Z0`, `POS`, `Voc`, etc. — ver `_PATRONES_TIPO` / `PATRONES_TIPO`). Si no se reconoce ningún tipo, el resultado es el string literal `"SIN CLASIFICAR"`.
- **X / Y**: se buscan las etiquetas "E" (Este) y "N" (Norte) token por token, con una validación de plausibilidad (la parte entera debe tener ≥5 dígitos) antes de aceptar un valor — esto existe específicamente para que una "E"/"N" suelta de ruido de OCR (un ícono mal leído) no robe un valor sin relación. Hay un respaldo por magnitud si no aparecen las etiquetas: Norte = 7 dígitos empezando en "9", Este = 6 dígitos.
- **COTA**: de "Elevación"/"Elev."/"Cota".
- **ABS**: de un patrón tipo `Est:K-0+218.161` → `-218.16` (primer signo + número, se descarta el "0" y el segundo signo).
- **Todos los números se truncan a 2 decimales sin redondear** (`math.trunc`, no `round`).

### Estrategia de OCR (`leer_imagen()` en Python / `ocr.js` en JS)

Correr Tesseract con el modo de segmentación de página (`--psm`) por defecto sobre la captura completa suele fusionar el campo "Código" con íconos vecinos y producir texto irreconocible. La solución:
1. Probar varios `--psm` (6, 4, 3, 11) sobre la imagen completa y quedarse con el resultado más completo (más campos no vacíos + Ensayo clasificado).
2. Si el Ensayo sigue sin clasificar, una segunda pasada: localizar la posición de la palabra "Código" (vía `image_to_data` en Python / los `words` con `bbox` de Tesseract.js), recortar solo la zona a su derecha (excluyendo la etiqueta y su fondo, que es justo lo que confunde a Tesseract) y releerla aislada.

### Invariante de seguridad del fuzzer

`tests/fuzz_parser.py` / `fuzz_parser_js.js` generan cientos de mutaciones de ruido de OCR (letras sueltas tipo etiqueta, caracteres espurios entre el tipo de ensayo y su número, tokens basura de íconos) sobre capturas doradas con resultado conocido. El criterio de éxito **no exige cero fallas**: con ruido suficientemente denso, a veces no hay forma de saber con certeza a qué campo pertenece un número, y ahí es preferible dejar el campo **vacío** (se nota en la métrica "Campos vacíos" de la UI y se corrige a mano) que insertar un valor **incorrecto sin avisar**. El fuzzer solo falla si encuentra una mutación que produce un valor incorrecto no vacío. Al tocar la lógica de extracción de X/Y, correr el fuzzer con varios miles de trials para confirmar que esa invariante se mantiene.

### Conversión de coordenadas (mapa)

Las capturas vienen en **PSAD56** (datum sudamericano provisional 1956, no WGS84) — ignorar el datum desplaza los puntos varios cientos de metros en el mapa. `utm_a_latlon()` (Python, usa `pyproj`) y `utmALatLon()` (JS, implementación propia de Transversa de Mercator inversa + traslación geocéntrica de 3 parámetros, sin dependencias) convierten UTM/PSAD56 → lat/lon WGS84. Ambas implementaciones usan los mismos parámetros de traslación (dX=-288, dY=175, dZ=-376, zona 17 Sur por defecto — proyecto en Ecuador) pero **no dan resultados idénticos bit a bit** entre sí (difieren ~5-10 m, dentro de la precisión propia de esta transformación) porque `pyproj` resuelve internamente con un método distinto al cálculo manual en JS; esto es aceptable para visualización en mapa, no para geodesia de precisión.

### Tres formas de desplegar, un solo código fuente de la lógica

| Superficie | Entry point | Requiere internet | Cómo se despliega |
|---|---|---|---|
| Web (Streamlit Cloud) | `streamlit_app.py` | Sí, siempre | Push a `main`, Streamlit Cloud auto-despliega. Tesseract vía `packages.txt` (apt). |
| Navegador (GitHub Pages, PWA) | `docs/index.html` | Solo la primera vez (luego offline vía Service Worker `docs/sw.js`) | Push a `main`; Pages sirve `docs/` (Settings → Pages → Branch `main` / carpeta `docs`). OCR con Tesseract.js + WebAssembly, vendorizado en `docs/vendor/` y `docs/tessdata/` (sin CDN, para que el Service Worker pueda cachearlo todo). |
| Escritorio Windows (offline) | `desktop_app.py` | No | `.github/workflows/build-windows.yml` compila un `.exe` con PyInstaller (Tesseract + `spa`/`eng` incluidos) y lo publica en Releases. Se dispara manual (`workflow_dispatch`) o con tag `vX.Y.Z`. |

`src/` es la versión de escritorio **original** (previa a `desktop_app.py`/`topo_parser.py`), con su propia lógica de parsing (`src/parser_topografia.py`) independiente — no confundir con el `topo_parser.py` actual ni asumir que comparten reglas.

### CI

`.github/workflows/tests.yml` corre en cada push/PR a `main`: `test_topo_parser.py`, `test_parser_js.js`, y ambos fuzzers (1000 trials). Instala Tesseract vía apt para poder correr el test de extremo a extremo con las capturas reales en `assets/`.

## Datos de prueba

`assets/*.jpg|png` son capturas reales (no sensibles) usadas por el test de extremo a extremo en `test_topo_parser.py` — cargarlas y confirmar el Ensayo/X/Y/COTA/ABS esperado es la forma más directa de detectar una regresión en el pipeline de OCR completo. **No subir capturas privadas de clientes/empresas al repo** — si hace falta depurar con una, trabajar solo con archivos temporales fuera del árbol del proyecto y, si aplica, añadir el caso como test sintético (coordenadas inventadas) en vez de con los datos reales.
