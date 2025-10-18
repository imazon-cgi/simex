// server.js (Linux-ready)
// Executar: NODE_ENV=production node server.js
// Variáveis opcionais:
//   PORT=3000
//   DATASET_DIR=/caminho/absoluto/para/dataset
//   TRUST_PROXY=1                (se estiver atrás de Nginx/Apache/ALB/ELB/Cloudflare)
//   CSP_REPORT_ONLY=1            (CSP em modo "report only")

const path = require('path');
const fs = require('fs');
const express = require('express');
const compression = require('compression');
const helmet = require('helmet');

const app = express();
const PORT = parseInt(process.env.PORT || '3000', 10);

// Diretórios (Linux é case-sensitive)
const ROOT_DIR = __dirname;
const DATASET_DIR = process.env.DATASET_DIR || path.join(ROOT_DIR, 'dataset');
const SAD_DIR = path.join(DATASET_DIR, 'sad');

// Se estiver atrás de proxy (Nginx/Apache/Cloudflare), habilite para obter IP correto
if (process.env.TRUST_PROXY) {
  app.set('trust proxy', true);
}

// ======== Content Security Policy (CSP) ========
// CORREÇÃO COMPLETA: Adicionado todos os domínios necessários
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
    "https://*.basemaps.cartocdn.com", // CORREÇÃO: Domínio correto para imagens
    "https://a.basemaps.cartocdn.com", // CORREÇÃO: Subdomínios específicos
    "https://b.basemaps.cartocdn.com",
    "https://c.basemaps.cartocdn.com",
    "https://unpkg.com",
    "https://cdn.jsdelivr.net",
    "https://cdnjs.cloudflare.com",
    "https://cdn.datatables.net",
    "https://imazongeo3-web.s3.sa-east-1.amazonaws.com"
  ],

  "connect-src": [
    "'self'",
    "https://*.tile.openstreetmap.org",
    "https://*.basemaps.cartocdn.com", // CORREÇÃO: Para requisições de conexão
    "https://a.basemaps.cartocdn.com",
    "https://b.basemaps.cartocdn.com", 
    "https://c.basemaps.cartocdn.com",
    "https://cdn.datatables.net",
    "https://cdnjs.cloudflare.com",
    "https://cdn.jsdelivr.net",
    "https://unpkg.com"
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
console.log('SAD_DIR:', SAD_DIR);

// ======== Servir /dataset (Linux: nomes exatos!) ========
// Monta o diretório inteiro do dataset em /dataset
app.use('/dataset', express.static(DATASET_DIR, { setHeaders: setStaticHeaders }));
// Monta explicitamente /dataset/sad -> <DATASET_DIR>/sad (útil para evitar confusão de docroot externos)
app.use('/dataset/sad', express.static(SAD_DIR, {
  setHeaders: setStaticHeaders,
  index: false,
  maxAge: 0
}));

// ======== Servir /img (para /img/simex.png no HTML) ========
app.use('/img', express.static(path.join(ROOT_DIR, 'img'), { setHeaders: setStaticHeaders }));

// ======== Raiz (HTML/estáticos do app) ========
app.use(express.static(ROOT_DIR, {
  setHeaders: setStaticHeaders,
  extensions: ['html'] // permite /rota → /rota.html
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