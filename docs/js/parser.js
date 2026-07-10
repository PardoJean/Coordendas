/**
 * parser.js
 * Puerto directo de topo_parser.py (lógica de extracción de datos
 * topográficos a partir del texto OCR). Reglas de negocio idénticas a la
 * versión Python: mismo Ensayo, X, Y, COTA y ABS para el mismo texto OCR.
 */
(function (global) {
  "use strict";

  const TIPOS = ["POZO", "VDC", "DCP", "TIS", "DCA"];
  const TIPOS_ORDEN = { POZO: 1, VDC: 2, DCP: 3, TIS: 4, DCA: 5 };

  const SIMBOLOGIA = {
    POZO: { color: [220, 38, 38], radio: 8, marcador: "circle" },
    VDC:  { color: [37, 99, 235], radio: 7, marcador: "triangle" },
    DCP:  { color: [22, 163, 74], radio: 6, marcador: "square" },
    TIS:  { color: [202, 138, 4], radio: 7, marcador: "diamond" },
    DCA:  { color: [147, 51, 234], radio: 8, marcador: "cross" },
  };
  const SIMBOLOGIA_SIN = { color: [107, 114, 128], radio: 6, marcador: "hollow" };

  function extraerTipoNumero(ensayo) {
    if (!ensayo) return ["SIN CLASIFICAR", 0];
    const m = ensayo.trim().match(/^([A-Za-z]+)\s*(\d*)/);
    if (m) {
      const tipo = m[1].toUpperCase();
      const num = parseInt(m[2], 10) || 0;
      return [tipo, num];
    }
    return ["SIN CLASIFICAR", 0];
  }

  function ordenarRegistros(registros) {
    return [...registros].sort((a, b) => {
      const [tipoA, numA] = extraerTipoNumero(a.Ensayo);
      const [tipoB, numB] = extraerTipoNumero(b.Ensayo);
      const priA = TIPOS_ORDEN[tipoA] !== undefined ? TIPOS_ORDEN[tipoA] : 99;
      const priB = TIPOS_ORDEN[tipoB] !== undefined ? TIPOS_ORDEN[tipoB] : 99;
      if (priA !== priB) return priA - priB;
      return numA - numB;
    });
  }

  function simbologiaPara(ensayo) {
    const [tipo] = extraerTipoNumero(ensayo);
    return SIMBOLOGIA[tipo] || SIMBOLOGIA_SIN;
  }

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
    // Tolera 1-3 caracteres de ruido de OCR entre el tipo y el número
    // (ej. "VDCS5" -> el OCR mete una "S" espuria entre "VDC" y "5").
    const mnum = resto.match(/^[^\d]{0,3}0*(\d{1,3})/);
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

    // Una "E" o "N" sueltas de un solo caracter son un imán para ruido de
    // OCR (iconos, letras mal leídas de otra parte de la pantalla). Antes
    // de aceptar el número que las sigue como coordenada, exigimos que
    // tenga pinta de UTM real (parte entera larga); si no, se ignora y se
    // sigue buscando una coincidencia mejor más adelante en el texto.
    function pareceCoordenadaUtm(valor) {
      if (!valor) return false;
      const entero = valor.split(".")[0].replace(/^[+-]/, "");
      return entero.length >= 5;
    }

    for (let i = 0; i < tokens.length; i++) {
      const tu = tokens[i].toUpperCase().trim();

      const me = tu.match(/^E[\s:.\-]+([+-]?\d[\d.,\s]*)$/);
      if (me && !res.X) {
        res.X = numLimpio(me[1]) || "";
      } else if (etiquetasE.has(tu) && !res.X && i + 1 < tokens.length) {
        const candidato = numLimpio(tokens[i + 1]) || "";
        if (pareceCoordenadaUtm(candidato)) res.X = candidato;
      }

      const mn = tu.match(/^N[\s:.\-]+([+-]?\d[\d.,\s]*)$/);
      if (mn && !res.Y) {
        res.Y = numLimpio(mn[1]) || "";
      } else if (etiquetasN.has(tu) && !res.Y && i + 1 < tokens.length) {
        const candidato = numLimpio(tokens[i + 1]) || "";
        if (pareceCoordenadaUtm(candidato)) res.Y = candidato;
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
    TIPOS,
    TIPOS_ORDEN,
    SIMBOLOGIA,
    truncar2,
    numLimpio,
    procesarAbs,
    extraerEnsayo,
    extraerCoordenadas,
    parsear,
    extraerTipoNumero,
    ordenarRegistros,
    simbologiaPara,
  };
})(window);
