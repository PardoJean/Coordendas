# Procesador Topográfico - README

Aplicación de escritorio en Python para Windows que procesa screenshots (capturas de pantalla) de topografía enviadas por WhatsApp, extrae automáticamente los datos utilizando OCR y genera un archivo Excel listo para usar.

## Requisitos

- **Python 3.11+**
- **Tesseract OCR** (dependencia externa, ver instalación abajo)

## Estructura del Proyecto

```
Proyecto/
├── config.py                # Configuración centralizada
├── ocr_engine.py            # Motor OCR y preprocesamiento de imagen
├── parser_topografia.py     # Lógica de parsing del texto OCR
├── validators.py            # Validación y normalización de datos
├── sorter.py                # Ordenamiento robusto de registros
├── excel_writer.py          # Escritura de Excel y CSV
├── gui.py                   # Interfaz gráfica con customtkinter/tkinter
├── main.py                  # Punto de entrada de la aplicación
├── requirements.txt         # Dependencias Python
├── run.bat                  # Script para ejecutar localmente
├── build.bat                # Script para compilar a .exe con PyInstaller
└── salida/                  # Carpeta generada con resultados
    ├── resultado.xlsx
    ├── resultado.csv
    ├── imagenes_ordenadas/
    └── log_proceso.txt
```

## Instalación

1. Clona o descarga este repositorio.
2. Instala las dependencias Python:
   ```bash
   pip install -r requirements.txt
   ```
3. **Instala Tesseract OCR para Windows**:
   - Descarga el instalador desde: https://github.com/UB-Mannheim/tesseract/wiki
   - Instálalo en la ruta por defecto: `C:\Program Files\Tesseract-OCR\tesseract.exe`
   - Asegúrate de que esta ruta está en tu variable de entorno `PATH` de Windows.

## Ejecución Local

Para ejecutar el programa desde el código Python, simplemente ejecuta el archivo `run.bat` o abre una terminal Powershell/CMD en la carpeta del proyecto y escribe:

```bash
python main.py
```

## Compilación a .exe

Para empaquetar la aplicación en un único .exe ejecutable, puedes usar el script `build.bat` o ejecutar el siguiente comando directamente desde la terminal en la carpeta del proyecto:

```bash
python -m PyInstaller --name "ProcesadorTopografico" --onefile --windowed main.py
```

 El ejecutable generado estará en la carpeta `dist/ProcesadorTopografico.exe`.

## Flujo de Uso

1. Abre el programa.
2. Haz clic en **"Seleccionar carpeta de imágenes"** y elige la carpeta que contiene las capturas de pantalla (`.jpg`, `.jpeg`, `.png`, `.webp`).
3. Haz clic en **"Cargar plantilla Excel"** y selecciona una plantilla existente (opcional; si no seleccionas, creará una nueva).
4. Haz clic en **"Procesar"**. El motor OCR analizará las imágenes y extraerá: `Ensayo`, `X`, `Y`, `COTA`, `ABS`.
5. Revisa la **tabla de vista previa editable**. Puedes hacer doble clic en una celda para modificarla.
6. Pulsa **"Guardar Excel"**, **"Guardar imágenes"** o **"Exportar todo"** para generar los archivos finales en la carpeta `sal
</parameter>
</invoke>
<parameter name="filePath"><parameter name="content"># Procesador Topográfico - README

Aplicación de escritorio en Python para Windows que procesa screenshots (capturas do pantalla) de topografía enviadas por WhatsApp, extrayendo automáticamente los datos variables con OCR y generando un Excel listo para usar.

## Requisitos Previos

- **Python 3.11 o superior**
- **Tesseract OCR** (ver instrucciones de instalación abajo)
- Dependencias instaladas desde `requirements.txt`

## Estructura del Proyecto

```
coordenadas_app/
│
├── config.py                # Configuración central del sistema
├── ocr_engine.py            # Motor OCR y preprocesamiento de imagen
├── parser_topografia.py     # Lógica de parsing del texto OCR
├── validators.py            # Validación y normalización de datos
├── sorter.py                # Ordenamiento robusto de registros
├── excel_writer.py          # Escritura de Excel y CSV
├── gui.py                   # Interfaz gráfica (customtkinter)
├── main.py                  # Punto de entrada de la aplicación
├── requirements.txt         # Dependencias Python
├── run.bat                  # Script de ejecución local
├── build.bat                # Script de compilación PyInstaller
└── README.md                # Este archivo
```

## Instalación Rápida

1. Abre una terminal o PowerShell en esta carpeta.
2. Instala las dependencias:
   ```bash
   pip install -r requirements.txt
   ```
3. **Instala Tesseract OCR** (dependencia externa obligatoria):
   - Descárgalo desde: https://github.com/UB-Mannheim/tesseract/wiki
   - Instálalo en la ruta por defecto: `C:\Program Files\Tesseract-OCR\tesseract.exe`
   - Asegúrate de que esta ruta esté en la variable `PATH` de tu Windows.

## Ejecución Local

Simplemente ejecuta el script `run.bat` o abre una terminal y ejecuta:

```bash
python main.py
```

## Compilación a .exe con PyInstaller

Para empaquetar la aplicación en un único archivo `.exe`, ejecuta en la terminal desde la carpeta raíz:

```bash
python -m PyInstaller --name "ProcesadorTopografico" --onefile --windowed main.py
```

O usa el script `build.bat` incluido. El ejecutable final se encontrará en `dist\ProcesadorTopografico.exe`.

## Flujo de Uso de la Aplicación

1. Abre `ProcesadorTopografico.exe` (o ejecuta `main.py`).
2. Haz clic en **"Seleccionar carpeta de imágenes"** y selecciona la carpeta con tus screenshots de WhatsApp (`.jpg`, `.png`, `.webp`, etc.).
3. (Opcional) Haz clic en **"Cargar plantilla Excel"** y selecciona una plantilla de salida con los encabezados deseados.
4. Pulsa el botón **"▶ Procesar"**. La barra de progreso mostrará el avance.
5. Revisa la **tabla de vista previa editable**. Si un dato es incorrecto, haz **doble clic en la celda** para editarlo.
6. Pulsa **"💾 Guardar Excel"** o **"📦 Exportar todo"** para generar la salida en la carpeta `salida/`.
7. La carpeta `salida/imagenes_ordenadas/` contendrá las imágenes originales renombradas consecutivamente (ej: `001_POZO_2.jpg`).

## Características Principales

- **OCR Local**: Usa Tesseract con preprocesamiento OpenCV (contraste, nitidez, binarización).
- **Parsing Intelligent**: Detecta automáticamente Ensayo, X, Y, COTA y ABS.
- **Ordenamiento Automático**: POZO > VDC > DCP > TIS > DCA, con orden numérico interno.
- **Validaciones**: Solo números en campos numéricos, prevención de duplicados.
- **Edición Manual**: La tabla de vista previa es completamente editable.
- **Exportación Completa**: Genera Excel (.xlsx), CSV (.csv), imágenes ordenadas y log de proceso.

## Notas Importantes

- **Tesseract OCR es obligatorio** para el funcionamiento del programa. El ejecutable dependerá de que Tesseract esté instalado en la máquina.
- Si las imágenes contienen información que no se detecta bien, utiliza la función de doble clic para editar manualmente antes de exportar.
- Asegúrate de que las imágenes sean relativamente claras y no tengan mucho ruido para obtener mejores resultados de OCR.
- Si `customtkinter` no está disponible, la interfaz recurre automáticamente a `tkinter` estándar.

## Licencia

Proyecto desarrollado bajo solicitud directa. Uso profesional y educativo.
