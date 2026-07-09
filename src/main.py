"""Punto de entrada de la aplicación Procesador Topográfico v3.0."""
import sys
from pathlib import Path

# Asegurar que el directorio raiz del proyecto este en sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from src import gui

def main():
    app = gui.App()
    app.mainloop()

if __name__ == "__main__":
    main()
