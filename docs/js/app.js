/**
 * app.js
 * Interfaz de usuario: pegar/subir imágenes, tabla editable, mapa (online y
 * offline) y exportación CSV. Corre 100% en el navegador.
 */
(function () {
  "use strict";

  const COLUMNAS = window.TopoParser.COLUMNAS;

  const el = {
    estadoConexion: document.getElementById("estado-conexion"),
    zonaPegar: document.getElementById("zona-pegar"),
    inputArchivo: document.getElementById("input-archivo"),
    btnProcesar: document.getElementById("btn-procesar"),
    mensajeEstado: document.getElementById("mensaje-estado"),
    detalleOcr: document.getElementById("detalle-ocr"),
    textoOcrCrudo: document.getElementById("texto-ocr-crudo"),
    seccionResultados: document.getElementById("seccion-resultados"),
    mensajeVacio: document.getElementById("mensaje-vacio"),
    tablaBody: document.querySelector("#tabla-resultados tbody"),
    btnAgregarFila: document.getElementById("btn-agregar-fila"),
    metricaRegistros: document.getElementById("metrica-registros"),
    metricaVacios: document.getElementById("metrica-vacios"),
    metricaPuntos: document.getElementById("metrica-puntos"),
    selectDatum: document.getElementById("select-datum"),
    inputZona: document.getElementById("input-zona"),
    mapaOffline: document.getElementById("mapa-offline"),
    btnXlsx: document.getElementById("btn-xlsx"),
    btnLimpiar: document.getElementById("btn-limpiar"),
    capasControl: document.getElementById("capas-control"),
  };

  let registros = []; // [{Ensayo,X,Y,COTA,ABS}]
  let _idCounter = 0;
  let archivosSeleccionados = [];
  let mapaLeaflet = null;
  let capaMarcadores = null;

  // ---- Estado de conexión --------------------------------------------
  function actualizarEstadoConexion() {
    const online = navigator.onLine;
    el.estadoConexion.textContent = online ? "🟢 En línea" : "🟡 Sin conexión — funcionando en modo offline";
  }
  window.addEventListener("online", actualizarEstadoConexion);
  window.addEventListener("offline", actualizarEstadoConexion);
  actualizarEstadoConexion();

  // ---- Mensajes ---------------------------------------------------------
  function mostrarMensaje(texto, esError) {
    el.mensajeEstado.textContent = texto;
    el.mensajeEstado.hidden = false;
    el.mensajeEstado.classList.toggle("error", !!esError);
  }
  function ocultarMensaje() {
    el.mensajeEstado.hidden = true;
  }

  // ---- Pegar imagen (Ctrl+V) --------------------------------------------
  el.zonaPegar.addEventListener("paste", async (evento) => {
    const items = (evento.clipboardData || window.clipboardData).items;
    for (const item of items) {
      if (item.type.startsWith("image/")) {
        const archivo = item.getAsFile();
        await procesarArchivos([archivo]);
        return;
      }
    }
    mostrarMensaje("El portapapeles no contiene una imagen.", true);
  });
  el.zonaPegar.addEventListener("click", () => el.zonaPegar.focus());

  // ---- Subir imagen -------------------------------------------------
  el.inputArchivo.addEventListener("change", () => {
    archivosSeleccionados = Array.from(el.inputArchivo.files || []);
    el.btnProcesar.disabled = archivosSeleccionados.length === 0;
  });
  el.btnProcesar.addEventListener("click", async () => {
    if (!archivosSeleccionados.length) return;
    await procesarArchivos(archivosSeleccionados);
    archivosSeleccionados = [];
    el.inputArchivo.value = "";
    el.btnProcesar.disabled = true;
  });

  async function procesarArchivos(archivos) {
    ocultarMensaje();
    let procesadas = 0;
    const errores = [];
    for (const archivo of archivos) {
      try {
        const { registro, textoOcr } = await window.TopoOcr.leerImagen(archivo, (estado) =>
          mostrarMensaje(`${estado} (${archivo.name})`)
        );
        agregarRegistro(registro);
        el.textoOcrCrudo.textContent = textoOcr;
        el.detalleOcr.hidden = false;
        procesadas += 1;
      } catch (e) {
        console.error(e);
        errores.push(`${archivo.name}: ${e.message || e}`);
      }
    }
    if (procesadas) {
      mostrarMensaje(`Procesada${procesadas > 1 ? "s" : ""} ${procesadas} imagen(es).`);
    }
    if (errores.length) {
      mostrarMensaje(`No se pudo leer: ${errores.join(" · ")}`, true);
    }
    renderizarTodo();
  }

  // ---- Tabla de resultados ----------------------------------------------
  function agregarRegistro(reg) {
    registros.push({
      _id: ++_idCounter,
      Ensayo: reg.Ensayo || "",
      X: reg.X || "",
      Y: reg.Y || "",
      COTA: reg.COTA || "",
      ABS: reg.ABS || "",
    });
  }

  function renderizarTabla() {
    const ordenados = window.TopoParser.ordenarRegistros(registros);
    el.tablaBody.innerHTML = "";
    for (const reg of ordenados) {
      const tr = document.createElement("tr");
      for (const col of COLUMNAS) {
        const td = document.createElement("td");
        td.contentEditable = "true";
        td.textContent = reg[col];
        td.dataset.id = reg._id;
        td.dataset.col = col;
        td.addEventListener("input", () => {
          const r = registros.find((x) => x._id === reg._id);
          if (r) r[col] = td.textContent.trim();
          renderizarMetricasYMapa();
        });
        tr.appendChild(td);
      }
      const tdBorrar = document.createElement("td");
      const btn = document.createElement("button");
      btn.className = "btn-borrar-fila";
      btn.textContent = "✕";
      btn.title = "Eliminar fila";
      btn.addEventListener("click", () => {
        registros = registros.filter((x) => x._id !== reg._id);
        renderizarTodo();
      });
      tdBorrar.appendChild(btn);
      tr.appendChild(tdBorrar);
      el.tablaBody.appendChild(tr);
    }
  }

  el.btnAgregarFila.addEventListener("click", () => {
    agregarRegistro({ Ensayo: "", X: "", Y: "", COTA: "", ABS: "" });
    renderizarTodo();
  });

  el.btnLimpiar.addEventListener("click", () => {
    registros = [];
    el.textoOcrCrudo.textContent = "";
    el.detalleOcr.hidden = true;
    ocultarMensaje();
    renderizarTodo();
  });

  // ---- Simbología canvas --------------------------------------------
  function dibujarFormaCanvas(ctx, x, y, tipo, color, oscuro) {
    const r = tipo === "POZO" ? 8 : tipo === "VDC" ? 7 : tipo === "DCP" ? 6 : tipo === "TIS" ? 7 : tipo === "DCA" ? 8 : 6;
    const [cr, cg, cb] = color;
    ctx.fillStyle = `rgb(${cr},${cg},${cb})`;
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 2;
    if (tipo === "POZO" || !tipo) {
      ctx.beginPath(); ctx.arc(x, y, r, 0, 2 * Math.PI); ctx.fill(); ctx.stroke();
    } else if (tipo === "VDC") {
      ctx.beginPath();
      ctx.moveTo(x, y - r); ctx.lineTo(x + r, y + r * 0.7); ctx.lineTo(x - r, y + r * 0.7);
      ctx.closePath(); ctx.fill(); ctx.stroke();
    } else if (tipo === "DCP") {
      ctx.fillRect(x - r * 0.7, y - r * 0.7, r * 1.4, r * 1.4);
      ctx.strokeRect(x - r * 0.7, y - r * 0.7, r * 1.4, r * 1.4);
    } else if (tipo === "TIS") {
      ctx.beginPath();
      ctx.moveTo(x, y - r); ctx.lineTo(x + r * 0.7, y);
      ctx.lineTo(x, y + r); ctx.lineTo(x - r * 0.7, y);
      ctx.closePath(); ctx.fill(); ctx.stroke();
    } else if (tipo === "DCA") {
      ctx.beginPath();
      ctx.moveTo(x - r, y); ctx.lineTo(x + r, y);
      ctx.moveTo(x, y - r); ctx.lineTo(x, y + r);
      ctx.strokeStyle = `rgb(${cr},${cg},${cb})`;
      ctx.lineWidth = 4; ctx.stroke();
      ctx.strokeStyle = "#ffffff"; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(x, y, r, 0, 2 * Math.PI); ctx.stroke();
    } else {
      ctx.beginPath(); ctx.arc(x, y, r, 0, 2 * Math.PI);
      ctx.fillStyle = "transparent"; ctx.strokeStyle = `rgb(${cr},${cg},${cb})`;
      ctx.lineWidth = 2; ctx.stroke();
    }
  }

  // ---- Capas activas ------------------------------------------------
  function getTiposActivos() {
    const cbs = el.capasControl.querySelectorAll(".capa-toggle");
    const activos = [];
    for (const cb of cbs) if (cb.checked) activos.push(cb.dataset.tipo);
    return activos;
  }

  // ---- Métricas + mapa ----------------------------------------------
  function construirPuntosMapa() {
    const zona = parseInt(el.inputZona.value, 10) || 17;
    const datum = el.selectDatum.value;
    const activos = getTiposActivos();
    const puntos = [];
    for (const reg of registros) {
      const [tipo] = window.TopoParser.extraerTipoNumero(reg.Ensayo);
      if (!activos.includes(tipo)) continue;
      const geo = window.TopoGeo.utmALatLon(reg.X, reg.Y, { zona, datum });
      if (!geo) continue;
      puntos.push({ ...reg, lat: geo.lat, lon: geo.lon });
    }
    return puntos;
  }

  function contarVacios() {
    let vacios = 0;
    for (const reg of registros) {
      for (const c of COLUMNAS) if (!reg[c]) vacios += 1;
    }
    return vacios;
  }

  function inicializarMapa() {
    if (mapaLeaflet) return;
    mapaLeaflet = L.map("mapa").setView([-3.58, -78.47], 14);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap",
    }).addTo(mapaLeaflet);
    capaMarcadores = L.layerGroup().addTo(mapaLeaflet);
  }

  function dibujarMapaOnline(puntos) {
    inicializarMapa();
    capaMarcadores.clearLayers();
    if (!puntos.length) return;
    const bounds = [];
    for (const p of puntos) {
      const [tipo] = window.TopoParser.extraerTipoNumero(p.Ensayo);
      const simb = window.TopoParser.simbologiaPara(p.Ensayo);
      const [r, g, b] = simb.color;
      const colorStr = `rgb(${r},${g},${b})`;
      const marcador = L.circleMarker([p.lat, p.lon], {
        radius: simb.radio,
        color: "#fff",
        weight: 2,
        fillColor: colorStr,
        fillOpacity: 0.9,
      }).bindTooltip(`<b>${p.Ensayo || "—"}</b><br>X: ${p.X}<br>Y: ${p.Y}<br>COTA: ${p.COTA}`, {
        permanent: false,
      });
      marcador.addTo(capaMarcadores);
      bounds.push([p.lat, p.lon]);
    }
    if (bounds.length === 1) {
      mapaLeaflet.setView(bounds[0], 16);
    } else {
      mapaLeaflet.fitBounds(bounds, { padding: [30, 30] });
    }
    setTimeout(() => mapaLeaflet.invalidateSize(), 150);
  }

  function dibujarMapaOffline(puntos) {
    const ctx = el.mapaOffline.getContext("2d");
    const w = el.mapaOffline.width;
    const h = el.mapaOffline.height;
    const oscuro = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
    ctx.fillStyle = oscuro ? "#0f172a" : "#ffffff";
    ctx.fillRect(0, 0, w, h);

    if (!puntos.length) {
      ctx.fillStyle = oscuro ? "#94a3b8" : "#64748b";
      ctx.font = "14px sans-serif";
      ctx.fillText("Sin coordenadas X/Y válidas todavía.", 16, 24);
      return;
    }

    const xs = puntos.map((p) => parseFloat(p.X));
    const ys = puntos.map((p) => parseFloat(p.Y));
    const margen = 40;
    const minX = Math.min(...xs), maxX = Math.max(...xs);
    const minY = Math.min(...ys), maxY = Math.max(...ys);
    const rangoX = Math.max(maxX - minX, 1);
    const rangoY = Math.max(maxY - minY, 1);
    const escala = Math.min((w - 2 * margen) / rangoX, (h - 2 * margen) / rangoY);

    const px = (x) => margen + (x - minX) * escala;
    const py = (y) => h - margen - (y - minY) * escala;

    ctx.strokeStyle = oscuro ? "#1e293b" : "#e2e8f0";
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
      const y = margen + ((h - 2 * margen) / 4) * i;
      ctx.beginPath(); ctx.moveTo(margen, y); ctx.lineTo(w - margen, y); ctx.stroke();
    }

    ctx.fillStyle = oscuro ? "#e2e8f0" : "#0f172a";
    ctx.font = "12px sans-serif";
    ctx.fillText("Este (X) →", w - margen - 70, h - 12);
    ctx.save();
    ctx.translate(14, margen + 10);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText("Norte (Y) →", 0, 0);
    ctx.restore();

    for (const p of puntos) {
      const x = px(parseFloat(p.X));
      const y = py(parseFloat(p.Y));
      const [tipo] = window.TopoParser.extraerTipoNumero(p.Ensayo);
      const simb = window.TopoParser.simbologiaPara(p.Ensayo);
      dibujarFormaCanvas(ctx, x, y, tipo, simb.color, oscuro);
      ctx.fillStyle = oscuro ? "#e2e8f0" : "#0f172a";
      ctx.font = "12px sans-serif";
      ctx.fillText(p.Ensayo || "—", x + 9, y - 9);
    }
  }

  function renderizarMetricasYMapa() {
    el.metricaRegistros.textContent = registros.length;
    el.metricaVacios.textContent = contarVacios();
    const puntos = construirPuntosMapa();
    el.metricaPuntos.textContent = puntos.length;
    dibujarMapaOnline(puntos);
    dibujarMapaOffline(puntos);
  }

  el.selectDatum.addEventListener("change", renderizarMetricasYMapa);
  el.inputZona.addEventListener("change", renderizarMetricasYMapa);
  el.capasControl.addEventListener("change", renderizarMetricasYMapa);

  // ---- XLSX ---------------------------------------------------------
  function descargarXlsx() {
    const ordenados = window.TopoParser.ordenarRegistros(registros);
    const data = ordenados.map((r) => {
      const obj = {};
      for (const c of COLUMNAS) obj[c] = r[c] || "";
      return obj;
    });
    const ws = XLSX.utils.json_to_sheet(data);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, "Coordenadas");
    const wbout = XLSX.write(wb, { bookType: "xlsx", type: "array" });
    const blob = new Blob([wbout], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "coordenadas.xlsx";
    a.click();
    URL.revokeObjectURL(url);
  }
  el.btnXlsx.addEventListener("click", descargarXlsx);

  // ---- Render general -------------------------------------------------
  function renderizarTodo() {
    const hayDatos = registros.length > 0;
    el.seccionResultados.hidden = !hayDatos;
    el.mensajeVacio.hidden = hayDatos;
    if (hayDatos) {
      renderizarTabla();
      renderizarMetricasYMapa();
    }
  }

  renderizarTodo();

  // ---- Service worker (offline) --------------------------------------
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("sw.js").catch((e) => console.warn("SW no registrado:", e));
    });
  }
})();
