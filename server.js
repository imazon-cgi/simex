// server.js
// Servidor Express para o dashboard SIMEX (index.html na raiz)
// - /dataset -> arquivos CSV/GeoJSON
// - /img     -> imagens (ex.: /img/simex.png)
// - CSP compatível com Bootstrap/Leaflet/Chart.js/D3/Turf/html2canvas

const path = require('path');
const express = require('express');
const compression = require('compression');
const helmet = require('helmet');

const app = express();
const PORT = process.env.PORT || 3002;

// Diretórios
const ROOT_DIR = __dirname;
const DATASET_DIR = path.join(ROOT_DIR, 'dataset');
const IMG_DIR = path.join(ROOT_DIR, 'img');

// ---- Segurança (helmet + CSP) ----
app.use(
  helmet({
    contentSecurityPolicy: {
      useDefaults: true,
      directives: {
        "default-src": ["'self'"],

        // Scripts (Bootstrap bundle, Leaflet, Chart.js, D3, etc.)
        "script-src": [
          "'self'",
          "'unsafe-inline'",
          "'unsafe-eval'",
          "https://cdn.jsdelivr.net",
          "https://unpkg.com",
          "https://cdnjs.cloudflare.com",
          "https://d3js.org"
        ],

        // CSS externos (Bootstrap, Font Awesome, Google Fonts)
        "style-src": [
          "'self'",
          "'unsafe-inline'",
          "https://cdn.jsdelivr.net",
          "https://cdnjs.cloudflare.com",
          "https://fonts.googleapis.com",
          "https://unpkg.com"
        ],

        // Fontes
        "font-src": [
          "'self'",
          "https://fonts.gstatic.com",
          "https://cdn.jsdelivr.net",
          "https://cdnjs.cloudflare.com"
        ],

        // Imagens (tiles OSM + CARTO, data:, blob:, e opcionalmente seu S3)
        "img-src": [
          "'self'",
          "data:",
          "blob:",
          "https://*.tile.openstreetmap.org",
          "https://*.basemaps.cartocdn.com",
          // Se usar imagens/GeoJSON via S3, libere explicitamente o bucket:
          // "https://imazongeo3-web.s3.sa-east-1.amazonaws.com"
        ],

        // Fetch/XHR (inclui unpkg para baixar sourcemap do Leaflet)
        "connect-src": [
          "'self'",
          "https://*.tile.openstreetmap.org",
          "https://cdn.jsdelivr.net",
          "https://cdnjs.cloudflare.com",
          "https://unpkg.com",
          "https://d3js.org"
        ],

        // Para libs que usam Web Workers / canvas
        "worker-src": ["'self'", "blob:"],

        "object-src": ["'none'"],
        "frame-ancestors": ["'self'"]
      }
    },
    crossOriginEmbedderPolicy: false,
    crossOriginOpenerPolicy: { policy: "same-origin-allow-popups" },
    crossOriginResourcePolicy: { policy: "cross-origin" },
    referrerPolicy: { policy: "no-referrer-when-downgrade" }
  })
);

// Compressão
app.use(compression({ threshold: 1024 }));

// Cabeçalhos de cache + MIME específicos
function setStaticHeaders(res, filePath) {
  const fp = filePath.toLowerCase();

  if (fp.endsWith('.geojson')) {
    res.type('application/geo+json; charset=utf-8');
  } else if (fp.endsWith('.csv')) {
    res.type('text/csv; charset=utf-8');
  } else if (fp.endsWith('.json')) {
    res.type('application/json; charset=utf-8');
  }

  // Cache leve para dados, mais agressivo para assets estáticos
  if (fp.includes('/dataset/') || fp.endsWith('.csv') || fp.endsWith('.geojson') || fp.endsWith('.json')) {
    res.setHeader('Cache-Control', 'public, max-age=600, stale-while-revalidate=120'); // 10 min
  } else if (/\.(js|css|png|jpg|jpeg|webp|svg|ico|woff2?|ttf)$/.test(fp)) {
    res.setHeader('Cache-Control', 'public, max-age=604800, immutable'); // 7 dias
  } else {
    res.setHeader('Cache-Control', 'no-cache');
  }
}

// Rotas estáticas
app.use('/dataset', express.static(DATASET_DIR, { setHeaders: setStaticHeaders }));
app.use('/img', express.static(IMG_DIR, { setHeaders: setStaticHeaders }));

// Servir arquivos estáticos da raiz (index.html, etc.)
app.use(
  express.static(ROOT_DIR, {
    setHeaders: setStaticHeaders,
    extensions: ['html'] // permite /rota -> rota.html
  })
);

// Healthcheck
app.get('/healthz', (_req, res) => res.status(200).send('ok'));

// Fallback SPA (somente quando não houver extensão no caminho)
app.get('*', (req, res, next) => {
  if (path.extname(req.path)) return next();
  res.sendFile(path.join(ROOT_DIR, 'index.html'));
});

app.listen(PORT, () => {
  console.log(`✅ SIMEX rodando em http://localhost:${PORT}`);
  console.log(`📁 Raiz:      ${ROOT_DIR}`);
  console.log(`📁 /dataset → ${DATASET_DIR}`);
  console.log(`📁 /img     → ${IMG_DIR}`);
});
