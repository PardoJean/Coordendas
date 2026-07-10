/**
 * test_parser_js.js
 * Pruebas de docs/js/parser.js y docs/js/geo.js (versión 100% navegador),
 * con los mismos casos que tests/test_topo_parser.py para mantener ambas
 * implementaciones en sincronía. Correr con: node tests/test_parser_js.js
 */
"use strict";
const path = require("path");

global.window = global;
require(path.join(__dirname, "..", "docs", "js", "parser.js"));
require(path.join(__dirname, "..", "docs", "js", "geo.js"));

const { parsear, truncar2, procesarAbs, extraerEnsayo, extraerCoordenadas } = global.TopoParser;
const { utmALatLon } = global.TopoGeo;

let todoOk = true;
function check(nombre, got, esperado) {
  const pasa = JSON.stringify(got) === JSON.stringify(esperado);
  console.log((pasa ? "OK  " : "FALLA"), nombre, "esperado=", JSON.stringify(esperado), "obtenido=", JSON.stringify(got));
  if (!pasa) todoOk = false;
}

console.log("== Capturas (tokens tal como los devuelve el OCR) ==");
const TOKENS_1 = ["Líneas", "eje 905", "1.250", "Nombre", "-218.161", "Código", "DCP 1",
  "Dist:1181.302m", "Est:K-0+218.161", "Cruz: -1181.302m", "Relleno: 118.285m", "Elev.: 786.715m",
  "N", "9603591.641", "Elevación", "786.715", "E", "780720.633", "Distancia 2D", "0.035",
  "Distancia base", "685.889", "Elev.", "0.012"];
check("Captura 1 (DCP 1)", parsear(TOKENS_1),
  { Ensayo: "DCP 1", X: "780720.63", Y: "9603591.64", COTA: "786.71", ABS: "-218.16" });

const TOKENS_2 = ["Líneas", "EJE 905", "1.250", "Nombre", "0.000", "Código", "VDC 4",
  "Dist:889.772m", "Est:K-0+154.895", "Cruz: -876.186m", "Relleno: 79.613m", "Elev.: 825.387m",
  "N", "9603295.217", "Distancia 2D", "0.010", "E", "780816.712", "Elevación", "825.387",
  "Distancia base", "667.181"];
check("Captura 2 (VDC 4)", parsear(TOKENS_2),
  { Ensayo: "VDC 4", X: "780816.71", Y: "9603295.21", COTA: "825.38", ABS: "-154.89" });

console.log("\n== Ensayo con ruido de OCR ==");
const casosEnsayo = [
  ["Código > P0Z0 1", "POZO 1"],
  ["Código > POZ0 1", "POZO 1"],
  ["Código: Voc 4", "VDC 4"],
  ["NTC 0.000 (LPH VCD3 Y", "VDC 3"], // OCR transpuso C y D (VCD en vez de VDC)
  ["C6digo > POZO1", "POZO 1"],
  ["Codigo > DOP 3", "DCP 3"],
  ["sin ningun codigo reconocible aqui", "SIN CLASIFICAR"],
  ["Nombre 0.000 (MA VDCS9 Y", "VDC 9"], // ruido entre el tipo y el número ("S" espuria)
];
for (const [texto, esperado] of casosEnsayo) {
  check(JSON.stringify(texto), extraerEnsayo(texto), esperado);
}

console.log("\n== Coordenadas con ruido de OCR (etiqueta E/N espuria) ==");
const TOKENS_RUIDO = [
  "H:0,011", "e", "H:0,011", "N", "12", "algo de relleno",
  "N", "9111111.11", "algo mas", "E", "711111.11",
];
const coordsRuido = extraerCoordenadas(TOKENS_RUIDO);
check("X (ignora la 'e' espuria)", coordsRuido.X, "711111.11");
check("Y (ignora la 'N' de un número corto)", coordsRuido.Y, "9111111.11");

console.log("\n== Reglas unitarias ==");
check("truncar 786.719", truncar2("786.719"), "786.71");
check("truncar -218.169", truncar2("-218.169"), "-218.16");
check("abs K-0+218.161", procesarAbs("K-0+218.161"), "-218.16");
check("abs K0+154.895", procesarAbs("K0+154.895"), "154.89");
check("abs con espacios", procesarAbs("K - 0 + 99.999"), "-99.99");

console.log("\n== ABS con ruido de OCR (tokens dañados reales) ==");
check('E5t: K-0+218.161', extraerCoordenadas(['E5t: K-0+218.161']).ABS, '-218.16');
check('Est/K separado', extraerCoordenadas(['algo', 'Est', 'K', '-0+', '218.161', 'mas']).ABS, '-218.16');
check('E5t + numero directo', extraerCoordenadas(['E5t:', '-218.161']).ABS, '-218.16');
check('Est:< -0+ 154.895', extraerCoordenadas(['Est:< -0+ 154.895']).ABS, '-154.89');
check('E5T: K0+ 40.883', extraerCoordenadas(['E5T: K0+ 40.883']).ABS, '40.88');
check('K1+177.600 (km>0)', extraerCoordenadas(['Dist:1249.300m Est:K1+177.600']).ABS, '1177.60');
check('K0+381.265 (km=0 sin regresión)', extraerCoordenadas(['Dist:1303.502m Est:K0+381.265']).ABS, '381.26');

console.log("\n== Conversión UTM -> lat/lon (PSAD56, zona 17 Sur) ==");
const geoPsad = utmALatLon("780816.71", "9603295.21", { zona: 17, datum: "PSAD56" });
const geoWgs = utmALatLon("780816.71", "9603295.21", { zona: 17, datum: "WGS84" });
check("PSAD56 lat cerca de -3.5889", Math.abs(geoPsad.lat - -3.5889) < 0.001, true);
check("PSAD56 y WGS84 difieren (hay cambio de datum)", Math.abs(geoPsad.lat - geoWgs.lat) > 1e-4, true);
check("vacío -> null", utmALatLon("", "9603295.21"), null);
check("texto -> null", utmALatLon("abc", "xyz"), null);

console.log(todoOk ? "\nTODOS LOS TESTS JS PASARON" : "\nHAY FALLAS");
process.exit(todoOk ? 0 : 1);
