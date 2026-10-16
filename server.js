// server.js (Linux-ready)
// Executar: NODE_ENV=production node server.js
// Variáveis opcionais:
//   PORT=3000
//   DATASET_DIR=/caminho/absoluto/para/dataset
//   TRUST_PROXY=1                (se estiver atrás de Nginx/Apache/ALB/ELB/Cloudflare)
//   CSP_REPORT_ONLY=1            (CSP em modo "report only")
//   DATABASE_URL=...             (banco do imazongeo_upload; sem ela, só S3)

const path = require('path');
require('dotenv').config({ path: path.join(__dirname, '.env'), quiet: true });
const fs = require('fs');
const os = require('os');
const { execFile } = require('child_process');
const { promisify } = require('util');
const express = require('express');
const compression = require('compression');
const helmet = require('helmet');
const {
  csvSimex, geojsonSimex, periodoSimex, linhasDownloadSimex, csvDownloadSimex, CAMPOS_DOWNLOAD,
  bancoConfigurado, SIMEX_VIEW
} = require('./banco');

const execFileAsync = promisify(execFile);

const app = express();
const PORT = parseInt(process.env.PORT || '3000', 10);

// Diretórios (Linux é case-sensitive)
const ROOT_DIR = __dirname;
const DATASET_DIR = process.env.DATASET_DIR || path.join(ROOT_DIR, 'dataset');
const SIMEX_DIR = path.join(DATASET_DIR, 'simex');

// Se estiver atrás de proxy (Nginx/Apache/Cloudflare), habilite para obter IP correto
if (process.env.TRUST_PROXY) {
  app.set('trust proxy', true);
}

// ======== Content Security Policy (CSP) ========
const CARTO_ORIGINS = [
  "https://*.basemaps.cartocdn.com",
  "https://a.basemaps.cartocdn.com",
  "https://b.basemaps.cartocdn.com",
  "https://c.basemaps.cartocdn.com"
];

const SIMEX_S3_ORIGINS = [
  "https://imazongeo3-web.s3.amazonaws.com",
  "https://imazongeo3-web.s3.sa-east-1.amazonaws.com"
];

const cspDirectives = {
  "default-src": ["'self'"],

  "script-src": [
    "'self'",
    "'unsafe-inline'",
    "'unsafe-eval'",
    "https://code.jquery.com",
    "https://cdn.jsdelivr.net",
    "https://unpkg.com",
    "https://cdnjs.cloudflare.com",
    "https://cdn.datatables.net",
    "https://d3js.org"
  ],

  "style-src": [
    "'self'",
    "'unsafe-inline'",
    "https://fonts.googleapis.com",
    "https://cdn.jsdelivr.net",
    "https://cdnjs.cloudflare.com",
    "https://cdn.datatables.net",
    "https://unpkg.com"
  ],

  "font-src": [
    "'self'",
    "https://fonts.gstatic.com",
    "https://cdn.jsdelivr.net",
    "https://cdnjs.cloudflare.com"
  ],

  "img-src": [
    "'self'",
    "data:",
    "blob:",
    "https://*.tile.openstreetmap.org",
    ...CARTO_ORIGINS,
    "https://unpkg.com",
    "https://cdn.jsdelivr.net",
    "https://cdnjs.cloudflare.com",
    "https://cdn.datatables.net",
    ...SIMEX_S3_ORIGINS
  ],

  "connect-src": [
    "'self'",
    "https://*.tile.openstreetmap.org",
    ...CARTO_ORIGINS,
    "https://cdn.datatables.net",
    "https://cdnjs.cloudflare.com",
    "https://cdn.jsdelivr.net",
    "https://unpkg.com",
    ...SIMEX_S3_ORIGINS
  ],

  "worker-src": ["'self'", "blob:"],
  "object-src": ["'none'"],
  "frame-ancestors": ["'self'"]
};
const useReportOnly = !!process.env.CSP_REPORT_ONLY;

app.use(
  helmet({
    contentSecurityPolicy: {
      useDefaults: true,
      directives: cspDirectives,
      reportOnly: useReportOnly
    },
    crossOriginEmbedderPolicy: false,
    crossOriginOpenerPolicy: { policy: "same-origin-allow-popups" },
    crossOriginResourcePolicy: { policy: "cross-origin" },
    referrerPolicy: { policy: "no-referrer-when-downgrade" }
  })
);

// ======== Compressão ========
app.use(compression({ threshold: 1024 }));

// ======== Headers estáticos (MIME + Cache) ========
function setStaticHeaders(res, filePath) {
  const lower = filePath.toLowerCase();

  if (lower.endsWith('.geojson')) {
    res.type('application/geo+json; charset=utf-8');
  } else if (lower.endsWith('.csv')) {
    res.type('text/csv; charset=utf-8');
  } else if (lower.endsWith('.json')) {
    res.type('application/json; charset=utf-8');
  }

  // Cache-Control
  if (lower.includes('/dataset/') || lower.endsWith('.csv') || lower.endsWith('.geojson') || lower.endsWith('.json')) {
    // Dados: 10 min + SWR
    res.setHeader('Cache-Control', 'public, max-age=600, stale-while-revalidate=120');
  } else if (/\.(js|css|png|jpg|jpeg|webp|svg|ico|woff2?|ttf)$/.test(lower)) {
    // Assets: 7 dias, immutable
    res.setHeader('Cache-Control', 'public, max-age=604800, immutable');
  } else {
    // HTML/outros: sem cache agressivo
    res.setHeader('Cache-Control', 'no-cache');
  }
}

// ======== Logs úteis de caminho ========
console.log('ROOT_DIR:', ROOT_DIR);
console.log('DATASET_DIR:', DATASET_DIR);
console.log('SIMEX_DIR:', SIMEX_DIR);
console.log('Banco do SIMEX:', bancoConfigurado ? SIMEX_VIEW : 'DATABASE_URL não definida (só S3)');

// ======== Exploração do SIMEX no banco ========
// 503 quando o banco não está configurado/ativo ou ainda não tem a tabela do
// SIMEX: o navegador então lê o CSV (ou o GeoJSON) do S3.
function semBanco(res) {
  res.setHeader('Cache-Control', 'no-store');
  res.status(503).type('text/plain').send('Dados do SIMEX indisponíveis no banco');
}

function comCacheDe10Min(res, tipoMime) {
  res.type(tipoMime);
  res.setHeader('Cache-Control', 'public, max-age=600, stale-while-revalidate=120');
}

// Anos cobertos pelo banco: a página monta o filtro de ano com eles
app.get('/api/simex/periodo', async (_req, res) => {
  const periodo = await periodoSimex();
  if (periodo === null) return semBanco(res);
  comCacheDe10Min(res, 'application/json; charset=utf-8');
  res.send(periodo);
});

app.get('/api/simex/:camada.csv', async (req, res) => {
  const csv = await csvSimex(req.params.camada);
  if (csv === null) return semBanco(res);
  comCacheDe10Min(res, 'text/csv; charset=utf-8');
  res.send(csv);
});

// Polígonos do mapa: de um ano (ou de todos, sem 'ano') e, quando informados,
// só das áreas listadas na página do ranking, ou das UFs pedidas quando o
// ranking é de estados (ambos separados por '|')
app.get('/api/simex/:camada.geojson', async (req, res) => {
  const lista = v => String(v || '').split('|').map(n => n.trim()).filter(Boolean).slice(0, 50);
  const ano = req.query.ano ? parseInt(req.query.ano, 10) : null;
  const geojson = await geojsonSimex(req.params.camada, ano, lista(req.query.nomes), lista(req.query.ufs));
  if (geojson === null) return semBanco(res);
  comCacheDe10Min(res, 'application/geo+json; charset=utf-8');
  res.send(geojson);
});

// ======== Downloads (como no SAD) ========
// Um ano inteiro (as 6 camadas) gerado na hora a partir da visão PostGIS, para
// CSV, GeoJSON e Shapefile trazerem exatamente o mesmo recorte:
//   /api/simex/download/2024.csv                 CSV (UTF-8 com BOM, sem geometria)
//   /api/simex/download/2024.zip?formato=geojson GeoJSON em ZIP
//   /api/simex/download/2024.zip                 Shapefile em ZIP
app.get('/api/simex/download/:ano.:formato', async (req, res) => {
  const ano = Number(req.params.ano);
  const formato = String(req.params.formato).toLowerCase();
  if (!Number.isInteger(ano) || !['csv', 'geojson', 'zip'].includes(formato)) {
    return res.status(400).type('text/plain').send('Parâmetros inválidos');
  }

  const linhas = await linhasDownloadSimex(ano);
  if (linhas === null) return semBanco(res);
  if (!linhas.length) return res.status(404).type('text/plain').send('Sem dados para o período');

  const nome = `simex_${ano}`;
  if (formato === 'csv') {
    res.type('text/csv; charset=utf-8');
    return res.attachment(`${nome}.csv`).send(csvDownloadSimex(linhas));
  }

  const fc = {
    type: 'FeatureCollection',
    features: linhas.map(l => ({
      type: 'Feature',
      properties: Object.fromEntries(CAMPOS_DOWNLOAD.map(c => [c, l[c]])),
      geometry: l.geometry
    }))
  };
  if (formato === 'geojson') {
    res.type('application/geo+json; charset=utf-8');
    return res.attachment(`${nome}.geojson`).send(JSON.stringify(fc));
  }

  // ZIP: o GeoJSON (?formato=geojson) ou o Shapefile convertido pelo ogr2ogr
  const tmp = await fs.promises.mkdtemp(path.join(os.tmpdir(), `simex-${ano}-`));
  const limpar = () => fs.promises.rm(tmp, { recursive: true, force: true });
  try {
    const geo = path.join(tmp, `${nome}.geojson`);
    const zip = path.join(tmp, `${nome}.zip`);
    await fs.promises.writeFile(geo, JSON.stringify(fc));
    if (req.query.formato === 'geojson') {
      await execFileAsync('zip', ['-j', '-q', zip, geo]);
    } else {
      const shp = path.join(tmp, 'shapefile');
      await fs.promises.mkdir(shp);
      await execFileAsync('ogr2ogr', ['-f', 'ESRI Shapefile', '-lco', 'ENCODING=UTF-8', shp, geo]);
      const partes = (await fs.promises.readdir(shp)).map(a => path.join(shp, a));
      await execFileAsync('zip', ['-j', '-q', zip, ...partes]);
    }
    res.download(zip, `${nome}.zip`, limpar);
  } catch (e) {
    await limpar();
    res.status(500).type('text/plain').send(`Falha ao gerar arquivo: ${e.message}`);
  }
});

// ======== Servir /dataset (Linux: nomes exatos!) ========
// Monta o diretório inteiro do dataset em /dataset
app.use('/dataset', express.static(DATASET_DIR, { setHeaders: setStaticHeaders }));
// Monta explicitamente /dataset/simex -> <DATASET_DIR>/simex (útil para evitar confusão de docroot externos)
app.use('/dataset/simex', express.static(SIMEX_DIR, {
  setHeaders: setStaticHeaders,
  index: false,
  maxAge: 0
}));

// ======== Servir /img (para /img/simex.png no HTML) ========
app.use('/img', express.static(path.join(ROOT_DIR, 'img'), { setHeaders: setStaticHeaders }));

// ======== Raiz (HTML/estáticos do app) ========
// Arquivos do servidor ficam fora: o .env tem a senha do banco, e os logs e a
// configuração não interessam ao navegador.
// Inclui os arquivos ocultos: sem isso o .env cai no fallback do SPA e responde
// a página em vez de 404 (o conteúdo não vaza, mas o 404 é mais claro).
const ARQUIVOS_PRIVADOS = /^\/(\.|server\.js|banco\.js|package(-lock)?\.json|ecosystem\.config\.js|logs(\/|$))/;
app.use((req, res, next) => {
  if (ARQUIVOS_PRIVADOS.test(req.path)) return res.status(404).type('text/plain').send('Não encontrado');
  next();
});

app.use(express.static(ROOT_DIR, {
  setHeaders: setStaticHeaders,
  extensions: ['html'], // permite /rota → /rota.html
  dotfiles: 'ignore'    // .env e outros arquivos ocultos
}));

// ======== Healthcheck ========
app.get('/healthz', (_req, res) => res.status(200).send('ok'));

// ======== Rotas de debug ========
// 1) CSP efetivo (ver o cabeçalho enviado por este processo)
app.get('/__csp', (req, res) => {
  res.type('text/plain');
  res.send(res.get('content-security-policy') || 'sem CSP');
});

// 2) Listar conteúdo do dataset (para checar nomes/case no servidor)
app.get('/__ls', (req, res) => {
  const sub = req.query.dir || '';
  const dir = path.join(DATASET_DIR, sub);
  fs.readdir(dir, (err, files) => {
    if (err) return res.status(500).json({ err: err.message, dir });
    res.json({ dir, files });
  });
});

// ======== SPA fallback ========
// Se pedir uma rota sem extensão, devolve index.html (se for SPA)
app.use((req, res, next) => {
  if (path.extname(req.path)) return next(); // pede arquivo com extensão → deixa 404 padrão
  res.sendFile(path.join(ROOT_DIR, 'index.html'));
});

// ======== Start ========
app.listen(PORT, () => {
  console.log(`✅ Server em http://localhost:${PORT}`);
  console.log(`🛡️ CSP ${useReportOnly ? '(Report-Only)' : '(Enforcing)'} ativo`);
});
