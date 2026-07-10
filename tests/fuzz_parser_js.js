/**
 * fuzz_parser_js.js
 * Misma prueba de robustez por mutación que tests/fuzz_parser.py, para
 * docs/js/parser.js (versión del navegador). Ver ese archivo para la
 * explicación completa del enfoque.
 *
 * Uso: node tests/fuzz_parser_js.js [trials] [seed]
 */
"use strict";
const path = require("path");

global.window = global;
require(path.join(__dirname, "..", "docs", "js", "parser.js"));
const { parsear } = global.TopoParser;

// ---- PRNG determinista (mismo algoritmo simple en todo el fuzzer, para
// que --seed sea reproducible sin depender de librerías externas) ----
function crearRng(semilla) {
  let s = semilla >>> 0;
  return function () {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
}
function randInt(rng, min, max) {
  return min + Math.floor(rng() * (max - min + 1));
}
function eleccion(rng, arr) {
  return arr[Math.floor(rng() * arr.length)];
}

const CASOS_DORADOS = [
  ["Captura 1 (DCP 1)", [
    "Líneas", "eje 905", "1.250", "Nombre", "-218.161", "Código", "DCP 1",
    "Dist:1181.302m", "Est:K-0+218.161", "Cruz: -1181.302m", "Relleno: 118.285m",
    "Elev.: 786.715m", "N", "9603591.641", "Elevación", "786.715", "E", "780720.633",
    "Distancia 2D", "0.035", "Distancia base", "685.889", "Elev.", "0.012",
  ], { Ensayo: "DCP 1", X: "780720.63", Y: "9603591.64", COTA: "786.71", ABS: "-218.16" }],

  ["Captura 2 (VDC 4)", [
    "Líneas", "EJE 905", "1.250", "Nombre", "0.000", "Código", "VDC 4",
    "Dist:889.772m", "Est:K-0+154.895", "Cruz: -876.186m", "Relleno: 79.613m",
    "Elev.: 825.387m", "N", "9603295.217", "Distancia 2D", "0.010", "E", "780816.712",
    "Elevación", "825.387", "Distancia base", "667.181",
  ], { Ensayo: "VDC 4", X: "780816.71", Y: "9603295.21", COTA: "825.38", ABS: "-154.89" }],

  ["Captura 3 (POZO 1)", [
    "Líneas", "EJE 905", "1.250", "Nombre", "0.000", "Código", "POZO 1",
    "Dist:960.203m", "Est:K-0+155.907", "Cruz: -947.461m", "Relleno: 83.001m",
    "En: -155.907m", "Elev.: 821.999m", "N", "9603365.959", "Distancia 2D", "0.005",
    "E", "780807.953", "Elevación", "821.999", "Distancia base", "645.261",
  ], { Ensayo: "POZO 1", X: "780807.95", Y: "9603365.95", COTA: "821.99", ABS: "-155.90" }],
];

const TOKENS_BASURA_ICONO = ["AR", "LJ", "«", "»", "O", "o", "A", "a", ".", "-", "()", "[]", "?", "*"];
const LETRAS_ETIQUETA_ESPURIA = ["e", "E", "n", "N"];
const ETIQUETAS_REALES = new Set(["E", "N", "E:", "N:", "ESTE", "NORTE", "ESTE:", "NORTE:"]);

function insertar(t, indice, token) {
  t.splice(Math.max(0, Math.min(indice, t.length)), 0, token);
}

function mutar(tokens, rng) {
  const t = tokens.slice();

  for (let k = 0; k < randInt(rng, 1, 3); k++) {
    insertar(t, randInt(rng, 0, t.length), eleccion(rng, TOKENS_BASURA_ICONO));
  }

  if (rng() < 0.6) {
    const posicionesValidas = [];
    for (let p = 0; p <= t.length; p++) {
      const antes = p === 0 || !ETIQUETAS_REALES.has(t[p - 1].toUpperCase().trim());
      const despues = p === t.length || !ETIQUETAS_REALES.has(t[p].toUpperCase().trim());
      if (antes && despues) posicionesValidas.push(p);
    }
    if (posicionesValidas.length) {
      const pos = eleccion(rng, posicionesValidas);
      insertar(t, pos, String(randInt(rng, 0, 9999)));
      insertar(t, pos, eleccion(rng, LETRAS_ETIQUETA_ESPURIA));
    }
  }

  for (let i = 0; i < t.length; i++) {
    if (t[i] === "Código" && i + 1 < t.length) {
      const partes = t[i + 1].split(" ");
      if (partes.length === 2 && rng() < 0.7) {
        const ruido = eleccion(rng, ["·", "S", "|", "_", "»"]).repeat(randInt(rng, 1, 2));
        t[i + 1] = `${partes[0]}${ruido}${partes[1]}`;
      }
      break;
    }
  }

  return t;
}

function esFallaSegura(esperado, obtenido) {
  for (const campo of Object.keys(esperado)) {
    const valObtenido = obtenido[campo];
    if (valObtenido !== esperado[campo] && valObtenido !== "" && valObtenido !== "SIN CLASIFICAR") {
      return false;
    }
  }
  return true;
}

function main() {
  const trials = parseInt(process.argv[2], 10) || 500;
  const semilla = parseInt(process.argv[3], 10) || 42;
  const rng = crearRng(semilla);

  let total = 0;
  let fallasSeguras = 0;
  const fallasInseguras = [];

  for (const [nombre, tokens, esperado] of CASOS_DORADOS) {
    for (let prueba = 0; prueba < trials; prueba++) {
      total++;
      const mutados = mutar(tokens, rng);
      const resultado = parsear(mutados);
      const igual = JSON.stringify(resultado) === JSON.stringify(esperado);
      if (igual) continue;
      if (esFallaSegura(esperado, resultado)) {
        fallasSeguras++;
      } else {
        fallasInseguras.push({ nombre, prueba, mutados, esperado, resultado });
        if (fallasInseguras.length >= 20) break;
      }
    }
  }

  console.log(`Casos dorados: ${CASOS_DORADOS.length} · Mutaciones por caso: ${trials} · Total: ${total}`);
  console.log(`Fallas seguras (campo vacío, sin dato equivocado): ${fallasSeguras}`);

  if (fallasInseguras.length === 0) {
    console.log("SIN FALLAS INSEGURAS: ninguna mutación insertó un valor incorrecto sin avisar.");
    process.exit(0);
  }

  console.log(`\n${fallasInseguras.length} FALLA(S) INSEGURA(S) (mostrando hasta 20):\n`);
  for (const f of fallasInseguras) {
    console.log(`-- ${f.nombre} (mutación #${f.prueba}) --`);
    console.log(`  tokens: ${JSON.stringify(f.mutados)}`);
    console.log(`  esperado: ${JSON.stringify(f.esperado)}`);
    console.log(`  obtenido: ${JSON.stringify(f.resultado)}\n`);
  }
  process.exit(1);
}

main();
