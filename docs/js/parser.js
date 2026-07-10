/**
 * parser.js
 * Puerto directo de topo_parser.py (lógica de extracción de datos
 * topográficos a partir del texto OCR). Reglas de negocio idénticas a la
 * versión Python: mismo Ensayo, X, Y, COTA y ABS para el mismo texto OCR.
 */
(function (global) {
  "use strict";

  const TIPOS = ["POZO", "VDC", "DCP", "TIS", "DCA"];

  // Patrones tolerantes a errores típicos de OCR para cada tipo de ensayo.
  const PATRONES_TIPO = {
    POZO: /P[O0][ZS2][O0]|FES[O0]?|PES[O0]?|POZ|POS\b/,
    VDC: /VDC|V[O0]C[D0]?|VUC|VBC|UDC|FER|PYR[O0]|T[O0]E/,
    DCP: /DCP|D[O0]P/,
    TIS: /TIS/,
    DCA: /DCA/,
  };

  function truncar2(valor) {
    if (valor === null || valor === undefined || valor === "") return "";
    const limpio = String(valor).replace(/\s/g, "").replace(",", ".");
    const v = parseFloat(limpio);
    if (Number.isNaN(v)) return "";
    const truncado = Math.trunc(v * 100) / 100;
    return truncado.toFixed(2);
  }

  function numLimpio(texto) {
    if (!texto) return null;
    const m = texto.match(/[+-]?\d[\d\s.,]*\d|\d/);
    if (!m) return null;
    let crudo = m[0].replace(/\s/g, "").replace(",", ".");
    const partes = crudo.split(".");
    if (partes.length > 2) {
      crudo = partes.slice(0, -1).join("") + "." + partes[partes.length - 1];
    }
    return crudo;
  }

  function procesarAbs(crudo) {
    if (!crudo) return "";
    const s = String(crudo).toUpperCase();
    const m = s.match(/([+-]?)\s*0\s*[+-]\s*(\d+(?:[.,]\d+)?)/);
    if (m) {
      const signo = m[1];
      const numero = truncar2(m[2]);
      return numero ? `${signo}${numero}` : "";
    }
    const n = numLimpio(s);
    return n ? truncar2(n) : "";
  }

  function regionCodigo(up) {
    const m = up.match(/C[ÓO0][D0]IG[O0]/);
    if (!m) return null;
    const fin = m.index + m[0].length;
    return up.slice(fin, fin + 25);
  }

  function extraerEnsayo(texto) {
    const up = texto.toUpperCase();

    function buscarEn(region) {
      let mejor = null; // {pos, tipo, m}
      for (const tipo of TIPOS) {
        const patron = PATRONES_TIPO[tipo];
        const m = region.match(patron);
        if (m && (mejor === null || m.index < mejor.pos)) {
          mejor = { pos: m.index, tipo, m };
        }
      }
      return mejor;
    }

    let region = regionCodigo(up);
    let resultado = region ? buscarEn(region) : null;
    let textoBusqueda = region;

    if (!resultado) {
      resultado = buscarEn(up);
      textoBusqueda = up;
    }

    if (!resultado) return "SIN CLASIFICAR";

    const { tipo, m } = resultado;
    const fin = m.index + m[0].length;
    const resto = textoBusqueda.slice(fin, fin + 10);
    const mnum = resto.match(/^\s*0*(\d{1,3})/);
    return mnum ? `${tipo} ${parseInt(mnum[1], 10)}` : tipo;
  }

  function extraerCoordenadas(tokensEntrada) {
    let tokens = Array.isArray(tokensEntrada) ? tokensEntrada : tokensEntrada.split("\n");
    tokens = tokens.map((t) => t.trim()).filter(Boolean);
    const full = tokens.join(" ");
    const up = full.toUpperCase();

    const res = { X: "", Y: "", COTA: "", ABS: "" };

    const etiquetasE = new Set(["E", "E:", "ESTE", "ESTE:"]);
    const etiquetasN = new Set(["N", "N:", "NORTE", "NORTE:"]);

    for (let i = 0; i < tokens.length; i++) {
      const tu = tokens[i].toUpperCase().trim();

      const me = tu.match(/^E[\s:.\-]+([+-]?\d[\d.,\s]*)$/);
      if (me && !res.X) {
        res.X = numLimpio(me[1]) || "";
      } else if (etiquetasE.has(tu) && !res.X && i + 1 < tokens.length) {
        res.X = numLimpio(tokens[i + 1]) || "";
      }

      const mn = tu.match(/^N[\s:.\-]+([+-]?\d[\d.,\s]*)$/);
      if (mn && !res.Y) {
        res.Y = numLimpio(mn[1]) || "";
      } else if (etiquetasN.has(tu) && !res.Y && i + 1 < tokens.length) {
        res.Y = numLimpio(tokens[i + 1]) || "";
      }
    }

    if (!res.X || !res.Y) {
      const crudos = full.match(/\d[\d\s.,]*\d/g) || [];
      for (const crudo of crudos) {
        const c = numLimpio(crudo);
        if (!c) continue;
        const entero = c.split(".")[0].replace(/^[+-]/, "");
        if (!res.Y && entero.length === 7 && entero.startsWith("9")) {
          res.Y = c;
        } else if (!res.X && entero.length === 6) {
          res.X = c;
        }
      }
    }

    const mc = up.match(/(?:ELEVACI[ÓO]N|ELEV|COTA)[^\d+-]{0,6}([+-]?\d+(?:[.,]\d+)?)/);
    if (mc) res.COTA = numLimpio(mc[1]);

    let ma = up.match(/EST[\s:.]*K\s*([+-]?\s*0\s*[+-]\s*\d+(?:[.,]\d+)?)/);
    if (!ma) ma = up.match(/K\s*([+-]?\s*0\s*[+-]\s*\d+(?:[.,]\d+)?)/);
    if (ma) res.ABS = procesarAbs(ma[1]);

    for (const k of ["X", "Y", "COTA"]) res[k] = truncar2(res[k]);

    return res;
  }

  function parsear(tokens) {
    const texto = Array.isArray(tokens) ? tokens.join("\n") : tokens;
    const coords = extraerCoordenadas(tokens);
    return {
      Ensayo: extraerEnsayo(texto),
      X: coords.X,
      Y: coords.Y,
      COTA: coords.COTA,
      ABS: coords.ABS,
    };
  }

  const COLUMNAS = ["Ensayo", "X", "Y", "COTA", "ABS"];

  global.TopoParser = {
    COLUMNAS,
    truncar2,
    numLimpio,
    procesarAbs,
    extraerEnsayo,
    extraerCoordenadas,
    parsear,
  };
})(window);
