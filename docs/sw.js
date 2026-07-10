/**
 * sw.js — Service Worker
 * Guarda en caché toda la app (HTML/CSS/JS, el motor de OCR y los datos de
 * idioma) la primera vez que se visita, para que funcione sin internet las
 * siguientes veces. Estrategia: cache-first con red de respaldo.
 */
const CACHE = "topo-v1";

const ARCHIVOS_PRECACHE = [
  "./",
  "./index.html",
  "./manifest.json",
  "./css/style.css",
  "./js/parser.js",
  "./js/geo.js",
  "./js/ocr.js",
  "./js/app.js",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
  "./vendor/leaflet/leaflet.js",
  "./vendor/leaflet/leaflet.css",
  "./vendor/tesseract/tesseract.min.js",
  "./vendor/tesseract/worker.min.js",
  "./vendor/tesseract/tesseract-core-simd-lstm.js",
  "./vendor/tesseract/tesseract-core-simd-lstm.wasm.js",
  "./vendor/tesseract/tesseract-core-simd-lstm.wasm",
  "./vendor/tesseract/tesseract-core-lstm.js",
  "./vendor/tesseract/tesseract-core-lstm.wasm.js",
  "./vendor/tesseract/tesseract-core-lstm.wasm",
  "./tessdata/eng.traineddata.gz",
  "./tessdata/spa.traineddata.gz",
];

self.addEventListener("install", (evento) => {
  evento.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(ARCHIVOS_PRECACHE)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (evento) => {
  evento.waitUntil(
    caches
      .keys()
      .then((nombres) => Promise.all(nombres.filter((n) => n !== CACHE).map((n) => caches.delete(n))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (evento) => {
  if (evento.request.method !== "GET") return;
  // Los tiles del mapa (openstreetmap.org) siempre van directo a la red:
  // no tiene sentido cachearlos (son miles de imágenes distintas).
  if (evento.request.url.includes("tile.openstreetmap.org")) return;

  evento.respondWith(
    caches.match(evento.request).then((respuestaCache) => {
      if (respuestaCache) return respuestaCache;
      return fetch(evento.request)
        .then((respuestaRed) => {
          if (respuestaRed && respuestaRed.status === 200 && (respuestaRed.type === "basic" || respuestaRed.type === "cors")) {
            const copia = respuestaRed.clone();
            caches.open(CACHE).then((cache) => cache.put(evento.request, copia));
          }
          return respuestaRed;
        })
        .catch(() => caches.match("./index.html"));
    })
  );
});
