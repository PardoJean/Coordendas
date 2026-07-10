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
    btnCsv: document.getElementById("btn-csv"),
    btnLimpiar: document.getElementById("btn-limpiar"),
  };

  let registros = []; // [{Ensayo,X,Y,COTA,ABS}]
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
      Ensayo: reg.Ensayo || "",
      X: reg.X || "",
      Y: reg.Y || "",
      COTA: reg.COTA || "",
      ABS: reg.ABS || "",
    });
  }

  function renderizarTabla() {
    el.tablaBody.innerHTML = "";
    registros.forEach((reg, indice) => {
      const tr = document.createElement("tr");
      for (const col of COLUMNAS) {
        const td = document.createElement("td");
        td.contentEditable = "true";
        td.textContent = reg[col];
        td.addEventListener("input", () => {
          registros[indice][col] = td.textContent.trim();
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
        registros.splice(indice, 1);
        renderizarTodo();
      });
      tdBorrar.appendChild(btn);
      tr.appendChild(tdBorrar);
      el.tablaBody.appendChild(tr);
    });
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

  // ---- Métricas + mapa ----------------------------------------------
  function construirPuntosMapa() {
    const zona = parseInt(el.inputZona.value, 10) || 17;
    const datum = el.selectDatum.value;
    const puntos = [];
    for (const reg of registros) {
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
      const marcador = L.circleMarker([p.lat, p.lon], {
        radius: 7,
        color: "#fff",
        weight: 2,
        fillColor: "#dc2626",
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
    const py = (y) => h - margen - (y - minY) * escala; // Norte hacia arriba

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
      ctx.beginPath();
      ctx.arc(x, y, 6, 0, 2 * Math.PI);
      ctx.fillStyle = "#dc2626";
      ctx.fill();
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 2;
      ctx.stroke();
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

  // ---- CSV ----------------------------------------------------------
  function descargarCsv() {
    const filas = [COLUMNAS.join(",")];
    for (const reg of registros) {
      filas.push(COLUMNAS.map((c) => `"${String(reg[c] || "").replace(/"/g, '""')}"`).join(","));
    }
    const blob = new Blob(["﻿" + filas.join("\r\n")], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "coordenadas.csv";
    a.click();
    URL.revokeObjectURL(url);
  }
  el.btnCsv.addEventListener("click", descargarCsv);

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
