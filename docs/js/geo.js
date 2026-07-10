/**
 * geo.js
 * Convierte coordenadas UTM (Este=X, Norte=Y) a latitud/longitud WGS84 para
 * ubicar los puntos en el mapa. Implementación propia (sin depender de
 * ninguna librería externa de proyecciones), en dos pasos:
 *
 *   1. Transversa de Mercator inversa (fórmulas de Krüger) sobre el
 *      elipsoide de origen -> lat/lon en el datum de origen.
 *   2. Traslación geocéntrica (X,Y,Z) de 3 parámetros -> lat/lon en WGS84.
 *
 * Las capturas de topografía en Ecuador vienen en PSAD56 (datum sudamericano
 * provisional 1956), que difiere de WGS84 en varios cientos de metros si no
 * se aplica el cambio de datum -> por eso el paso 2 es imprescindible.
 */
(function (global) {
  "use strict";

  const ELIPSOIDES = {
    // International 1924 (usado por PSAD56)
    intl1924: { a: 6378388.0, f: 1 / 297.0 },
    // WGS84
    wgs84: { a: 6378137.0, f: 1 / 298.257223563 },
  };

  // Traslación geocéntrica PSAD56 -> WGS84 (EPSG, método "Geocentric
  // translations"), parámetros para Sudamérica: dX=-288, dY=175, dZ=-376 m.
  const DATUM_SHIFT = { PSAD56: { dX: -288, dY: 175, dZ: -376 }, WGS84: { dX: 0, dY: 0, dZ: 0 } };
  const ELIPSOIDE_POR_DATUM = { PSAD56: "intl1924", WGS84: "wgs84" };

  function utmInverso(este, norte, huso, hemisferioNorte, elipsoide, k0) {
    k0 = k0 || 0.9996;
    const { a, f } = elipsoide;
    const e2 = f * (2 - f);
    const ep2 = e2 / (1 - e2);
    const lon0 = ((-183 + huso * 6) * Math.PI) / 180;
    const x = este - 500000.0;
    const y = hemisferioNorte ? norte : norte - 10000000.0;
    const M = y / k0;
    const mu = M / (a * (1 - e2 / 4 - (3 * e2 ** 2) / 64 - (5 * e2 ** 3) / 256));
    const e1 = (1 - Math.sqrt(1 - e2)) / (1 + Math.sqrt(1 - e2));
    const phi1 =
      mu +
      ((3 * e1) / 2 - (27 * e1 ** 3) / 32) * Math.sin(2 * mu) +
      ((21 * e1 ** 2) / 16 - (55 * e1 ** 4) / 32) * Math.sin(4 * mu) +
      ((151 * e1 ** 3) / 96) * Math.sin(6 * mu) +
      ((1097 * e1 ** 4) / 512) * Math.sin(8 * mu);
    const N1 = a / Math.sqrt(1 - e2 * Math.sin(phi1) ** 2);
    const T1 = Math.tan(phi1) ** 2;
    const C1 = ep2 * Math.cos(phi1) ** 2;
    const R1 = (a * (1 - e2)) / (1 - e2 * Math.sin(phi1) ** 2) ** 1.5;
    const D = x / (N1 * k0);

    const phi =
      phi1 -
      ((N1 * Math.tan(phi1)) / R1) *
        (D ** 2 / 2 -
          ((5 + 3 * T1 + 10 * C1 - 4 * C1 ** 2 - 9 * ep2) * D ** 4) / 24 +
          ((61 + 90 * T1 + 298 * C1 + 45 * T1 ** 2 - 252 * ep2 - 3 * C1 ** 2) * D ** 6) / 720);

    const lon =
      lon0 +
      (D -
        ((1 + 2 * T1 + C1) * D ** 3) / 6 +
        ((5 - 2 * C1 + 28 * T1 - 3 * C1 ** 2 + 8 * ep2 + 24 * T1 ** 2) * D ** 5) / 120) /
        Math.cos(phi1);

    return { lat: (phi * 180) / Math.PI, lon: (lon * 180) / Math.PI };
  }

  function geodesicoAGeocentrico(latDeg, lonDeg, h, elipsoide) {
    const { a, f } = elipsoide;
    const e2 = f * (2 - f);
    const lat = (latDeg * Math.PI) / 180;
    const lon = (lonDeg * Math.PI) / 180;
    const N = a / Math.sqrt(1 - e2 * Math.sin(lat) ** 2);
    return {
      X: (N + h) * Math.cos(lat) * Math.cos(lon),
      Y: (N + h) * Math.cos(lat) * Math.sin(lon),
      Z: (N * (1 - e2) + h) * Math.sin(lat),
    };
  }

  function geocentricoAGeodesico(X, Y, Z, elipsoide) {
    const { a, f } = elipsoide;
    const e2 = f * (2 - f);
    const b = a * (1 - f);
    const ep2 = (a * a - b * b) / (b * b);
    const p = Math.sqrt(X * X + Y * Y);
    const theta = Math.atan2(Z * a, p * b);
    const lon = Math.atan2(Y, X);
    const lat = Math.atan2(
      Z + ep2 * b * Math.sin(theta) ** 3,
      p - e2 * a * Math.cos(theta) ** 3
    );
    return { lat: (lat * 180) / Math.PI, lon: (lon * 180) / Math.PI };
  }

  /**
   * Convierte una coordenada UTM (Este=X, Norte=Y) a {lat, lon} en WGS84.
   * Devuelve null si los valores no son numéricos o son cero/vacíos.
   */
  function utmALatLon(este, norte, opciones) {
    opciones = opciones || {};
    const zona = opciones.zona || 17;
    const hemisferioNorte = !!opciones.hemisferioNorte;
    const datum = (opciones.datum || "PSAD56").toUpperCase();

    const e = parseFloat(String(este).replace(/\s/g, "").replace(",", "."));
    const n = parseFloat(String(norte).replace(/\s/g, "").replace(",", "."));
    if (!Number.isFinite(e) || !Number.isFinite(n) || e === 0 || n === 0) return null;

    const nombreElipsoide = ELIPSOIDE_POR_DATUM[datum] || "intl1924";
    const elipsoideOrigen = ELIPSOIDES[nombreElipsoide];
    const { lat: latOrigen, lon: lonOrigen } = utmInverso(e, n, zona, hemisferioNorte, elipsoideOrigen);

    const shift = DATUM_SHIFT[datum] || DATUM_SHIFT.PSAD56;
    if (shift.dX === 0 && shift.dY === 0 && shift.dZ === 0) {
      return { lat: latOrigen, lon: lonOrigen };
    }

    const { X, Y, Z } = geodesicoAGeocentrico(latOrigen, lonOrigen, 0, elipsoideOrigen);
    const resultado = geocentricoAGeodesico(X + shift.dX, Y + shift.dY, Z + shift.dZ, ELIPSOIDES.wgs84);
    if (Number.isNaN(resultado.lat) || Number.isNaN(resultado.lon)) return null;
    return resultado;
  }

  global.TopoGeo = { utmALatLon, DATUMS: Object.keys(DATUM_SHIFT) };
})(window);
