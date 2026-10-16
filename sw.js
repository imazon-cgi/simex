/* sw.js — cache dos dados do SIMEX.
   O dashboard lê a exploração do banco (/api/simex) e, quando ele não
   responde, dos arquivos do S3. Nada é pré-baixado: só o GeoJSON de imóveis
   rurais do S3 passa de 100 MB, e ele é reserva, não a fonte do dia a dia. */
const CACHE = 'simex-dados-v3';

// Respostas curtas (banco, dataset local, tiles): responde do cache e
// revalida em segundo plano. Em produção o app fica sob /simex/. Os downloads
// (/api/simex/download) ficam de fora: são arquivos grandes, gerados na hora.
const SWR_PATHS = [
  /^https?:\/\/[^\/]+(\/simex)?\/api\/simex\/(?!download\/)/,
  /^https?:\/\/[^\/]+(\/simex)?\/dataset\//,
  /^https?:\/\/[a-d]\.basemaps\.cartocdn\.com\//,
  /^https?:\/\/.*tile\.openstreetmap\.org\//
];

// Arquivos do S3: republicados com o mesmo nome, então a rede vem primeiro e o
// cache só entra quando ela falha.
const S3_PATH = /^https?:\/\/imazongeo3-web\.s3(\.[a-z0-9-]+)?\.amazonaws\.com\/dashboard\/simex\//;

self.addEventListener('install', () => self.skipWaiting());

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const chaves = await caches.keys();
    await Promise.all(chaves.filter(k => k !== CACHE).map(k => caches.delete(k)));
    await self.clients.claim();
  })());
});

async function staleWhileRevalidate(req) {
  const cache = await caches.open(CACHE);
  const cached = await cache.match(req, { ignoreVary: true });
  const rede = fetch(req).then(res => {
    if (res.ok) cache.put(req, res.clone());
    return res;
  }).catch(() => cached || Response.error());
  return cached || rede;
}

async function networkFirst(req) {
  const cache = await caches.open(CACHE);
  try {
    const res = await fetch(new Request(req, { cache: 'no-store' }));
    if (res.ok) cache.put(req, res.clone());
    return res;
  } catch (err) {
    return (await cache.match(req, { ignoreVary: true })) || Response.error();
  }
}

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  if (SWR_PATHS.some(rx => rx.test(req.url))) return event.respondWith(staleWhileRevalidate(req));
  if (S3_PATH.test(req.url)) return event.respondWith(networkFirst(req));
});
