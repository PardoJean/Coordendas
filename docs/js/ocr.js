/**
 * ocr.js
 * Orquesta Tesseract.js para leer una imagen, replicando la estrategia de
 * topo_parser.leer_imagen(): prueba varios modos de segmentación (--psm) y
 * se queda con el resultado más completo; si el Ensayo no queda clasificado,
 * hace una segunda pasada recortando y releyendo solo el campo "Código".
 *
 * Todo corre dentro del navegador (WebAssembly), sin servidor ni internet
 * una vez que los archivos de docs/vendor/tesseract y docs/tessdata quedaron
 * en caché (ver sw.js).
 */
(function (global) {
  "use strict";

  const { COLUMNAS, parsear, extraerEnsayo } = window.TopoParser;

  const PSM_INTENTOS = ["6", "4", "3", "11"];
  const PSM_BUSCAR_CODIGO = ["3", "4", "11", "12", "6"];
  const PSM_RECORTE_CODIGO = ["11", "6", "7"];
  const PATRON_ETIQUETA_CODIGO = /C[ÓO0][D0]IG[O0]/i;

  let workerPromise = null;

  function crearWorker() {
    if (!workerPromise) {
      workerPromise = Tesseract.createWorker(["spa", "eng"], 1, {
        workerPath: "vendor/tesseract/worker.min.js",
        corePath: "vendor/tesseract/",
        langPath: "tessdata/",
        gzip: true,
        cacheMethod: "readWrite",
        logger: () => {},
      });
    }
    return workerPromise;
  }

  function puntuar(reg) {
    let puntos = 0;
    for (const c of COLUMNAS) {
      const valor = reg[c] || "";
      if (c === "Ensayo") {
        if (valor && valor !== "SIN CLASIFICAR") puntos += 1;
      } else if (valor !== "") {
        puntos += 1;
      }
    }
    return puntos;
  }

  async function reconocer(worker, imagen, psm) {
    await worker.setParameters({ tessedit_pageseg_mode: psm });
    return worker.recognize(imagen);
  }

  /** Recorta, de un <canvas>/imagen, la zona inmediatamente a la derecha de
   * la palabra "Código", donde está el valor (ej. "DCP 1", "VDC 5"). */
  function recortarValorCodigo(canvasOrigen, words) {
    for (const w of words || []) {
      if (!w.text || !PATRON_ETIQUETA_CODIGO.test(w.text)) continue;
      if ((w.confidence || 0) < 40) continue;
      const bbox = w.bbox;
      let alto = Math.min(bbox.y1 - bbox.y0, 60);
      const rellenoY = Math.max(12, Math.round(alto * 0.35));
      const x0 = Math.min(bbox.x1 + 12, canvasOrigen.width - 10);
      const x1 = Math.min(x0 + 380, canvasOrigen.width);
      const y0 = Math.max(bbox.y0 - rellenoY, 0);
      const y1 = Math.min(bbox.y1 + rellenoY, canvasOrigen.height);
      if (x1 - x0 < 20) continue;

      const recorte = document.createElement("canvas");
      recorte.width = x1 - x0;
      recorte.height = y1 - y0;
      recorte.getContext("2d").drawImage(canvasOrigen, x0, y0, x1 - x0, y1 - y0, 0, 0, x1 - x0, y1 - y0);
      return recorte;
    }
    return null;
  }

  async function clasificarPorRecorte(worker, canvasOrigen) {
    for (const psmBusqueda of PSM_BUSCAR_CODIGO) {
      const { data } = await reconocer(worker, canvasOrigen, psmBusqueda);
      const recorte = recortarValorCodigo(canvasOrigen, data.words);
      if (!recorte) continue;
      for (const psm of PSM_RECORTE_CODIGO) {
        const { data: dataRecorte } = await reconocer(worker, recorte, psm);
        const ensayo = extraerEnsayo(dataRecorte.text || "");
        if (ensayo !== "SIN CLASIFICAR") return ensayo;
      }
      return null; // ya se encontró "Código" pero no se logró clasificar
    }
    return null;
  }

  function imagenACanvas(imagenBitmapOFile) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => {
        const canvas = document.createElement("canvas");
        canvas.width = img.naturalWidth;
        canvas.height = img.naturalHeight;
        canvas.getContext("2d").drawImage(img, 0, 0);
        URL.revokeObjectURL(img.src);
        resolve(canvas);
      };
      img.onerror = reject;
      img.src = URL.createObjectURL(imagenBitmapOFile);
    });
  }

  /**
   * Lee una imagen (File/Blob) y devuelve {registro, textoOcr}, igual que
   * topo_parser.leer_imagen() en la versión Python.
   */
  async function leerImagen(archivo, onProgreso) {
    const worker = await crearWorker();
    const canvas = await imagenACanvas(archivo);

    let mejorReg = null;
    let mejorTexto = "";
    let mejorPuntos = -1;

    for (let i = 0; i < PSM_INTENTOS.length; i++) {
      if (onProgreso) onProgreso(`Analizando (modo ${i + 1}/${PSM_INTENTOS.length})…`);
      const { data } = await reconocer(worker, canvas, PSM_INTENTOS[i]);
      const reg = parsear(data.text || "");
      const puntos = puntuar(reg);
      if (puntos > mejorPuntos) {
        mejorReg = reg;
        mejorTexto = data.text || "";
        mejorPuntos = puntos;
      }
      if (puntos === COLUMNAS.length) break;
    }

    if (mejorReg.Ensayo === "SIN CLASIFICAR") {
      if (onProgreso) onProgreso("Afinando lectura del campo Código…");
      const ensayoRecorte = await clasificarPorRecorte(worker, canvas);
      if (ensayoRecorte) mejorReg = { ...mejorReg, Ensayo: ensayoRecorte };
    }

    return { registro: mejorReg, textoOcr: mejorTexto };
  }

  global.TopoOcr = { leerImagen };
})(window);
