/* Service Worker para cache dos datasets SIMEX */
const CACHE_NAME = 'simex-datasets-v2';
const S3_ORIGINS = new Set([
  'https://imazongeo3-web.s3.amazonaws.com',
  'https://imazongeo3-web.s3.sa-east-1.amazonaws.com',
]);

// Arquivos a serem pré-carregados no cache (CSV e GeoJSON)
const S3_BASE = 'https://imazongeo3-web.s3.amazonaws.com/dashboard/simex';
const PRECACHE_URLS = [
  `${S3_BASE}/geojson/simex_amz_PAMTM_limite_municipios_amz_legal.geojson`,
  `${S3_BASE}/geojson/simex_amz_PAMTM_assentamentos.geojson`,
  `${S3_BASE}/csv/simex_amazonia_PAMT_assentamentos.csv`,
  `${S3_BASE}/geojson/simex_amz_PAMTM_imoveisrurais.geojson`,
  `${S3_BASE}/csv/simex_amazonia_PAMT_imoveisrurais.csv`,
  `${S3_BASE}/geojson/simex_amz_PAMTM_mun.geojson`,
  `${S3_BASE}/csv/simex_amazonia_PAMT_municipios.csv`,
  `${S3_BASE}/geojson/simex_amz_PAMTM_TI.geojson`,
  `${S3_BASE}/csv/simex_amazonia_PAMT_ti.csv`,
  `${S3_BASE}/geojson/simex_amz_PAMTM_TerrasNDest.geojson`,
  `${S3_BASE}/csv/simex_amazonia_PAMT_terras_ndest.csv`,
  `${S3_BASE}/geojson/simex_amz_PAMTM_UC.geojson`,
  `${S3_BASE}/csv/simex_amazonia_PAMT_uc.csv`,
];

self.addEventListener('install', (event) => {
  self.skipWaiting();
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE_NAME);
    const results = await Promise.allSettled(PRECACHE_URLS.map((url) => cache.add(url)));
    const failed = results.filter((result) => result.status === 'rejected');
    if (failed.length) {
      console.warn(`[SW] Pré-cache parcial: ${PRECACHE_URLS.length - failed.length}/${PRECACHE_URLS.length} arquivos.`);
    }
  })());
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
    const isS3 = S3_ORIGINS.has(url.origin) && url.pathname.startsWith('/dashboard/simex/');
    return request.method === 'GET' && isS3;
  } catch (e) {
    return false;
  }
}

// Estratégia: Network-First com fallback em cache para evitar exibir CSV antigo
self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (!shouldHandle(req)) return;

  event.respondWith(
    (async () => {
      try {
        const networkReq = new Request(req, { cache: 'no-store' });
        const res = await fetch(networkReq);
        if (res && res.status === 200) {
          const cache = await caches.open(CACHE_NAME);
          cache.put(req, res.clone());
        }
        return res;
      } catch (err) {
        const cached = await caches.match(req);
        return cached || Response.error();
      }
    })()
  );
});
