/* Service Worker para cache dos datasets SIMEX */
const CACHE_NAME = 'simex-datasets-v1';

// Arquivos a serem pré-carregados no cache (CSV e GeoJSON)
const PRECACHE_URLS = [
  '/dataset/AMZ_legal_amz_legal.geojson',
  '/dataset/simex/geojson/simex_amazonia_PAMT2007_2023_assentamentos.geojson',
  '/dataset/simex/csv/simex_amazonia_PAMT2007_2023_assentamentos.csv',
  '/dataset/simex/geojson/simex_amazonia_PAMT2007_2023_imoveisrurais.geojson',
  '/dataset/simex/csv/simex_amazonia_PAMT2007_2023_imoveisrurais.csv',
  '/dataset/simex/geojson/simex_amazonia_PAMT2007_2023_mun.geojson',
  '/dataset/simex/csv/simex_amazonia_PAMT2007_2023_municipios.csv',
  '/dataset/simex/geojson/simex_amazonia_PAMT2007_2023_TI.geojson',
  '/dataset/simex/csv/simex_amazonia_PAMT2007_2023_TI.csv',
  '/dataset/simex/geojson/simex_amazonia_PAMT2007_2023_TerrasNDest.geojson',
  '/dataset/simex/csv/simex_amazonia_PAMT2007_2023_TerrasNDest.csv',
  '/dataset/simex/geojson/simex_amazonia_PAMT2007_2023_UC.geojson',
  '/dataset/simex/csv/simex_amazonia_PAMT2007_2023_UC.csv',
];

self.addEventListener('install', (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE_URLS))
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
      )
      .then(() => self.clients.claim())
  );
});

function shouldHandle(request) {
  try {
    const url = new URL(request.url);
    return (
      request.method === 'GET' &&
      url.origin === self.location.origin &&
      url.pathname.startsWith('/dataset/')
    );
  } catch (e) {
    return false;
  }
}

// Estratégia: Stale-While-Revalidate para os datasets
self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (!shouldHandle(req)) return;

  event.respondWith(
    caches.match(req).then((cached) => {
      const networkFetch = fetch(req)
        .then((res) => {
          if (res && res.status === 200) {
            const clone = res.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(req, clone));
          }
          return res;
        })
        .catch(() => cached);

      return cached || networkFetch;
    })
  );
});

