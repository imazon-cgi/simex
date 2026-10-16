// banco.js — exploração madeireira do SIMEX lida do banco do imazongeo_upload
// (PostgreSQL/PostGIS).
//
// O banco é opcional. Sem DATABASE_URL, com o banco fora do ar, sem a visão do
// SIMEX ou sem dados da camada pedida, as funções devolvem null e o dashboard
// continua lendo os CSVs e GeoJSON do S3.
//
// Visão esperada (imazongeo.vw_simex do imazongeo_upload), uma linha por
// polígono de exploração:
//   ano        inteiro
//   camada     'municipios' | 'imoveis_rurais' | 'assentamentos' |
//              'terras_indigenas' | 'unidades_conservacao' | 'terras_nao_destinadas'
//   categoria  'autorizada' | 'não autorizada' | 'análise' (vazio em 2020)
//   uf         sigla da UF
//   municipio  nome do município
//   territorio nome do imóvel, assentamento, TI, UC ou gleba
//   subclasse  classe fundiária de origem (SIGEF, CARpr, ARU, ND_B...)
//   esfera     federal ou estadual (só unidades_conservacao)
//   grupo      US ou PI (só unidades_conservacao)
//   fase_ti    situação jurídica (só terras_indigenas)
//   area_ha    área do polígono (ha)
const { Pool } = require('pg');

const DATABASE_URL = (process.env.DATABASE_URL || '').trim();
const SIMEX_VIEW = (process.env.SIMEX_DB_VIEW || 'imazongeo.vw_simex').trim();
const CACHE_MS = parseInt(process.env.SIMEX_DB_CACHE_MS || '600000', 10); // 10 min, igual ao /dataset
const RETRY_MS = 60 * 1000; // banco fora do ar ou sem dados: tenta de novo após 1 min
// Teto de polígonos por requisição do mapa. Acima disso o banco devolve nada e o
// navegador cai no GeoJSON do S3, em vez de baixar centenas de MB. A abertura
// da página (modo "Todos", todos os anos) pede os imóveis rurais dos 10
// municípios do topo: ~17,7 mil polígonos, 16 MB do banco contra 123 MB do S3.
const MAX_POLIGONOS = parseInt(process.env.SIMEX_DB_MAX_POLIGONOS || '20000', 10);

if (!/^[A-Za-z_]\w*(\.[A-Za-z_]\w*)?$/.test(SIMEX_VIEW)) {
  throw new Error(`SIMEX_DB_VIEW inválida: ${SIMEX_VIEW}`);
}

// Cada recorte do dashboard: a camada no banco, a coluna com o nome do
// território e as colunas extras que só ele usa. Os nomes entre aspas são os
// que o index.html procura no CSV do S3 — o banco devolve o mesmo cabeçalho.
//
// 'rotulo' é a coluna que o dashboard mostra no ranking e no mapa, e por onde
// ele recorta os polígonos. Em imóveis rurais o rótulo é o município (o nome do
// imóvel é um código), por isso ela nem sempre é 'territorio'.
const RECORTES = {
  municipios:            { camada: 'municipios',            nome: null,                         rotulo: 'municipio',  extras: [] },
  imoveis_rurais:        { camada: 'imoveis_rurais',        nome: ['territorio', 'name'],       rotulo: 'municipio',  extras: [['subclasse', 'sub_class']] },
  assentamentos:         { camada: 'assentamentos',         nome: ['territorio', 'name'],       rotulo: 'territorio', extras: [['subclasse', 'sub_class']] },
  terras_nao_destinadas: { camada: 'terras_nao_destinadas', nome: ['territorio', 'name'],       rotulo: 'territorio', extras: [['subclasse', 'sub_class']] },
  terras_indigenas:      { camada: 'terras_indigenas',      nome: ['territorio', 'terrai_nom'], rotulo: 'territorio', extras: [['fase_ti', 'fase_ti']] },
  unidades_conservacao:  { camada: 'unidades_conservacao',  nome: ['territorio', 'nome_1'],     rotulo: 'territorio', extras: [['grupo', 'grupo'], ['esfera', 'esfera']] }
};

// Colunas comuns a todos os recortes: [coluna da visão, nome usado pelo index.html]
const COLUNAS_BASE = [['uf', 'sigla_uf'], ['ano', 'ano'], ['categoria', 'categoria'], ['municipio', 'nome']];

function colunas(recorte) {
  return [...COLUNAS_BASE, ...(recorte.nome ? [recorte.nome] : []), ...recorte.extras];
}

// O dashboard só usa somas de área e contagens de nomes distintos (nunca conta
// linhas), então os polígonos são somados por ano + área: mesmos totais com um
// CSV muito menor (imóveis rurais vai de 52 mil linhas para poucos milhares).
function sqlCsv(recorte) {
  const grupo = colunas(recorte);
  return `SELECT ${grupo.map(([col, nome]) => `${col} AS "${nome}"`).join(', ')},
                 round(sum(area_ha)::numeric, 6) AS "area_ha"
          FROM ${SIMEX_VIEW}
          WHERE camada = $1
          GROUP BY ${grupo.map(([col]) => col).join(', ')}
          ORDER BY ano`;
}

// Polígonos de um recorte, com as mesmas propriedades que o GeoJSON do S3 traz.
// O contorno da Amazônia Legal continua vindo do S3: o banco guarda exploração,
// não limites territoriais.
function sqlGeojson(recorte, filtro) {
  const props = colunas(recorte)
    .map(([col, nome]) => `'${nome}', ${col}`)
    .concat("'area_ha', round(area_ha::numeric, 6)");
  return `SELECT json_build_object(
            'type', 'FeatureCollection',
            'features', coalesce(json_agg(json_build_object(
              'type', 'Feature',
              'properties', json_build_object(${props.join(', ')}),
              'geometry', ST_AsGeoJSON(geom, 6)::json)), '[]'::json))::text AS geojson
          FROM ${SIMEX_VIEW} WHERE ${filtro}`;
}

// $1 camada; depois, se houver, o ano, os nomes das áreas desenhadas no mapa e
// as UFs (o ranking de estados lista UFs, não áreas). Sem ano ('all' no filtro
// da página), o teto de polígonos é quem decide se o banco responde.
function filtroGeojson(recorte, ano, nomes, ufs) {
  const valores = [recorte.camada];
  let sql = 'camada = $1';
  if (ano !== null) {
    valores.push(ano);
    sql += ` AND ano = $${valores.length}`;
  }
  if (nomes.length) {
    valores.push(nomes);
    sql += ` AND ${recorte.rotulo} = ANY($${valores.length})`;
  }
  if (ufs.length) {
    valores.push(ufs);
    sql += ` AND uf = ANY($${valores.length})`;
  }
  return { sql, valores };
}

// Um ano inteiro (as 6 camadas) para os downloads, nos campos do padrão do
// imazongeo_upload e com a geometria completa: sem o recorte do mapa.
const CAMPOS_DOWNLOAD = ['ano', 'camada', 'categoria', 'uf', 'municipio', 'cod_mun',
  'territorio', 'subclasse', 'area_ha'];
const sqlDownload = `
  SELECT ano, camada, categoria, uf, municipio, cod_mun, territorio, subclasse,
         area_ha::float8 AS area_ha, ST_AsGeoJSON(geom)::json AS geometry
    FROM ${SIMEX_VIEW}
   WHERE ano = $1
   ORDER BY camada, uf, municipio, territorio`;

function celulaCsv(v) {
  if (v === null || v === undefined) return '';
  const s = String(v);
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function paraCsv(nomes, linhas) {
  const saida = [nomes.join(',')];
  for (const linha of linhas) saida.push(linha.map(celulaCsv).join(','));
  return saida.join('\n') + '\n';
}

let pool = null;
function obterPool() {
  if (!pool) {
    pool = new Pool({
      connectionString: DATABASE_URL,
      max: 4,
      connectionTimeoutMillis: 3000,
      idleTimeoutMillis: 30000,
      statement_timeout: 120000
    });
    // Erro numa conexão ociosa (ex.: banco reiniciado) não pode derrubar o servidor
    pool.on('error', err => console.warn('Banco: conexão ociosa perdida:', err.message));
  }
  return pool;
}

// Loga só quando a fonte de um recorte muda, para não repetir a cada consulta
const ultimaMensagem = new Map();
function registrar(chave, mensagem) {
  if (ultimaMensagem.get(chave) === mensagem) return;
  ultimaMensagem.set(chave, mensagem);
  console.log(`SIMEX ${chave}: ${mensagem}`);
}

let indisponivelAte = 0;
function aoFalhar(chave, err) {
  indisponivelAte = Date.now() + RETRY_MS;
  const motivos = {
    '42P01': `${SIMEX_VIEW} não existe`,
    '42703': `${SIMEX_VIEW} está desatualizada (falta uma coluna); rode banco/sql/simex.sql`
  };
  registrar(chave, `banco indisponível (${motivos[err.code] || err.message || err.code}); lendo do S3`);
  return null;
}

async function consultarCsv(recorte, chave) {
  try {
    const { rows, fields } = await obterPool().query({
      text: sqlCsv(recorte),
      values: [recorte.camada],
      rowMode: 'array'
    });
    if (!rows.length) {
      registrar(chave, `sem dados em ${SIMEX_VIEW}; lendo do S3`);
      return null;
    }
    registrar(chave, `lendo do banco (${SIMEX_VIEW})`);
    return paraCsv(fields.map(f => f.name), rows);
  } catch (err) {
    return aoFalhar(chave, err);
  }
}

async function consultarGeojson(recorte, chave, ano, nomes, ufs) {
  const { sql, valores } = filtroGeojson(recorte, ano, nomes, ufs);
  try {
    const { rows } = await obterPool().query(`SELECT count(*) FROM ${SIMEX_VIEW} WHERE ${sql}`, valores);
    const total = Number(rows[0].count);
    if (!total) {
      // Nenhuma das áreas pedidas nesta camada (no modo "Todos" o ranking lista
      // municípios, e TIs, UCs e assentamentos não se chamam assim): se a camada
      // tem dados no ano, a resposta certa é vazia. Ir ao S3 baixaria a camada
      // inteira, e o mapa, que filtra pelos mesmos nomes, também não acharia nada.
      if (nomes.length || ufs.length) {
        const base = filtroGeojson(recorte, ano, [], []);
        const existe = await obterPool().query(`SELECT 1 FROM ${SIMEX_VIEW} WHERE ${base.sql} LIMIT 1`, base.valores);
        if (existe.rows.length) {
          registrar(chave, `nenhuma das áreas pedidas em ${SIMEX_VIEW}; resposta vazia`);
          return '{"type":"FeatureCollection","features":[]}';
        }
      }
      registrar(chave, `sem polígonos em ${SIMEX_VIEW}; lendo do S3`);
      return null;
    }
    if (total > MAX_POLIGONOS) {
      registrar(chave, `recorte com ${total} polígonos (teto ${MAX_POLIGONOS}); lendo do S3`);
      return null;
    }
    const r = await obterPool().query(sqlGeojson(recorte, sql), valores);
    registrar(chave, `lendo do banco (${SIMEX_VIEW})`);
    return r.rows[0].geojson;
  } catch (err) {
    return aoFalhar(chave, err);
  }
}

async function consultarPeriodo() {
  try {
    const { rows } = await obterPool().query(
      `SELECT min(ano) AS ano_min, max(ano) AS ano_max FROM ${SIMEX_VIEW}`
    );
    const p = rows[0];
    if (!p || !p.ano_max) return null;
    registrar('periodo', `${p.ano_min} a ${p.ano_max}`);
    return JSON.stringify({ ano_min: p.ano_min, ano_max: p.ano_max });
  } catch (err) {
    return aoFalhar('periodo', err);
  }
}

// chave -> { expira, valor: Promise<string|null> }; a Promise evita consultas
// repetidas quando vários navegadores pedem o mesmo arquivo ao mesmo tempo.
const cache = new Map();

function comCache(chave, consultar) {
  const item = cache.get(chave);
  if (item && item.expira > Date.now()) return item.valor;
  if (Date.now() < indisponivelAte) return Promise.resolve(null);

  const novo = { expira: Date.now() + CACHE_MS, valor: consultar() };
  novo.valor.then(v => { if (v === null) novo.expira = Date.now() + RETRY_MS; });
  if (cache.size > 60) cache.delete(cache.keys().next().value); // o mapa varia com ano e nomes
  cache.set(chave, novo);
  return novo.valor;
}

// CSV do recorte no layout do dashboard, ou null se o banco não puder ser usado
function csvSimex(camada) {
  const recorte = RECORTES[camada];
  if (!DATABASE_URL || !recorte) return Promise.resolve(null);
  return comCache(camada, () => consultarCsv(recorte, camada));
}

// GeoJSON do recorte, opcionalmente só de um ano, das áreas desenhadas no mapa
// e das UFs pedidas. null quando o banco não pode ser usado: o navegador então
// busca o GeoJSON do S3.
function geojsonSimex(camada, ano, nomes = [], ufs = []) {
  const recorte = RECORTES[camada];
  const anoOk = ano === null || (Number.isInteger(ano) && ano >= 2000 && ano <= 2100);
  if (!DATABASE_URL || !recorte || !anoOk) return Promise.resolve(null);
  const chave = `${camada}.geojson/${ano ?? 'todos'}/${nomes.join('|')}/${ufs.join('|')}`;
  return comCache(chave, () => consultarGeojson(recorte, chave, ano, nomes, ufs));
}

// {ano_min, ano_max} do banco, ou null (a página então usa o padrão dela)
function periodoSimex() {
  if (!DATABASE_URL) return Promise.resolve(null);
  return comCache('periodo', consultarPeriodo);
}

// Linhas de um ano para os downloads (sem cache: cada formato é gerado na
// hora), ou null quando o banco não está configurado ou não respondeu.
async function linhasDownloadSimex(ano) {
  if (!DATABASE_URL) return null;
  try {
    const { rows } = await obterPool().query(sqlDownload, [ano]);
    return rows;
  } catch (err) {
    console.warn(`SIMEX download ${ano}: banco indisponível (${err.message || err.code})`);
    return null;
  }
}

// CSV do download: UTF-8 com BOM (acentos certos no Excel) e sem geometria,
// como no padrão do imazongeo_upload
function csvDownloadSimex(linhas) {
  return '﻿' + paraCsv(CAMPOS_DOWNLOAD, linhas.map(l => CAMPOS_DOWNLOAD.map(c => l[c])));
}

module.exports = {
  csvSimex, geojsonSimex, periodoSimex, linhasDownloadSimex, csvDownloadSimex, CAMPOS_DOWNLOAD,
  bancoConfigurado: !!DATABASE_URL, SIMEX_VIEW
};
