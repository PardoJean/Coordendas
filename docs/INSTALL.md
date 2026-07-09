# GUÍA COMPLETA DE INSTALACIÓN - Procesador Topográfico OCR

## 📦 Requisitos Previos

Antes de comenzar, asegúrate de tener:

1. **Sistema Operativo:** Windows 10 o Windows 11
2. **Conexión a Internet:** Para descargar los instaladores
3. **Espacio en Disco:** Aproximadamente 500 MB libres

---

## 🔹 PASO 1: Instalar Python

1. Ve a [https://www.python.org/downloads](https://www.python.org/downloads)
2. Descarga la versión **Python 3.11** (o superior) para Windows
3. **IMPORTANTE:** Durante la instalación, marca la casilla **"Add Python to PATH"**
4. Completa la instalación

### Verificar instalación:

Abre **CMD** o **PowerShell** y ejecuta:
```bash
python --version
```

Debe mostrar algo similar a: `Python 3.11.x`

---

## 🔹 PASO 2: Instalar Tesseract OCR

Tesseract es el motor de reconocimiento de texto que usa esta aplicación. Es **absolutamente necesario** para que el programa funcione.

1. Ve a: [https://github.com/UB-Mannheim/tesseract/wiki](https://github.com/UB-Mannheim/tesseract/wiki)
2. Descarga el instalador para Windows:
   - Si tienes Windows 64-bit: `tesseract-ocr-w64-setup.exe`
3. Ejecuta el instalador y sigue los pasos por defecto.
   - **Ruta recomendada:** `C:\Program Files\Tesseract-OCR\`
4. Selecciona los **idiomas adicionales**:
   - ✅ Español (spa)
   - ✅ Inglés (eng)
5. Completa la instalación

### Verificar instalación:

Abre un nuevo **CMD** o **PowerShell** y ejecuta:
```bash
tesseract --version
```

Debe mostrar la versión de Tesseract instalada.

---

## 🔹 PASO 3: Copiar los archivos del proyecto

Copia la carpeta completa del proyecto a una ubicación en tu computadora, por ejemplo:
```
C:\Users\TuUsuario\Documentos\ProcesadorTopografico\
```

Verifica que contenga estos archivos principales:
- `config.py`
- `ocr_engine.py`
- `parser_topografia.py`
- `gui.py`
- `main.py`
- `requirements.txt`
- `run.bat`
- `build.bat`

---

## 🔹 PASO 4: Instalar dependencias de Python

Abre **CMD** o **PowerShell** dentro de la carpeta del proyecto y ejecuta:

```bash
pip install -r requirements.txt
```

Este comando instalará automáticamente:
- `opencv-python` — Procesamiento de imágenes
- `pytesseract` — Interfaz para Tesseract OCR
- `customtkinter` — Interfaz gráfica moderna
- `openpyxl` — Manejo de archivos Excel
- `pandas` — Manejo de datos
- `pillow` — Procesamiento de imágenes

---

## 🔹 PASO 5: Ejecutar la aplicación (modo desarrollo)

Para probar que todo funcione correctamente, ejecuta:

```bash
python main.py
```

Si se abre la ventana de la aplicación, ¡la instalación fue exitosa!

---

## 📦 PASO 6: Empaquetar como .exe (Opcional)

Si deseas distribuir la aplicación como un solo archivo ejecutable sin necesidad de Python instalado:

### 6.1 Instalar PyInstaller

```bash
pip install pyinstaller
```

### 6.2 Compilar a .exe

Ejecuta el siguiente comando en la carpeta del proyecto:

```bash
python -m PyInstaller --name "ProcesadorTopografico" --onefile --windowed --clean main.py
```

O simplemente ejecuta el script incluido:

```bash
build.bat
```

### 6.3 Ubicar el ejecutable

El archivo ejecutable se generará en:
```
dist\ProcesadorTopografico.exe
```

Ese archivo puede copiarse a cualquier computadora Windows y ejecutarse directamente.

---

## ⚠️ Solución de Problemas Comunes

### Error: "Tesseract no encontrado"
- Asegúrate de que Tesseract esté instalado en `C:\Program Files\Tesseract-OCR\tesseract.exe`
- Usa el botón "Configurar Tesseract" en la interfaz de la aplicación
- O crea el archivo `tesseract_path.txt` con la ruta completa al ejecutable

### Error: "No se encontraron módulos"
- Revisa que `requirements.txt` y `main.py` estén en la misma carpeta
- Reinicia la terminal(CMD/Powershell) y vuelve a ejecutar `pip install -r requirements.txt`

### Error al compilar con PyInstaller
- Asegúrate de tener suficiente espacio en disco (mínimo 2GB libres)
- Cierra todas las instancias del programa antes de recompilar
- Ejecuta siempre con `--clean` para evitar conflictos con versiones anteriores

---

## 📂 Archivos de Salida Generados

Al guardar resultados, la aplicación crea la carpeta `salida/` con:

- `salida/resultado.xlsx` — Archivo Excel final
- `salida/resultado.csv` — Archivo CSV auxiliar
- `salida/imagenes_ordenadas/` — Imágenes renombradas y ordenadas
- `salida/log_proceso.txt` — Registro del proceso OCR

---

## 📱 Flujo de Trabajo Básico

1. **Seleccionar carpeta de imágenes:** Carga las capturas de pantalla recibidas por WhatsApp
2. **Cargar plantilla Excel:** (Opcional) Carga una plantilla de Excel existente
3. **Procesar:** La app analiza las imágenes y extrae los datos
4. **Editar:** Revisa la tabla y edita celdas haciendo doble clic si es necesario
5. **Guardar:** Exporta el Excel final o todas las salidas a la carpeta `salida/`

---

## 📞 Soporte y Notas

- La aplicación trabaja completamente en local — no requiere conexión a Internet para procesar
- El OCR de screenshots de móvil puede ocasionalmente producir lecturas incorrectas; siempre verifica los datos en la tabla antes de exportar
- La edición manual de la tabla (doble clic en celda) permite corregir cualquier dato con confianza baja
