# BACKUP SESION - Procesador Topografico OCR
## Fecha: 2026-06-29 | Proyecto: Aplicacion desktop Windows para procesar screenshots de topografia

---

## ARCHIVO GENERADOS

### Codigo Fuente (Python)
- config.py - Configuracion central: rutas, orden (POZO>VDC>DCP>TIS>DCA), patrones regex, correcciones OCR
- ocr_engine.py - Motor OCR con Tesseract + OpenCV. Incluye CLAHE, sharpening, recortes (header y tabla), binarizacion, upscaling x6
- parser_topografia.py - Parsing del texto OCR: extrae Ensayo, X, Y, COTA, ABS. Coordenadas UTM sin prefijo N/E
- validators.py - Normalizacion y validacion de datos (decimales, separadores)
- sorter.py - Ordenamiento POZO > VDC > DCP > TIS > DCA, con orden numerico interno
- excel_writer.py - Escritura de Excel (.xlsx) y CSV (.csv) respetando plantillas
- gui.py - Interfaz grafica en customtkinter (fallback a tkinter). Threading seguro via queue.Queue + after()
- main.py - Punto de entrada

### Scripts y Configuracion
- requirements.txt - Dependencias: opencv-python, pytesseract, customtkinter, openpyxl, pandas
- run.bat - Ejecutar localmente (python main.py)
- build.bat - Recompilar con PyInstaller
- README.md - Documentacion completa
- BACKUP_SESION.md - Este archivo (resumen de la sesion)

### Ejecutable
- dist/ProcesadorTopografico.exe - Ejecutable por PyInstaller

---

## TIMELINE DE PROBLEMAS Y SOLUCIONES

1. Tesseract no detectado
   - Solucion: Agregar rutas adicionales en ocr_engine.py (AppData\Local\Programs\Tesseract-OCR)

2. GUI bloqueada al procesar (crash de threading en Tkinter)
   - Solucion: Reescribir gui.py con queue.Queue y poll_queue() via after(100, ...)

3. Error cget(state) en CTkTextbox
   - Solucion: Eliminar logica de state en _log_msg(). CTkTextbox no soporta state como tk.Text

4. Coordenadas X/Y no detectadas
   - Solucion: Simplificar patrones de fallback a d{6} (X) y d{7} (Y), refactorizar extraer_x_y_sin_prefijo()

5. Deteccion de Ensayo (Pozo, VDC) desde screenshots de movil
   - Solucion multipunto:
     a) ocr_engine.py: Crop del header superior (25%), inversion de colores si fondo oscuro, CLAHE agresivo, upscale x6
     b) config.py: Tabla CORRECCIONES_OCR_CODIGO (Fes->POZO, PYRO->VDC, etc.)
     c) parser_topografia.py: Pre-correccion de texto, patrones alternativos (codigo_alt, ensayo_suelto_generico), mapeo de correcciones

---

## ESTADO ACTUAL

- Ejecutable: dist/ProcesadorTopografico.exe (compilado y funcional)
- GUI: Abre sin errores, threading corregido
- OCR: Tesseract detectado automaticamente
- Extraccion: X, Y, COTA, ABS funcionan correctamente
- Ordenamiento: Automatico por prioridad
- Exportacion: Excel y CSV generados en salida/

---

## INSTRUCCIONES

Ejecutar localmente:
  python main.py

Recompilar .exe:
  python -m PyInstaller --name "ProcesadorTopografico" --onefile --windowed --clean main.py

---

## NOTAS PARA MEJORAS FUTURAS

- Deteccion del campo Ensayo puede beneficiarse de modelos OCR mas avanzados (EasyOCR) si las correcciones por diccionario no son suficientes
- Empaquetar Tesseract junto al .exe para eliminar dependencia externa
- Agregar test unitarios con las imagenes de ejemplo
- Implementar multiprocessing para acelerar OCR en lotes
- Empaquetar como installer standalone con Inno Setup
