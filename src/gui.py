"""gui.py - Interfaz grafica del Procesador Topografico v3.0 (Portapapeles + Drag&Drop)"""
import os
import sys
import tempfile
import shutil
import threading
import queue
import tkinter as tk
from tkinter import messagebox
from pathlib import Path

# Drag & Drop support
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DRAG_DROP_AVAILABLE = True
except ImportError:
    DRAG_DROP_AVAILABLE = False

# CustomTkinter para look moderno
try:
    import customtkinter as ctk
    USAR_CTK = True
except ImportError:
    USAR_CTK = False

# Modulos del proyecto
from src import ocr_engine
from src import parser_topografia
from src import excel_writer
from src import validators
from src import sorter

# ================================================================
# Utilidades para extraer imagenes del portapapeles (Windows)
# ================================================================
import ctypes
from ctypes import wintypes

def get_clipboard_images():
    """Extrae imagenes del portapapeles de Windows y retorna lista de arrays OpenCV (BGR)."""
    import cv2
    import numpy as np
    from PIL import Image, ImageGrab

    imagenes = []
    # Intentar obtener imagen del clipboard con PIL
    try:
        img = ImageGrab.grabclipboard()
        if img is None:
            return imagenes
        # Si es una lista de rutas (archivos)
        if isinstance(img, list):
            for path in img:
                if isinstance(path, str) and os.path.isfile(path):
                    im = cv2.imread(path)
                    if im is not None:
                        imagenes.append(im)
            return imagenes
        # Si es una imagen PIL directa
        if isinstance(img, Image.Image):
            # Convertir PIL (RGB) a OpenCV (BGR)
            img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            imagenes.append(img_cv)
            return imagenes
    except Exception:
        pass
    return imagenes


# ================================================================
# Configuracion de colores
# ================================================================
if USAR_CTK:
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")


# ================================================================
# Worker de procesamiento
# ================================================================
class WorkerProceso(threading.Thread):
    """Hilo de trabajo para procesar imagenes en memoria sin bloquear la GUI."""
    def __init__(self, app, imagenes_list):
        super().__init__(daemon=True)
        self.app = app
        self.imagenes = imagenes_list  # Lista de tuplas: (nombre, array_bgr)
        self.resultados = []
        self.cancelado = False
        self.temp_dir = None

    def run(self):
        try:
            ocr_engine.configurar_tesseract()
        except Exception as e:
            self.app.queue.put(("error", f"Error configurando OCR: {e}"))
            return

        total = len(self.imagenes)
        if total == 0:
            self.app.queue.put(("info", "No se encontraron imagenes para procesar."))
            self.app.queue.put(("done", None))
            return

        self.app.queue.put(("estado", f"Procesando 0/{total}..."))
        self.app.queue.put(("progreso", 0))

        # Crear carpeta temporal para guardar imagenes si es necesario (algunas librerias lo requieren)
        self.temp_dir = tempfile.mkdtemp(prefix="topo_")

        for i, (nombre, img_array) in enumerate(self.imagenes):
            if self.cancelado:
                break
            try:
                self.app.queue.put(("estado", f"Imagen {i+1}/{total}: {nombre}"))
                if img_array is None:
                    continue

                # Guardar temporalmente si OCR requiere archivo (buffer interno, se borra al final)
                temp_path = os.path.join(self.temp_dir, f"temp_{i}.png")
                import cv2
                cv2.imwrite(temp_path, img_array)

                texto, confianza = ocr_engine.ejecutar_ocr(img_array)
                registro = parser_topografia.parsear_texto(texto, archivo=nombre)
                registro["__nombre__"] = nombre
                registro["__confianza__"] = confianza
                registro["__id__"] = i

                warnings = validators.validar_numericos(registro)
                for w in warnings:
                    self.app.queue.put(("log", f"[ADVERTENCIA] {nombre}: {w}"))

                self.resultados.append(registro)
                self.app.queue.put(("fila", registro))
                self.app.queue.put(("log", f"[OK] {nombre} (conf: {confianza:.1f}%)"))
            except Exception as e:
                self.app.queue.put(("log", f"[ERROR] {nombre}: {e}"))
            finally:
                progreso = int(((i + 1) / total) * 100)
                self.app.queue.put(("progreso", progreso))

        self.app.queue.put(("done", self.resultados))

    def cancelar(self):
        self.cancelado = True
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
            except Exception:
                pass


# ================================================================
# Clase principal de la GUI
# ================================================================
class App(ctk.CTk if USAR_CTK else tk.Tk):
    def __init__(self):
        if USAR_CTK:
            super().__init__()
            self.configure(fg_color="#111827")
        else:
            super().__init__()
            self.configure(bg="#1F2937")
            self.columnconfigure(0, weight=1)
            self.rowconfigure(0, weight=1)

        self.title("Procesador Topografico - v3.0")
        self.geometry("1200x700")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.imagenes_pendientes = []  # Lista de (nombre, array_bgr)
        self.resultados = []
        self.worker = None
        self.queue = queue.Queue()
        self.ultima_ruta_excel = None
        self._sort_col = None
        self._sort_reverse = False

        self._crear_interfaz()
        self._checks_iniciales()
        self.after(100, self._poll_queue)

    def _crear_interfaz(self):
        # --- Panel izquierdo: Controles ---
        self._crear_panel_izquierdo()
        # --- Panel derecho: Tabla y Logs ---
        self._crear_panel_derecho()
        # --- Barra de estado inferior ---
        self._crear_barra_estado()

        # Bind global para Ctrl+V (pegar)
        self.bind("<Control-v>", lambda e: self._pegar_imagenes())
        self.bind("<Control-V>", lambda e: self._pegar_imagenes())

    def _crear_panel_izquierdo(self):
        if USAR_CTK:
            panel = ctk.CTkFrame(self, fg_color="#1F2937", corner_radius=10)
        else:
            panel = tk.Frame(self, bg="#1F2937")
        panel.grid(row=0, column=0, padx=10, pady=10, sticky="nsw")
        panel.grid_propagate(False)
        panel.configure(width=320)

        # Header
        titulo = ctk.CTkLabel(panel, text="Procesador Topografico", font=("Arial", 18, "bold"), text_color="#F9FAFB")
        titulo.pack(pady=(15,5), padx=20, anchor="w")
        subtitulo = ctk.CTkLabel(panel, text="v3.0 - Pegar o Arrastrar imagenes", font=("Arial", 11), text_color="#9CA3AF")
        subtitulo.pack(padx=20, anchor="w")

        # --- Seccion: Pegar / Arrastrar ---
        sec_sep = ctk.CTkLabel(panel, text="1. CARGAR IMAGENES", font=("Arial", 10, "bold"), text_color="#6B7280")
        sec_sep.pack(pady=(20,0), padx=20, anchor="w")

        # Area de drop (frame visual)
        self.drop_frame = ctk.CTkFrame(panel, fg_color="#374151", corner_radius=8, border_width=2, border_color="#4B5563")
        self.drop_frame.pack(pady=(10,5), padx=20, fill="x")
        self.drop_frame.bind("<Button-1>", lambda e: self._pegar_imagenes())
        
        self.lbl_drop = ctk.CTkLabel(self.drop_frame, 
                                     text="Click aqui o presiona Ctrl+V\npara pegar imagenes del portapapeles", 
                                     font=("Arial", 11), 
                                     text_color="#9CA3AF")
        self.lbl_drop.pack(pady=20, padx=10)

        # Drag & Drop setup
        if DRAG_DROP_AVAILABLE:
            try:
                self.drop_frame.register_drop_target("*")
                self.drop_frame.dnd_bind("<<Drop>>", self._on_drop)
                self.lbl_drop.configure(text="Arrastra imagenes aqui\no presiona Ctrl+V para pegar")
            except Exception:
                pass

        # Boton alternativo para pegar
        btn_pegar = ctk.CTkButton(panel, text="Paste from Clipboard", command=self._pegar_imagenes,
                                  fg_color="#2563EB", hover_color="#1D4ED8", font=("Arial", 12, "bold"), height=35)
        btn_pegar.pack(pady=(5,0), padx=20, fill="x")

        # Label de estado
        self.lbl_imagenes = ctk.CTkLabel(panel, text="0 imagenes cargadas", font=("Arial", 10), text_color="#9CA3AF")
        self.lbl_imagenes.pack(padx=20, anchor="w")

        # --- Progreso ---
        self.progreso = ctk.CTkProgressBar(panel, mode='determinate', fg_color="#374151", progress_color="#2563EB")
        self.progreso.pack(pady=15, padx=20, fill="x")
        self.progreso.set(0)

        # --- Boton Procesar ---
        btn_procesar = ctk.CTkButton(panel, text="Start Processing", command=self._iniciar_proceso,
                                     fg_color="#059669", hover_color="#047857", font=("Arial", 13, "bold"), height=40)
        btn_procesar.pack(pady=(5, 10), padx=20, fill="x")

        # --- Boton Limpiar ---
        btn_limpiar = ctk.CTkButton(panel, text="Limpiar Todo", command=self._limpiar_todo,
                                    fg_color="#DC2626", hover_color="#B91C1C", font=("Arial", 12, "bold"), height=35)
        btn_limpiar.pack(pady=(5, 10), padx=20, fill="x")

        # --- Botones de Accion ---
        sec_sep4 = ctk.CTkLabel(panel, text="2. EXPORTAR", font=("Arial", 10, "bold"), text_color="#6B7280")
        sec_sep4.pack(pady=(10,0), padx=20, anchor="w")

        btn_guardar = ctk.CTkButton(panel, text="Guardar Excel", command=self._guardar_excel,
                                    fg_color="#4B5563", hover_color="#6B7280", font=("Arial", 11))
        btn_guardar.pack(pady=5, padx=20, fill="x")

        btn_temporal = ctk.CTkButton(panel, text="Exportar Temporal", command=self._exportar_temporal,
                                     fg_color="#2563EB", hover_color="#1D4ED8", font=("Arial", 11))
        btn_temporal.pack(pady=5, padx=20, fill="x")

        btn_abrir = ctk.CTkButton(panel, text="Abrir Excel", command=self._abrir_ultimo_excel,
                                  fg_color="#059669", hover_color="#047857", font=("Arial", 11))
        btn_abrir.pack(pady=5, padx=20, fill="x")

    def _crear_panel_derecho(self):
        if USAR_CTK:
            panel = ctk.CTkFrame(self, fg_color="#111827", corner_radius=10)
        else:
            panel = tk.Frame(self, bg="#111827")
        panel.grid(row=0, column=1, padx=(0,10), pady=10, sticky="nsew")
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(0, weight=3)
        panel.grid_rowconfigure(1, weight=1)

        # --- Tabla de Preview ---
        frame_tabla = ctk.CTkFrame(panel, fg_color="transparent")
        frame_tabla.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        frame_tabla.columnconfigure(0, weight=1)
        frame_tabla.rowconfigure(0, weight=1)

        self.tree = tk.ttk.Treeview(frame_tabla, columns=("Ensayo", "X", "Y", "COTA", "ABS"), show="headings")
        self.tree.grid(row=0, column=0, sticky="nsew")
        for col in ("Ensayo", "X", "Y", "COTA", "ABS"):
            self.tree.heading(col, text=col, command=lambda _c=col: self._sort_by(_c))
            self.tree.column(col, width=140, anchor="center")

        scrollbar = tk.ttk.Scrollbar(frame_tabla, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.bind("<Double-1>", self._on_double_click_table)

        # --- Panel de Log ---
        frame_log = ctk.CTkFrame(panel, fg_color="#1F2937", corner_radius=8)
        frame_log.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        lbl_log = ctk.CTkLabel(frame_log, text="Log del sistema", font=("Arial", 11, "bold"), text_color="#F9FAFB")
        lbl_log.pack(anchor="w", padx=10, pady=(5,0))
        self.txt_log = ctk.CTkTextbox(frame_log, wrap="word", height=120, fg_color="#111827", text_color="#10B981", font=("Consolas", 10))
        self.txt_log.pack(fill="both", expand=True, padx=10, pady=(0,5))

    def _crear_barra_estado(self):
        if USAR_CTK:
            barra = ctk.CTkFrame(self, height=30, fg_color="#111827", corner_radius=0)
        else:
            barra = tk.Frame(self, height=30, bg="#111827")
        barra.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0,10))

        self.lbl_estado = ctk.CTkLabel(barra, text="Listo - Presiona Ctrl+V para pegar imagenes", font=("Arial", 10), text_color="#9CA3AF")
        self.lbl_estado.pack(side="left", padx=15, pady=3)

    def _checks_iniciales(self):
        tesseract_path = ocr_engine.encontrar_tesseract()
        if tesseract_path:
            self._log(f"Tesseract detectado: {tesseract_path}")
        else:
            self._log("[ADVERTENCIA] Tesseract no detectado. Configuralo antes de procesar.")

    # ================================================================
    # Gestion del Portapapeles y Drop
    # ================================================================
    def _pegar_imagenes(self):
        """Extrae imagenes del portapapeles y las almacena en memoria."""
        import cv2
        import numpy as np
        from PIL import Image, ImageGrab

        nuevas = get_clipboard_images()
        if not nuevas:
            messagebox.showinfo("No hay imagenes", "El portapapeles no contiene imagenes.")
            return

        for i, img_array in enumerate(nuevas):
            nombre = f"clipboard_{len(self.imagenes_pendientes) + i + 1}.png"
            self.imagenes_pendientes.append((nombre, img_array))

        self.lbl_imagenes.configure(text=f"{len(self.imagenes_pendientes)} imagenes cargadas")
        self._log(f"Pegadas {len(nuevas)} imagenes del portapapeles (total: {len(self.imagenes_pendientes)})")
        self.lbl_estado.configure(text=f"{len(self.imagenes_pendientes)} imagenes listas para procesar")

    def _on_drop(self, event):
        """Maneja el evento de drag and drop de archivos."""
        import cv2
        if event.data:
            # En tkinterdnd2, event.data es una cadena con rutas separadas por espacios (puede ser tricky)
            # Intentar parsear rutas de archivo
            rutas = self._parsear_rutas_drop(event.data)
            for ruta in rutas:
                if os.path.isfile(ruta):
                    try:
                        img = cv2.imread(ruta)
                        if img is not None:
                            nombre = os.path.basename(ruta)
                            self.imagenes_pendientes.append((nombre, img))
                            self._log(f"Arrastrado: {nombre}")
                        else:
                            self._log(f"[ERROR] No se pudo leer: {ruta}")
                    except Exception as e:
                        self._log(f"[ERROR] {ruta}: {e}")
            self.lbl_imagenes.configure(text=f"{len(self.imagenes_pendientes)} imagenes cargadas")

    def _parsear_rutas_drop(self, data):
        """Parsea las rutas del evento drop de tkinterdnd2."""
        import re
        # Intentar extraer rutas entre llaves o comillas
        rutas = re.findall(r'\{([^}]+)\}', data)
        if rutas:
            return rutas
        # Fallback: separar por espacios (menos fiable con espacios en rutas)
        return [data.strip()]

    # ================================================================
    # Cola de eventos y utilidades
    # ================================================================
    def _poll_queue(self):
        try:
            while True:
                tipo, dato = self.queue.get_nowait()
                if tipo == "log":
                    self._log(dato)
                elif tipo == "info":
                    messagebox.showinfo("Informacion", dato)
                elif tipo == "error":
                    messagebox.showerror("Error", dato)
                elif tipo == "estado":
                    self.lbl_estado.configure(text=dato)
                elif tipo == "progreso":
                    self.progreso.set(dato / 100.0)
                elif tipo == "fila":
                    self._agregar_fila(dato)
                elif tipo == "done":
                    self.proceso_terminado(dato)
        except queue.Empty:
            pass
        self.after(100, self._poll_queue)

    def _log(self, texto):
        if hasattr(self, "txt_log"):
            self.txt_log.insert("end", f"{texto}\n")
            self.txt_log.see("end")

    def limpiar_tabla(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.resultados = []
        self.progreso.set(0)

    def _limpiar_todo(self):
        self.imagenes_pendientes.clear()
        self.resultados = []
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.progreso.set(0)
        self.lbl_imagenes.configure(text="0 imagenes cargadas")
        self.lbl_estado.configure(text="Listo - Presiona Ctrl+V para pegar imagenes")
        self._log("=== PANTALLA LIMPIADA ===")

    def _agregar_fila(self, registro):
        self.tree.insert("", "end", values=(
            registro.get("Ensayo", ""),
            registro.get("X", ""),
            registro.get("Y", ""),
            registro.get("COTA", ""),
            registro.get("ABS", ""),
        ))

    # ================================================================
    # Ordenar tabla por columna
    # ================================================================
    def _sort_by(self, col):
        """Ordena la tabla por la columna seleccionada."""
        # Toggle direction on repeated clicks
        if self._sort_col == col:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_col = col
            self._sort_reverse = False

        def _sort_key(item):
            val = item.get(col, "")
            if col == "Ensayo":
                return str(val).lower()
            try:
                return float(val) if val not in (None, "") else 0
            except (ValueError, TypeError):
                return 0

        try:
            self.resultados.sort(key=_sort_key, reverse=self._sort_reverse)
        except Exception as e:
            self._log(f"[ERROR] No se pudo ordenar: {e}")
            return

        self._refresh_tree()

    def _refresh_tree(self):
        """Limpia y repobla el Treeview con self.resultados."""
        for item in self.tree.get_children():
            self.tree.delete(item)
        for reg in self.resultados:
            self.tree.insert("", "end", values=(
                reg.get("Ensayo", ""),
                reg.get("X", ""),
                reg.get("Y", ""),
                reg.get("COTA", ""),
                reg.get("ABS", ""),
            ))

    def proceso_terminado(self, resultados):
        if resultados is not None:
            self.resultados = resultados
            # Aplicar ordenamiento por defecto
            self.resultados = sorter.ordenar_registros(self.resultados)
            self._refresh_tree()
            self._log(f"=== PROCESO COMPLETADO: {len(resultados)} registros ===")
            self.lbl_estado.configure(text=f"Procesado: {len(resultados)} registros. Listo para guardar Excel.")
        else:
            self._log("=== PROCESO CANCELADO ===")

    # ================================================================
    # Acciones
    # ================================================================
    def _iniciar_proceso(self):
        if not self.imagenes_pendientes:
            messagebox.showerror("Error", "No hay imagenes cargadas. Usa Ctrl+V para pegar.")
            return
        if not ocr_engine.encontrar_tesseract():
            messagebox.showerror("Error", "Tesseract no encontrado. Configuralo antes de procesar.")
            return
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("Espere", "Ya hay un proceso en curso.")
            return

        self.limpiar_tabla()
        self.resultados = []
        self.worker = WorkerProceso(self, self.imagenes_pendientes.copy())
        self.worker.start()

    def _guardar_excel(self):
        if not self.resultados:
            messagebox.showerror("Error", "No hay datos para guardar. Procesa primero.")
            return
        try:
            ruta = excel_writer.escribir_excel(sorter.ordenar_registros(self.resultados))
            self.ultima_ruta_excel = ruta
            messagebox.showinfo("Informacion", f"Excel guardado en:\n{ruta}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _exportar_temporal(self):
        if not self.resultados:
            messagebox.showerror("Error", "No hay datos para exportar. Procesa primero.")
            return
        try:
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            temp_dir = tempfile.gettempdir()
            ruta_temp = Path(temp_dir) / f"Topografia_{timestamp}.xlsx"
            ruta = excel_writer.escribir_excel(sorter.ordenar_registros(self.resultados.copy()), str(ruta_temp))
            self.ultima_ruta_excel = ruta
            self._log(f"Excel temporal: {ruta}")
            messagebox.showinfo("Informacion", f"Excel temporal exportado a:\n{ruta}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _abrir_ultimo_excel(self):
        if not self.ultima_ruta_excel or not os.path.exists(self.ultima_ruta_excel):
            messagebox.showerror("Error", "No hay Excel generado para abrir. Exporta primero.")
            return
        try:
            os.startfile(self.ultima_ruta_excel)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir el Excel: {e}")

    def _on_double_click_table(self, event):
        item_id = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        if not item_id or col == "#0":
            return
        col_idx = int(col[1:]) - 1
        columnas = self.tree["columns"]
        if col_idx < 0 or col_idx >= len(columnas):
            return
        campo = columnas[col_idx]
        valores = self.tree.item(item_id, "values")
        valor_actual = valores[col_idx]
        dialog = tk.Toplevel(self)
        dialog.title(f"Editar {campo}")
        dialog.geometry("200x80")
        dialog.transient(self)
        entry = tk.Entry(dialog)
        entry.insert(0, str(valor_actual))
        entry.pack(padx=10, pady=10)
        entry.focus_set()

        def guardar():
            nuevos = list(valores)
            nuevos[col_idx] = entry.get()
            self.tree.item(item_id, values=tuple(nuevos))
            dialog.destroy()
        tk.Button(dialog, text="Guardar", command=guardar).pack(pady=5)
