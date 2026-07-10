"""
Procesador Topográfico — Aplicación de escritorio (offline).

Lee capturas de topografía con OCR y exporta a Excel/CSV, SIN necesidad de
internet. Reutiliza exactamente la misma lógica de extracción que la versión
web (topo_parser.py), e incluye una vista Este/Norte de los puntos que también
funciona sin conexión (no usa mapas web, solo las coordenadas planas UTM).

Al compilarse como .exe (PyInstaller) trae Tesseract incluido, así que el
usuario final solo abre el programa con doble clic.
"""
import os
import queue
import shutil
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image


# ────────────────────────────────────────────────────────────────────────────
# Localizar Tesseract (incluido dentro del .exe cuando está compilado)
# ────────────────────────────────────────────────────────────────────────────
def _configurar_tesseract():
    import pytesseract

    if getattr(sys, "frozen", False):  # ejecutándose como .exe (PyInstaller)
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        tess = os.path.join(base, "tesseract", "tesseract.exe")
        tessdata = os.path.join(base, "tesseract", "tessdata")
        if os.path.exists(tess):
            pytesseract.pytesseract.tesseract_cmd = tess
            if os.path.isdir(tessdata):
                os.environ["TESSDATA_PREFIX"] = tessdata
            return
    ruta = shutil.which("tesseract")
    if ruta:
        pytesseract.pytesseract.tesseract_cmd = ruta


_configurar_tesseract()

from topo_parser import COLUMNAS, TIPOS, SIMBOLOGIA, _SIMBOLOGIA_SIN, leer_imagen, ordenar_registros, extraer_tipo_numero  # noqa: E402


# ────────────────────────────────────────────────────────────────────────────
# Hilo de procesamiento (OCR) para no congelar la interfaz
# ────────────────────────────────────────────────────────────────────────────
class Trabajador(threading.Thread):
    def __init__(self, cola, rutas):
        super().__init__(daemon=True)
        self.cola = cola
        self.rutas = rutas

    def run(self):
        total = len(self.rutas)
        for i, ruta in enumerate(self.rutas, start=1):
            nombre = os.path.basename(ruta)
            self.cola.put(("estado", f"Procesando {i}/{total}: {nombre}"))
            try:
                reg, _texto = leer_imagen(Image.open(ruta))
            except Exception as e:  # noqa: BLE001
                self.cola.put(("log", f"[ERROR] {nombre}: {e}"))
                continue
            self.cola.put(("fila", reg))
            self.cola.put(("log", f"[OK] {nombre} → {reg.get('Ensayo', '—')}"))
        self.cola.put(("fin", total))


# ────────────────────────────────────────────────────────────────────────────
# Ventana principal
# ────────────────────────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Procesador Topográfico — Offline")
        self.geometry("980x620")
        self.minsize(820, 520)

        self.cola = queue.Queue()
        self.trabajador = None
        self.ultima_ruta = None
        self.registros_tmp = []  # para acumular y ordenar al terminar

        self._crear_widgets()
        self.after(100, self._revisar_cola)

    # -- Construcción de la interfaz --------------------------------------
    def _crear_widgets(self):
        barra = ttk.Frame(self, padding=8)
        barra.pack(side="top", fill="x")

        ttk.Button(barra, text="📂 Abrir imágenes…", command=self.abrir_imagenes).pack(side="left", padx=3)
        ttk.Button(barra, text="🗺️ Ver Este/Norte", command=self.ver_mapa).pack(side="left", padx=3)
        ttk.Button(barra, text="⬇️ Guardar Excel", command=self.guardar_excel).pack(side="left", padx=3)
        ttk.Button(barra, text="🗑️ Limpiar", command=self.limpiar).pack(side="left", padx=3)

        cont = ttk.Frame(self, padding=(8, 0))
        cont.pack(side="top", fill="both", expand=True)

        self.tabla = ttk.Treeview(cont, columns=COLUMNAS, show="headings", height=14)
        for col in COLUMNAS:
            self.tabla.heading(col, text=col)
            self.tabla.column(col, width=150, anchor="center")
        self.tabla.pack(side="left", fill="both", expand=True)
        self.tabla.bind("<Double-1>", self._editar_celda)

        scroll = ttk.Scrollbar(cont, orient="vertical", command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=scroll.set)
        scroll.pack(side="left", fill="y")

        ttk.Label(self, text="Doble clic en una celda para corregir un valor.",
                  foreground="#555").pack(side="top", anchor="w", padx=10)

        marco_log = ttk.LabelFrame(self, text="Registro", padding=4)
        marco_log.pack(side="top", fill="x", padx=8, pady=6)
        self.log = tk.Text(marco_log, height=6, wrap="word")
        self.log.pack(fill="x")

        self.estado = ttk.Label(self, text="Listo. Abre una o varias capturas para empezar.",
                                anchor="w", padding=6)
        self.estado.pack(side="bottom", fill="x")
        pie = ttk.Label(self, text="Versión 1.0 · © 2026 · Todos los derechos reservados",
                        anchor="center", foreground="#888", padding=2)
        pie.pack(side="bottom", fill="x")

    # -- Acciones ---------------------------------------------------------
    def abrir_imagenes(self):
        rutas = filedialog.askopenfilenames(
            title="Selecciona capturas de topografía",
            filetypes=[("Imágenes", "*.jpg *.jpeg *.png *.webp *.bmp"), ("Todos", "*.*")],
        )
        if not rutas:
            return
        if self.trabajador and self.trabajador.is_alive():
            messagebox.showinfo("Espera", "Ya hay un procesamiento en curso.")
            return
        self._log(f"Procesando {len(rutas)} imagen(es)…")
        self.trabajador = Trabajador(self.cola, list(rutas))
        self.trabajador.start()

    def ver_mapa(self):
        registros = [dict(zip(COLUMNAS, t)) for t in self._filas()]
        registros = ordenar_registros(registros)
        puntos = []
        for reg in registros:
            try:
                puntos.append((reg["Ensayo"] or "—", float(reg["X"]), float(reg["Y"])))
            except (ValueError, TypeError):
                continue
        if not puntos:
            messagebox.showinfo("Sin datos", "No hay coordenadas X/Y válidas para graficar.")
            return
        try:
            import matplotlib
            matplotlib.use("TkAgg")
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Error", f"No se pudo cargar el gráfico: {e}")
            return

        ventana = tk.Toplevel(self)
        ventana.title("Ubicación de los puntos (Este / Norte)")
        ventana.geometry("840x660")

        marco_ctrls = ttk.Frame(ventana)
        marco_ctrls.pack(side="top", fill="x", padx=8, pady=4)
        ttk.Label(marco_ctrls, text="Capas:").pack(side="left", padx=2)
        vars_capas = {}
        for tipo in TIPOS + ["SIN CLASIFICAR"]:
            v = tk.BooleanVar(value=True)
            vars_capas[tipo] = v
            cb = ttk.Checkbutton(marco_ctrls, text=tipo, variable=v)
            cb.pack(side="left", padx=4)

        fig = plt.Figure(figsize=(7, 6), dpi=100)
        ax = fig.add_subplot(111)
        lienzo = FigureCanvasTkAgg(fig, master=ventana)
        lienzo.get_tk_widget().pack(fill="both", expand=True)

        def redibujar():
            ax.clear()
            tipos_activos = {t for t, v in vars_capas.items() if v.get()}
            xs, ys, anotaciones = [], [], []
            leyenda_patches = []
            for nombre, x, y in puntos:
                tipo, _ = extraer_tipo_numero(nombre)
                if tipo not in tipos_activos:
                    continue
                simb = SIMBOLOGIA.get(tipo) or _SIMBOLOGIA_SIN
                color = f"#{simb['color'][0]:02x}{simb['color'][1]:02x}{simb['color'][2]:02x}"
                ax.scatter([x], [y], c=color, s=80, zorder=3, edgecolors="white",
                          marker=simb["marcador"])
                anotaciones.append(ax.annotate(nombre, (x, y), textcoords="offset points", xytext=(6, 6), fontsize=9))
                xs.append(x)
                ys.append(y)
            if xs and ys:
                ax.set_xlim(min(xs) - 5, max(xs) + 5)
                ax.set_ylim(min(ys) - 5, max(ys) + 5)
            # Repulsión de etiquetas con adjustText
            try:
                from adjustText import adjust_text
                adjust_text(anotaciones, ax=ax, only_move={"points": "xy", "text": "xy"},
                            arrowprops=dict(arrowstyle="-", color="gray", lw=0.4))
            except ImportError:
                pass
            # Leyenda
            from matplotlib.patches import Patch
            for tipo in TIPOS + ["SIN CLASIFICAR"]:
                simb = SIMBOLOGIA.get(tipo) or _SIMBOLOGIA_SIN
                color = f"#{simb['color'][0]:02x}{simb['color'][1]:02x}{simb['color'][2]:02x}"
                leyenda_patches.append(Patch(facecolor=color, label=tipo))
            ax.legend(handles=leyenda_patches, loc="lower right", fontsize=8, framealpha=0.9)
            ax.set_xlabel("Este (X)")
            ax.set_ylabel("Norte (Y)")
            ax.set_title("Puntos topográficos")
            ax.grid(True, linestyle="--", alpha=0.4)
            ax.ticklabel_format(style="plain", useOffset=False)
            ax.set_aspect("equal", adjustable="datalim")
            lienzo.draw()

        for v in vars_capas.values():
            v.trace_add("write", lambda *_: redibujar())

        redibujar()

    def guardar_excel(self):
        filas = [dict(zip(COLUMNAS, t)) for t in self._filas()]
        if not filas:
            messagebox.showerror("Error", "No hay datos para guardar.")
            return
        filas = ordenar_registros(filas)
        ruta = filedialog.asksaveasfilename(
            title="Guardar Excel", defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")], initialfile="coordenadas.xlsx",
        )
        if not ruta:
            return
        try:
            import pandas as pd
            pd.DataFrame(filas, columns=COLUMNAS).to_excel(ruta, index=False, sheet_name="Coordenadas")
            self.ultima_ruta = ruta
            self._log(f"Excel guardado: {ruta}")
            messagebox.showinfo("Guardado", f"Excel guardado en:\n{ruta}")
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Error", str(e))

    def limpiar(self):
        for item in self.tabla.get_children():
            self.tabla.delete(item)
        self.log.delete("1.0", "end")
        self.estado.configure(text="Listo. Abre una o varias capturas para empezar.")

    # -- Edición de celdas ------------------------------------------------
    def _editar_celda(self, evento):
        item = self.tabla.identify_row(evento.y)
        columna = self.tabla.identify_column(evento.x)
        if not item or not columna:
            return
        idx = int(columna[1:]) - 1
        if idx < 0 or idx >= len(COLUMNAS):
            return
        x, y, ancho, alto = self.tabla.bbox(item, columna)
        valor = self.tabla.set(item, COLUMNAS[idx])
        editor = tk.Entry(self.tabla)
        editor.insert(0, valor)
        editor.select_range(0, "end")
        editor.focus_set()
        editor.place(x=x, y=y, width=ancho, height=alto)

        def guardar(_evt=None):
            self.tabla.set(item, COLUMNAS[idx], editor.get())
            editor.destroy()

        editor.bind("<Return>", guardar)
        editor.bind("<FocusOut>", guardar)
        editor.bind("<Escape>", lambda _e: editor.destroy())

    # -- Utilidades -------------------------------------------------------
    def _filas(self):
        return [tuple(self.tabla.set(item, c) for c in COLUMNAS)
                for item in self.tabla.get_children()]

    def _log(self, texto):
        self.log.insert("end", texto + "\n")
        self.log.see("end")

    def _revisar_cola(self):
        try:
            while True:
                tipo, dato = self.cola.get_nowait()
                if tipo == "estado":
                    self.estado.configure(text=dato)
                elif tipo == "log":
                    self._log(dato)
                elif tipo == "fila":
                    self.registros_tmp.append(dato)
                    self.tabla.insert("", "end", values=tuple(dato.get(c, "") for c in COLUMNAS))
                elif tipo == "fin":
                    self.registros_tmp = ordenar_registros(self.registros_tmp)
                    for item in self.tabla.get_children():
                        self.tabla.delete(item)
                    for reg in self.registros_tmp:
                        self.tabla.insert("", "end", values=tuple(reg.get(c, "") for c in COLUMNAS))
                    self.registros_tmp = []
                    self.estado.configure(text=f"Listo. Procesadas {dato} imagen(es).")
        except queue.Empty:
            pass
        self.after(100, self._revisar_cola)


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
