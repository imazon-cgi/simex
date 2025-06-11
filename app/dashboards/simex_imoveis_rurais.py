"""
Dashboard – SIMEX • Exploração Madeireira em Imóveis Rurais Privados
Rota Flask: /simex/imoveis_rurais/
"""

# ────────────────────────── imports ──────────────────────────
from __future__ import annotations

import io, os, tempfile, requests, unidecode
import dash, dash_bootstrap_components as dbc, geopandas as gpd, pandas as pd
import plotly.express as px, plotly.graph_objects as go
from dash import html, dcc, Input, Output, State, callback_context

HEADERS = {"User-Agent": "Mozilla/5.0"}

# ─────────────────── utilitários de download ──────────────────
def _tmp_from_url(url: str, suffix: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=45); r.raise_for_status()
    f = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    for chunk in r.iter_content(1024 * 1024):
        f.write(chunk)
    f.close(); return f.name

def load_geojson(url: str):
    try:
        return gpd.read_file(url)
    except Exception:
        try:
            p = _tmp_from_url(url, ".geojson")
            g = gpd.read_file(p); os.unlink(p); return g
        except Exception:
            return None

def load_parquet(url: str) -> pd.DataFrame | None:
    try:
        return pd.read_parquet(url)
    except Exception:
        try:
            buf = io.BytesIO(requests.get(url, headers=HEADERS, timeout=45).content)
            return pd.read_parquet(buf)
        except Exception:
            return None

# ───────────────────────── URLs de dados ──────────────────────
GJSON = [
    "https://raw.githubusercontent.com/imazon-cgi/simex/main/"
    "datasets/geojson/simex_amazonia_PAMT2007_2023_imoveisrurais.geojson",
]
PARQUET = [
    "https://raw.githubusercontent.com/imazon-cgi/simex/main/"
    "datasets/csv/simex_amazonia_PAMT2007_2023_imoveisrurais.parquet",
]

# ──────────────────────── carrega dados ───────────────────────
roi = load_geojson(GJSON[0])
roi["name"] = roi["name"].str.encode("latin1", errors="ignore").str.decode("utf-8", errors="ignore")

df = load_parquet(PARQUET[0])
df["name"] = df["name"].str.encode("latin1", errors="ignore").str.decode("utf-8", errors="ignore").astype(str)

list_states = df["sigla_uf"].unique()
list_anual  = sorted(df["ano"].unique())

state_options = [{"label": s, "value": s} for s in list_states]
year_options  = [{"label": y, "value": y} for y in list_anual]
category_options = [
    {"label": "Não autorizada", "value": "não autorizada"},
    {"label": "Autorizada",     "value": "autorizada"},
    {"label": "Análise",        "value": "análise"},
    {"label": "Todas",          "value": None},
]

# ╭────────────────────────────────────────────────────────────╮
# │ Função pública – registrar dashboard                      │
# ╰────────────────────────────────────────────────────────────╯
def register_simex_imoveis_rurais_dashboard(flask_server):
    app = dash.Dash(
        __name__,
        server=flask_server,
        url_base_pathname="/simex/imoveis_rurais/",
        external_stylesheets=[
            dbc.themes.BOOTSTRAP,
            "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css",
        ],
        suppress_callback_exceptions=True,
        title="SIMEX – Imóveis Rurais",
    )

    # ───────────── layout ─────────────
    app.layout = dbc.Container([
        html.Meta(name="viewport", content="width=device-width, initial-scale=1"),

        dcc.Download(id="download-dataframe-csv"),

        # ░░░ TOPO RESPONSIVO (sticky) ░░░
        html.Div([
            # 1ª LINHA: anos + atualizar
            dbc.Row([
                dbc.Col(html.Label("Ano Inicial:", className="label-fit"),
                        xs=12, sm="auto",
                        className="d-flex align-items-center"),
                dbc.Col(dcc.Dropdown(id="start-year-dropdown",
                                     options=year_options, value=2016, clearable=False),
                        xs=12, sm=6, md=3, lg=2),

                dbc.Col(html.Label("Ano Final:", className="label-fit"),
                        xs=12, sm="auto",
                        className="d-flex align-items-center mt-2 mt-sm-0"),
                dbc.Col(dcc.Dropdown(id="end-year-dropdown",
                                     options=year_options, value=2023, clearable=False),
                        xs=12, sm=6, md=3, lg=2, className="mt-2 mt-sm-0"),

                dbc.Col(dbc.Button([html.I(className="fa fa-refresh me-1"),
                                    "Atualizar Intervalo"],
                                   id="refresh-button", n_clicks=0,
                                   color="success", className="btn-sm custom-button w-100"),
                        xs=12, sm="auto",
                        className="d-flex align-items-center mt-2 mt-sm-0"),
            ], className="gx-2 gy-1"),

            # 2ª LINHA: botões de ação
            dbc.Row([
                dbc.Col(dbc.Button([html.I(className="fa fa-filter me-1"), "Remover Filtros"],
                                   id="reset-button-top", n_clicks=0,
                                   color="success", className="btn-sm custom-button w-100"),
                        xs=6, sm="auto", className="mt-2 mt-sm-0"),

                dbc.Col(dbc.Button([html.I(className="fa fa-map me-1"), "Selecione o Estado"],
                                   id="open-state-modal-button",
                                   color="success", className="btn-sm custom-button w-100"),
                        xs=6, sm="auto", className="mt-2 mt-sm-0"),

                dbc.Col(dbc.Button([html.I(className="fa fa-map me-1"), "Selecionar Área de Interesse"],
                                   id="open-area-modal-button",
                                   color="success", className="btn-sm custom-button w-100"),
                        xs=6, sm="auto", className="mt-2 mt-sm-0"),

                dbc.Col(dbc.Button([html.I(className="fa fa-download me-1"), "Baixar CSV"],
                                   id="open-modal-button",
                                   color="success", className="btn-sm custom-button w-100"),
                        xs=6, sm="auto", className="mt-2 mt-sm-0"),
            ], className="gx-2 gy-1 mb-3"),
        ], className="sticky-top bg-white shadow-sm pt-2 pb-2 px-2", style={"zIndex": 999}),

        # CATEGORIA
        dbc.Row([
            dbc.Col(html.Label("Categoria:", className="label-fit"),
                    xs=12, sm="auto", className="d-flex align-items-center"),
            dbc.Col(dcc.Dropdown(id="category-dropdown",
                                 options=category_options, value=None, clearable=False),
                    xs=12, sm=6, md=3, lg=2, className="mt-2 mt-sm-0"),
        ], className="gx-2 mb-4"),

        # GRÁFICOS
        dbc.Row([
            dbc.Col(dbc.Card(dcc.Graph(id="bar-graph-yearly"), className="graph-block"),
                    xs=12, lg=6),
            dbc.Col(dbc.Card(dcc.Graph(id="choropleth-map"), className="graph-block"),
                    xs=12, lg=6),
        ], className="mb-4"),
        dbc.Row(dbc.Col(dbc.Card(dcc.Graph(id="line-graph"), className="graph-block"),
                        xs=12), className="mb-4"),

        # STORES
        dcc.Store(id="selected-states", data=[]),
        dcc.Store(id="selected-year",   data=list_anual[-1]),
        dcc.Store(id="selected-area",   data=[]),
        dcc.Store(id="selected-areas-store", data=[]),

        # MODAIS (inalterados)
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("Escolha Áreas de Interesse da Amazônia Legal")),
            dbc.ModalBody(dcc.Dropdown(options=state_options, id="state-dropdown-modal",
                                       placeholder="Selecione o Estado", multi=True)),
            dbc.ModalFooter(dbc.Button("Fechar", id="close-state-modal-button", color="danger")),
        ], id="state-modal", is_open=False),

        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("Escolha as Áreas de Interesse")),
            dbc.ModalBody(dcc.Dropdown(id="area-dropdown",
                                       placeholder="Selecione as Áreas de Interesse", multi=True)),
            dbc.ModalFooter(dbc.Button("Fechar", id="close-area-modal-button", color="danger")),
        ], id="area-modal", is_open=False),

        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("Configurações para gerar o CSV")),
            dbc.ModalBody([
                dbc.Checklist(options=state_options, id="state-checklist", inline=True),
                html.Hr(),
                dbc.RadioItems(options=[{"label":"Ponto","value":"."},{"label":"Vírgula","value":","}],
                               value=".", id="decimal-separator",
                               inline=True, className="mb-2"),
                dbc.Checkbox(label="Sem acentuação", id="remove-accents", value=False),
            ]),
            dbc.ModalFooter([
                dbc.Button("Download", id="download-button", color="success"),
                dbc.Button("Fechar",    id="close-modal-button", color="danger"),
            ]),
        ], id="modal", is_open=False),
    ], fluid=True)

    # ───────────────────────── helpers & callbacks ─────────────────────────
    def preencher_anos_faltantes(df_in, anos, municipios):
        df_agg = df_in.groupby(["ano","nome"], as_index=False).sum()
        full_index = pd.MultiIndex.from_product([anos, municipios], names=["ano","nome"])
        return (df_agg.set_index(["ano","nome"])
                       .reindex(full_index, fill_value=0).reset_index())

    def get_centroid(geojson, municipio_nome):
        try:
            gdf_mun = geojson[geojson["nome"] == municipio_nome]
            if not gdf_mun.empty:
                c = gdf_mun.geometry.centroid.iloc[0]
                return c.y, c.x
        except Exception as e:
            print(f"Erro ao obter centroide para {municipio_nome}: {e}")
        return -14, -55

    # --------------- CALLBACK PRINCIPAL (gráficos) ---------------
    @app.callback(
        [Output("bar-graph-yearly","figure"),
         Output("choropleth-map","figure"),
         Output("line-graph","figure"),
         Output("selected-states","data"),
         Output("state-dropdown-modal","value"),
         Output("selected-area","data"),
         Output("area-dropdown","options"),
         Output("area-dropdown","value"),
         Output("selected-areas-store","data")],
        [Input("start-year-dropdown","value"),
         Input("end-year-dropdown","value"),
         Input("category-dropdown","value"),
         Input("choropleth-map","clickData"),
         Input("bar-graph-yearly","clickData"),
         Input("state-dropdown-modal","value"),
         Input("area-dropdown","value"),
         Input("reset-button-top","n_clicks"),
         Input("refresh-button","n_clicks")],
        [State("selected-states","data"),
         State("selected-area","data"),
         State("selected-areas-store","data")],
    )
    def update_graphs(start_year, end_year, selected_category,
                      map_click, bar_click,
                      sel_state_modal, sel_area_dropdown,
                      reset_clicks, refresh_clicks,
                      selected_states, selected_area_state,
                      selected_areas_store):

        trig = ([p["prop_id"] for p in callback_context.triggered] or [""])[0]

        # defaults
        start_year = int(start_year or 2016)
        end_year   = int(end_year or 2023)
        df["ano"]  = df["ano"].astype(int)

        # reset
        if trig == "reset-button-top.n_clicks":
            selected_states = []; sel_state_modal = None
            selected_area_state = []; selected_category = None
            start_year, end_year = 2016, 2023
            selected_areas_store = []

        # clicou barra
        if trig == "bar-graph-yearly.clickData" and bar_click:
            area = bar_click["points"][0]["y"]
            selected_areas_store = [a for a in selected_areas_store if a != area] \
                if area in selected_areas_store else selected_areas_store + [area]

        # clicou mapa
        if trig == "choropleth-map.clickData" and map_click:
            mun = map_click["points"][0]["location"]
            if mun in df["nome"].values:
                selected_area_state = [a for a in selected_area_state if a != mun] \
                    if mun in selected_area_state else selected_area_state + [mun]

        if sel_area_dropdown: selected_area_state = sel_area_dropdown

        # filtros
        df_f = df[df["categoria"] == selected_category] if selected_category else df.copy()
        df_f = df_f[(df_f["ano"] >= start_year) & (df_f["ano"] <= end_year)]

        if isinstance(selected_area_state, str): selected_area_state = [selected_area_state]
        if sel_state_modal:   df_f = df_f[df_f["sigla_uf"].isin(sel_state_modal)]
        if selected_area_state: df_f = df_f[df_f["nome"].isin(selected_area_state)]

        area_opts = [{"label": n, "value": n} for n in df_f["nome"].unique()]
        title_text = f"Categoria: {selected_category or 'Todas'}"

        # top 10
        df_f = df_f.drop_duplicates(subset=["name","area_ha","nome","geocodigo","ano"])
        df_ac = (df_f.groupby("nome", as_index=False)
                      .agg({"area_ha":"sum","name":"first"})
                      .sort_values("area_ha", ascending=False).head(10))

        # BAR
        colors = ["darkcyan" if n in selected_areas_store else "lightgray" for n in df_ac["nome"]]
        bar = go.Figure(go.Bar(
            y=df_ac["nome"], x=df_ac["area_ha"], orientation="h", marker_color=colors,
            text=[f"{v:.2f} ha" for v in df_ac["area_ha"]], textposition="auto",
            customdata=df_ac["name"],
            hovertemplate="<b>Área:</b> %{x:.2f} ha<br><b>Município:</b> %{y}<br>"
                          "<b>Imóvel Rural:</b> %{customdata}<extra></extra>"
        ))
        bar.update_layout(
            title=dict(text=f"Área Acumulada de Exploração Madeireira <br>- Imóveis Rurais Privados<br>{title_text}",
                       x=0.5, font=dict(size=12)),
            xaxis_title="Hectares (ha)", yaxis_title="Área de Interesse", bargap=0.1,
            yaxis=dict(categoryorder="array", categoryarray=df_ac.sort_values("area_ha")["nome"]),
            margin=dict(l=0,r=0,t=60,b=0))

        # MAP
        roi_sel = roi[roi["nome"].isin(selected_areas_store or df_ac["nome"])]
        lat, lon, zoom = (-14,-55,4) if not selected_area_state else (*get_centroid(roi, selected_area_state[0]),6)
        mapa = px.choropleth_mapbox(df_ac, geojson=roi_sel, color="area_ha", locations="nome",
                                    featureidkey="properties.nome", mapbox_style="carto-positron",
                                    center={"lat":lat,"lon":lon}, zoom=zoom,
                                    color_continuous_scale="YlOrRd",
                                    hover_data={"nome":True,"name":True,"area_ha":True})
        mapa.update_layout(coloraxis_colorbar_title="Hectares",
                           title=dict(text=f"Mapa de Exploração Madeireira (ha) - Imóveis Rurais Privados<br>{title_text}",
                                      x=0.5),
                           margin=dict(l=0,r=0,t=50,b=0))

        # LINE
        areas = selected_areas_store or df_ac["nome"]
        df_line = (df_f[df_f["nome"].isin(areas)]
                   .groupby(["ano","nome"])["area_ha"].sum().reset_index())
        df_line_full = preencher_anos_faltantes(df_line, sorted(df_f["ano"].unique()), areas)
        line = px.line(df_line_full, x="ano", y="area_ha", color="nome",
                       title=f"Série Histórica <br>de Área de Exploração Madeireira <br> Imóveis Rurais Privados<br>{title_text}",
                       labels={"area_ha":"Área por ano (ha)","ano":"Ano"},
                       template="plotly_white")
        line.update_traces(mode="lines+markers")
        line.update_layout(xaxis_title="Ano", yaxis_title="Área por ano (ha)",
                           legend=dict(orientation="h", x=0.5, y=-0.2,
                                       xanchor="center", yanchor="top"),
                           title_x=0.5, margin=dict(l=0,r=0,t=60,b=0))

        return (bar, mapa, line,
                selected_states, sel_state_modal,
                selected_area_state, area_opts, None, selected_areas_store)

    # ---------- callbacks de modais e download (inalterados) ----------
    @app.callback(Output("state-modal","is_open"),
                  [Input("open-state-modal-button","n_clicks"),
                   Input("close-state-modal-button","n_clicks")],
                  State("state-modal","is_open"))
    def toggle_state_modal(n1,n2,is_open): return not is_open if n1 or n2 else is_open

    @app.callback(Output("area-modal","is_open"),
                  [Input("open-area-modal-button","n_clicks"),
                   Input("close-area-modal-button","n_clicks")],
                  State("area-modal","is_open"))
    def toggle_area_modal(n1,n2,is_open): return not is_open if n1 or n2 else is_open

    @app.callback(Output("modal","is_open"),
                  [Input("open-modal-button","n_clicks"),
                   Input("close-modal-button","n_clicks")],
                  State("modal","is_open"))
    def toggle_modal(n1,n2,is_open): return not is_open if n1 or n2 else is_open

    @app.callback(Output("download-dataframe-csv","data"),
                  Input("download-button","n_clicks"),
                  [State("state-checklist","value"),
                   State("decimal-separator","value"),
                   State("remove-accents","value")],
                  prevent_initial_call=True)
    def download_csv(n_clicks, sel_states, sep, rm_acc):
        if not n_clicks: return dash.no_update
        filtered = df[df["sigla_uf"].isin(sel_states)] if sel_states else df.copy()
        if rm_acc: filtered = filtered.applymap(lambda x: unidecode.unidecode(x) if isinstance(x,str) else x)
        return dcc.send_data_frame(filtered.to_csv, "simex_imoveis_rurais.csv",
                                   sep=sep, index=False)

    return app
