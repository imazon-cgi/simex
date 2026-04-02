/* Service Worker para cache dos datasets SIMEX */
const CACHE_NAME = 'simex-datasets-v1';

// Arquivos a serem pré-carregados no cache (CSV e GeoJSON)
const S3_BASE = 'https://imazongeo3-web.s3.amazonaws.com/dashboard/simex';
const PRECACHE_URLS = [
  `${S3_BASE}/geojson/simex_amazonia_PAMT_limite_municipios_amz_legal.geojson`,
  `${S3_BASE}/geojson/simex_amazonia_PAMT_assentamentos.geojson`,
  `${S3_BASE}/csv/simex_amazonia_PAMT_assentamentos.csv`,
  `${S3_BASE}/geojson/simex_amazonia_PAMT_imoveisrurais.geojson`,
  `${S3_BASE}/csv/simex_amazonia_PAMT_imoveisrurais.csv`,
  `${S3_BASE}/geojson/simex_amazonia_PAMT_mun.geojson`,
  `${S3_BASE}/csv/simex_amazonia_PAMT_municipios.csv`,
  `${S3_BASE}/geojson/simex_amazonia_PAMT_TI.geojson`,
  `${S3_BASE}/csv/simex_amazonia_PAMT_TI.csv`,
  `${S3_BASE}/geojson/simex_amazonia_PAMT_TerrasNDest.geojson`,
  `${S3_BASE}/csv/simex_amazonia_PAMT_TerrasNDest.csv`,
  `${S3_BASE}/geojson/simex_amazonia_PAMT_UC.geojson`,
  `${S3_BASE}/csv/simex_amazonia_PAMT_UC.csv`,
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
    const isS3 = url.origin === 'https://imazongeo3-web.s3.amazonaws.com' &&
                 url.pathname.startsWith('/dashboard/simex/');
    return request.method === 'GET' && isS3;
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

