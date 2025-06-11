# app/dashboards/simex_terra_ndest.py
"""
Dashboard – SIMEX • Exploração Madeireira em Terras Não-Destinadas
Rota Flask: /simex/terra_dest/
"""
from __future__ import annotations
import io, os, tempfile, requests, unidecode

import dash
import dash_bootstrap_components as dbc
import geopandas as gpd
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import html, dcc, Input, Output, State, callback_context

HEADERS = {"User-Agent": "Mozilla/5.0"}

# ───────────────────────── helpers ─────────────────────────
def _tmp(url: str, suf: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=45, stream=True); r.raise_for_status()
    f = tempfile.NamedTemporaryFile(delete=False, suffix=suf)
    for c in r.iter_content(1024 * 1024): f.write(c)
    f.close(); return f.name

def load_geo(url: str):
    try: return gpd.read_file(url)
    except Exception:
        try:
            p = _tmp(url, ".geojson"); gdf = gpd.read_file(p)
            os.unlink(p); return gdf
        except Exception: return None

def load_parquet(url: str):
    try: return pd.read_parquet(url)
    except Exception:
        try:
            buf = io.BytesIO(requests.get(url, headers=HEADERS, timeout=45).content)
            return pd.read_parquet(buf)
        except Exception: return None

# ───────────────────────── dados ──────────────────────────
GJSON = (
    "https://cdn.jsdelivr.net/gh/imazon-cgi/simex@main/"
    "datasets/geojson/simex_amazonia_PAMT2007_2023_TerrasNDest.geojson"
)
PARQUET = (
    "https://cdn.jsdelivr.net/gh/imazon-cgi/simex@main/"
    "datasets/csv/simex_amazonia_PAMT2007_2023_TerrasNDest.parquet"
)

roi = load_geo(GJSON)
roi["name"] = roi["name"].str.encode("latin1", "ignore").str.decode("utf-8", "ignore")
df  = load_parquet(PARQUET)
df["name"] = (df["name"].str.encode("latin1", "ignore")
                        .str.decode("utf-8", "ignore")
                        .astype(str))

list_states = df["sigla_uf"].unique()
list_anual  = sorted(df["ano"].unique())
state_options = [{"label": s, "value": s} for s in list_states]
year_options  = [{"label": a, "value": a} for a in list_anual]

category_options = [
    {"label": "Não autorizada", "value": "não autorizada"},
    {"label": "Autorizada",      "value": "autorizada"},
    {"label": "Análise",         "value": "análise"},
    {"label": "Todas",           "value": None},
]

# ───────────────────── CSS global ─────────────────────
GLOBAL_CSS = """
.label-fit{white-space:nowrap;font-weight:600;font-size:.86rem}
.custom-button{box-shadow:none!important}
.graph-block .dash-graph{width:100%!important;height:100%!important}
.graph-block{min-height:340px}
@media (max-width:576px){.graph-block{min-height:260px}}
"""

# ╭──────────────────────────────────────────────────────────╮
# │ Registro do dashboard                                   │
# ╰──────────────────────────────────────────────────────────╯
def register_simex_terra_dest_dashboard(flask_server):
    app = dash.Dash(
        __name__,
        server=flask_server,
        url_base_pathname="/simex/terra_dest/",
        external_stylesheets=[
            dbc.themes.BOOTSTRAP,
            "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css",
        ],
        suppress_callback_exceptions=True,
        title="SIMEX – Terras N-Destinadas",
    )

    # injeção de CSS
    app.clientside_callback(
        f"""function(x){{const tag=document.createElement('style');
                        tag.innerHTML={repr(GLOBAL_CSS)};
                        document.head.appendChild(tag);return null}}""",
        Output("css-out","children"), Input("css-in","data")
    )

    # ---------------- layout ----------------
    app.layout = html.Div([
        dcc.Store(id="css-in", data=0), html.Div(id="css-out"),

        dbc.Container([
            html.Meta(name="viewport",
                      content="width=device-width, initial-scale=1"),

            # ───── linha de controles ─────
            dbc.Row([
                dbc.Col(html.Label("Ano Inicial:", className="label-fit"),
                        xs="auto", className="d-flex align-items-center"),
                dbc.Col(dcc.Dropdown(id="start-year-dropdown",
                                     options=year_options, value=2016,
                                     clearable=False),
                        xs=12, sm=6, md=3, lg=3),

                dbc.Col(html.Label("Ano Final:", className="label-fit"),
                        xs="auto", className="d-flex align-items-center"),
                dbc.Col(dcc.Dropdown(id="end-year-dropdown",
                                     options=year_options, value=2023,
                                     clearable=False),
                        xs=12, sm=6, md=3, lg=3),

                dbc.Col(dbc.Button([html.I(className="fa fa-refresh me-1"),
                                    "Atualizar Intervalo"],
                                   id="refresh-button", n_clicks=0,
                                   color="success",
                                   className="btn-sm custom-button"),
                        xs="auto",
                        className="d-flex align-items-center justify-content-end mt-2 mt-md-0"),

                dbc.Col(dbc.Button([html.I(className="fa fa-filter me-1"),
                                    "Remover Filtros"],
                                   id="reset-button-top", n_clicks=0,
                                   color="success",
                                   className="btn-sm custom-button"),
                        xs="auto", className="d-flex align-items-center mt-2 mt-md-0"),

                dbc.Col(dbc.Button([html.I(className="fa fa-map me-1"),
                                    "Selecione o Estado"],
                                   id="open-state-modal-button",
                                   color="success",
                                   className="btn-sm custom-button"),
                        xs="auto", className="d-flex align-items-center mt-2 mt-md-0"),

                dbc.Col(dbc.Button([html.I(className="fa fa-map me-1"),
                                    "Selecionar Área de Interesse"],
                                   id="open-area-modal-button",
                                   color="success",
                                   className="btn-sm custom-button"),
                        xs="auto", className="d-flex align-items-center mt-2 mt-md-0"),

                dbc.Col(dbc.Button([html.I(className="fa fa-download me-1"),
                                    "Baixar CSV"],
                                   id="open-modal-button",
                                   color="success",
                                   className="btn-sm custom-button"),
                        xs="auto", className="d-flex align-items-center mt-2 mt-md-0"),
            ], className="gx-2 mb-3 flex-wrap"),

            # categoria
            dbc.Row([
                dbc.Col(html.Label("Categoria:", className="label-fit"),
                        xs="auto", className="d-flex align-items-center"),
                dbc.Col(dcc.Dropdown(id="category-dropdown",
                                     options=category_options,
                                     value=None, clearable=False),
                        xs=12, sm=6, md=4, lg=3),
            ], className="gx-2 mb-4"),

            # ───── gráficos ─────
            dbc.Row([
                dbc.Col(dbc.Card(dcc.Graph(id="bar-graph-yearly",
                                           config={"responsive": True}),
                                 className="graph-block shadow-sm"),
                        xs=12, lg=6, className="mb-4"),
                dbc.Col(dbc.Card(dcc.Graph(id="choropleth-map",
                                           config={"responsive": True}),
                                 className="graph-block shadow-sm"),
                        xs=12, lg=6, className="mb-4"),
            ]),
            dbc.Row([
                dbc.Col(dbc.Card(dcc.Graph(id="line-graph",
                                           config={"responsive": True}),
                                 className="graph-block shadow-sm"),
                        xs=12, className="mb-4"),
            ]),

            # stores + download
            dcc.Store(id="selected-states",      data=[]),
            dcc.Store(id="selected-area",        data=[]),
            dcc.Store(id="selected-areas-store", data=[]),
            dcc.Download(id="download-dataframe-csv"),

            # ──────── MODAIS ────────
            dbc.Modal([
                dbc.ModalHeader(dbc.ModalTitle("Escolha Estados")),
                dbc.ModalBody(
                    dcc.Dropdown(options=state_options,
                                 id="state-dropdown-modal",
                                 placeholder="Selecione o(s) Estado(s)",
                                 multi=True)
                ),
                dbc.ModalFooter(
                    dbc.Button("Fechar",
                               id="close-state-modal-button",
                               color="danger")
                )
            ], id="state-modal", is_open=False, size="lg", scrollable=True),

            dbc.Modal([
                dbc.ModalHeader(dbc.ModalTitle("Escolha as Áreas de Interesse")),
                dbc.ModalBody(
                    dcc.Dropdown(id="area-dropdown",
                                 placeholder="Selecione as Áreas",
                                 multi=True)
                ),
                dbc.ModalFooter(
                    dbc.Button("Fechar",
                               id="close-area-modal-button",
                               color="danger")
                )
            ], id="area-modal", is_open=False, size="lg", scrollable=True),

            dbc.Modal([
                dbc.ModalHeader(dbc.ModalTitle("Configurações para gerar o CSV")),
                dbc.ModalBody([
                    dbc.Checklist(options=state_options,
                                  id="state-checklist",
                                  inline=True),
                    html.Hr(),
                    dbc.RadioItems(options=[{"label":"Ponto","value":"."},
                                            {"label":"Vírgula","value":","}],
                                   value=".", id="decimal-separator",
                                   inline=True, className="mb-2"),
                    dbc.Checkbox(label="Sem acentuação",
                                 id="remove-accents", value=False)
                ]),
                dbc.ModalFooter([
                    dbc.Button("Download", id="download-button", color="success"),
                    dbc.Button("Fechar", id="close-modal-button", color="danger")
                ])
            ], id="modal", is_open=False, size="lg", scrollable=True),
        ], fluid=True)
    ])

    # ───────── auxiliares ─────────
    def preencher_anos_faltantes(df_in, anos, areas):
        idx = pd.MultiIndex.from_product([anos, areas], names=["ano","name"])
        return (df_in.groupby(["ano","name"], as_index=False)["area_ha"]
                   .sum()
                   .set_index(["ano","name"])
                   .reindex(idx, fill_value=0)
                   .reset_index())

    def get_centroid(gjson, nm):
        try:
            g = gjson.loc[gjson["name"] == nm]
            if not g.empty:
                c = g.geometry.centroid.iloc[0]
                return c.y, c.x
        except Exception: pass
        return -14, -55

    # ───────── callback principal ─────────
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
         State("selected-areas-store","data")]
    )
    def update_graphs(sy, ey, cat,
                      map_click, bar_click,
                      modal_states, modal_areas,
                      reset, refresh,
                      st_store, ar_store, areas_sel):

        trig = callback_context.triggered[0]["prop_id"]

        sy = int(sy or 2016); ey = int(ey or 2023)
        df["ano"] = df["ano"].astype(int)

        # reset
        if trig.startswith("reset-button-top"):
            st_store, modal_states = [], None
            ar_store, areas_sel    = [], []
            cat, sy, ey            = None, 2016, 2023

        # clique barra
        if trig.startswith("bar-graph-yearly") and bar_click:
            area = bar_click["points"][0]["y"]
            areas_sel = [a for a in areas_sel if a != area] if area in areas_sel else areas_sel + [area]

        # clique mapa
        if trig.startswith("choropleth-map") and map_click:
            area = map_click["points"][0]["location"]
            ar_store = [a for a in ar_store if a != area] if area in ar_store else ar_store + [area]

        # filtros
        dff = df.copy()
        if cat: dff = dff[dff["categoria"] == cat]
        dff = dff[(dff["ano"]>=sy)&(dff["ano"]<=ey)]
        if modal_states: dff = dff[dff["sigla_uf"].isin(modal_states)]
        if ar_store:     dff = dff[dff["name"].isin(ar_store)]

        area_opts = [{"label":n,"value":n} for n in dff["name"].unique()]

        # top-10
        top10 = (dff.groupby("name", as_index=False)
                   .agg(area_ha=("area_ha","sum"))
                   .sort_values("area_ha", ascending=False)
                   .head(10))
        top10["name"] = (top10["name"]
                         .str.encode("latin1","ignore")
                         .str.decode("utf-8","ignore")
                         .str.replace(r"[^\x00-\x7F]+","",regex=True))

        sel_set = set(areas_sel)
        colors  = ["darkcyan" if n in sel_set else "lightgray"
                   for n in top10["name"]]

        bar = go.Figure(go.Bar(
            y=top10["name"], x=top10["area_ha"],
            orientation="h", marker_color=colors,
            hovertemplate="<b>%{y}</b><br>Área: %{x:.2f} ha<extra></extra>"
        ))
        bar.update_layout(
            title_text=f"Área Acumulada de Exploração Madeireira - {cat or 'Todas'}",
            title_x=0.5, autosize=True,
            xaxis_title="Hectares (ha)",
            yaxis_title="Área de Interesse",
            yaxis=dict(categoryorder="array",
                       categoryarray=top10.sort_values("area_ha")["name"]),
            bargap=.1, margin_t=50, font_size=10,
            legend_orientation="h", legend_y=-0.2
        )

        # mapa
        roi_sel = roi[roi["name"].isin(sel_set or top10["name"])]
        lat,lon = (get_centroid(roi, (ar_store or top10["name"])[0])
                   if ar_store else (-14,-55))
        zoom = 6 if ar_store else 4
        map_fig = px.choropleth_mapbox(
            top10, geojson=roi_sel, color="area_ha",
            locations="name", featureidkey="properties.name",
            mapbox_style="carto-positron",
            center={"lat":lat,"lon":lon},
            zoom=zoom,
            color_continuous_scale="YlOrRd",
            hover_data={"name":True,"area_ha":":.2f"},
        )
        map_fig.update_layout(
            autosize=True,
            margin_r=0, margin_l=0, margin_b=0,
            title={"text":f"Mapa <br> Exploração Madeireira (ha) - {cat or 'Todas'}",
                   "x":0.5},
        )

        # linha
        focus = areas_sel if areas_sel else top10["name"]
        dfl = (dff[dff["name"].isin(focus)]
               .groupby(["ano","name"])["area_ha"].sum().reset_index())
        dfl = preencher_anos_faltantes(dfl, range(sy,ey+1), focus)
        line = px.line(
            dfl, x="ano", y="area_ha", color="name",
            labels={"area_ha":"Área (ha)","ano":"Ano"},
            template="plotly_white",
        )
        line.update_traces(mode="lines+markers")
        line.update_layout(
            autosize=True,
            title_text=f"Série Histórica <br> Área de Exploração Madeireira - {cat or 'Todas'}",
            title_x=0.5,
            yaxis_tickformat=".0f",
            legend_orientation="h",
            legend_y=-0.2,
        )

        return bar, map_fig, line, st_store, modal_states, ar_store, \
               area_opts, None, areas_sel

    # ───────── modais & download ─────────
    for _open,_close,_modal in [
        ("open-state-modal-button","close-state-modal-button","state-modal"),
        ("open-area-modal-button", "close-area-modal-button", "area-modal"),
        ("open-modal-button",      "close-modal-button",      "modal")
    ]:
        @app.callback(Output(_modal,"is_open"),
                      [Input(_open,"n_clicks"),Input(_close,"n_clicks")],
                      State(_modal,"is_open"))
        def toggle_modal(n1,n2,is_open):
            if n1 or n2: return not is_open
            return is_open

    @app.callback(
        Output("download-dataframe-csv","data"),
        Input("download-button","n_clicks"),
        State("state-checklist","value"),
        State("decimal-separator","value"),
        State("remove-accents","value"))
    def download_csv(n, states, dec, rm_acc):
        if not n: return dash.no_update
        dff = df if not states else df[df["sigla_uf"].isin(states)]
        if rm_acc:
            dff = dff.applymap(lambda x: unidecode.unidecode(x)
                               if isinstance(x,str) else x)
        return dcc.send_data_frame(dff.to_csv,
                                   "degradacao_amazonia.csv",
                                   sep=dec, index=False)

    return app
