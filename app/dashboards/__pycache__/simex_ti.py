"""
Dashboard SIMEX – Exploração madeireira em Terras Indígenas (TI)
Rota: /simex_ti/
"""

# --------------------------------------------------------------- imports
import io, os, tempfile, requests, dash, unidecode
import pandas as pd
import geopandas as gpd
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
from dash import html, dcc, Input, Output, State, callback_context

HEADERS = {"User-Agent": "Mozilla/5.0"}

# ------------------------------------------------ helpers de download
def _tmp_from_url(url, suffix):
    r = requests.get(url, headers=HEADERS, timeout=60, stream=True)
    r.raise_for_status()
    fh = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    for chunk in r.iter_content(1024 * 1024):
        fh.write(chunk)
    fh.close()
    return fh.name


def try_read_geojson(url):
    try:
        return gpd.read_file(url)
    except Exception:
        try:
            path = _tmp_from_url(url, ".geojson")
            gdf = gpd.read_file(path)
            os.unlink(path)
            return gdf
        except Exception as e:
            print(f"[GeoJSON] falhou em {url}: {e}")
            return None


def try_read_parquet(url):
    try:
        return pd.read_parquet(url)
    except Exception:
        try:
            buf = io.BytesIO(requests.get(url, headers=HEADERS, timeout=60).content)
            return pd.read_parquet(buf)
        except Exception as e:
            print(f"[Parquet] falhou em {url}: {e}")
            return None


def fix_txt(v):
    if not isinstance(v, str):
        return v
    try:
        return v.encode("latin1").decode("utf-8")
    except UnicodeDecodeError:
        return v


# ------------------------------------------------ fontes de dados
GEOJSON_URLS = [
    "https://raw.githubusercontent.com/imazon-cgi/simex/main/datasets/geojson/simex_amazonia_PAMT2007_2023_TI.geojson",
    "https://cdn.jsdelivr.net/gh/imazon-cgi/simex@main/datasets/geojson/simex_amazonia_PAMT2007_2023_TI.geojson",
]

PARQUET_URLS = [
    "https://raw.githubusercontent.com/imazon-cgi/simex/main/datasets/csv/simex_amazonia_PAMT2007_2023_TI.parquet",
    "https://cdn.jsdelivr.net/gh/imazon-cgi/simex@main/datasets/csv/simex_amazonia_PAMT2007_2023_TI.parquet",
]

roi = next((g for u in GEOJSON_URLS if (g := try_read_geojson(u)) is not None), None)
if roi is None:
    raise RuntimeError("Falha ao baixar GeoJSON de TI.")

df = next((d for u in PARQUET_URLS if (d := try_read_parquet(u)) is not None), None)
if df is None:
    raise RuntimeError("Falha ao baixar Parquet de TI.")

# ------------------------------------------------ pré-processamento
for col in ("terrai_nom",):
    if col in roi.columns:
        roi[col] = roi[col].map(fix_txt)
    if col in df.columns:
        df[col] = df[col].map(fix_txt)

df["ano"] = pd.to_numeric(df["ano"], errors="coerce").fillna(0).astype(int)

list_states = sorted(df["sigla_uf"].dropna().unique())
list_years = sorted(df["ano"].unique())

state_options = [{"label": s, "value": s} for s in list_states]
year_options = [{"label": y, "value": y} for y in list_years]
category_options = [
    {"label": "Não autorizada", "value": "não autorizada"},
    {"label": "Autorizada", "value": "autorizada"},
    {"label": "Análise", "value": "análise"},
    {"label": "Todas", "value": None},
]

# =============================================================================
def register_simex_ti_dashboard(server):
    """Registra o painel em /simex_ti/."""
    app = dash.Dash(
        __name__,
        server=server,
        url_base_pathname="/simex_ti/",
        external_stylesheets=[
            dbc.themes.BOOTSTRAP,
            "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css",
        ],
        suppress_callback_exceptions=True,
    )

    # ------------------------------ layout ---------------------------------
    app.layout = dbc.Container(
        [
            html.Meta(name="viewport", content="width=device-width, initial-scale=1"),
            dbc.Row(
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody(
                            [
                                dbc.Row(
                                    [
                                        dbc.Col(
                                            dbc.Button(
                                                [html.I(className="fa fa-filter mr-1"), "Remover Filtros"],
                                                id="reset-button-top",
                                                n_clicks=0,
                                                color="primary",
                                                className="btn-sm custom-button",
                                            ),
                                            width="auto",
                                        ),
                                        dbc.Col(
                                            dbc.Button(
                                                [html.I(className="fa fa-map mr-1"), "Selecione o Estado"],
                                                id="open-state-modal-button",
                                                className="btn btn-secondary btn-sm custom-button",
                                            ),
                                            width="auto",
                                        ),
                                        dbc.Col(
                                            dbc.Button(
                                                [html.I(className="fa fa-map mr-1"), "Selecionar Área de Interesse"],
                                                id="open-area-modal-button",
                                                className="btn btn-secondary btn-sm custom-button",
                                            ),
                                            width="auto",
                                        ),
                                        dbc.Col(
                                            dbc.Button(
                                                [html.I(className="fa fa-download mr-1"), "Baixar CSV"],
                                                id="open-modal-button",
                                                className="btn btn-secondary btn-sm custom-button",
                                            ),
                                            width="auto",
                                        ),
                                    ],
                                    justify="end",
                                ),
                                dcc.Download(id="download-dataframe-csv"),
                            ]
                        ),
                        className="mb-4 title-card",
                    ),
                    width=12,
                )
            ),
            # ------------- filtros ano ---------------------------------------
            dbc.Row(
                [
                    dbc.Col(html.Label("Ano Inicial:"), width="auto", className="d-flex align-items-center"),
                    dbc.Col(
                        dcc.Dropdown(id="start-year-dropdown", options=year_options, value=2016, clearable=False),
                        width=4,
                    ),
                    dbc.Col(html.Label("Ano Final:"), width="auto", className="d-flex align-items-center"),
                    dbc.Col(
                        dcc.Dropdown(id="end-year-dropdown", options=year_options, value=2023, clearable=False),
                        width=4,
                    ),
                    dbc.Col(
                        dbc.Button(
                            [html.I(className="fa fa-refresh mr-1"), "Atualizar Intervalo"],
                            id="refresh-button",
                            n_clicks=0,
                            color="success",
                            className="btn-sm custom-button",
                        ),
                        width="auto",
                    ),
                ],
                className="mb-4 align-items-center",
            ),
            # ------------- categoria -----------------------------------------
            dbc.Row(
                [
                    dbc.Col(html.Label("Categoria:"), width="auto", className="d-flex align-items-center"),
                    dbc.Col(
                        dcc.Dropdown(id="category-dropdown", options=category_options, value=None, clearable=False),
                        width=4,
                    ),
                ],
                className="mb-4 align-items-center",
            ),
            # ------------- gráficos ------------------------------------------
            dbc.Row(
                [
                    dbc.Col(dbc.Card(dcc.Graph(id="bar-graph-yearly"), className="graph-block"), width=12, lg=6),
                    dbc.Col(dbc.Card(dcc.Graph(id="choropleth-map"), className="graph-block"), width=12, lg=6),
                ],
                className="mb-4",
            ),
            dbc.Row(dbc.Col(dbc.Card(dcc.Graph(id="line-graph"), className="graph-block"), width=12), className="mb-4"),
            # ------------- stores --------------------------------------------
            dcc.Store(id="selected-states", data=[]),
            dcc.Store(id="selected-area", data=[]),
            dcc.Store(id="selected-areas-store", data=[]),
            # ------------- modais --------------------------------------------
            dbc.Modal(
                [
                    dbc.ModalHeader(dbc.ModalTitle("Escolha Estados")),
                    dbc.ModalBody(
                        dcc.Dropdown(options=state_options, id="state-dropdown-modal", placeholder="Selecione", multi=True)
                    ),
                    dbc.ModalFooter(dbc.Button("Fechar", id="close-state-modal-button", color="danger")),
                ],
                id="state-modal",
                is_open=False,
            ),
            dbc.Modal(
                [
                    dbc.ModalHeader(dbc.ModalTitle("Escolha Terras Indígenas")),
                    dbc.ModalBody(
                        dcc.Dropdown(id="area-dropdown", placeholder="Selecione", multi=True)
                    ),
                    dbc.ModalFooter(dbc.Button("Fechar", id="close-area-modal-button", color="danger")),
                ],
                id="area-modal",
                is_open=False,
            ),
            dbc.Modal(
                [
                    dbc.ModalHeader(dbc.ModalTitle("Configurações CSV")),
                    dbc.ModalBody(
                        [
                            dbc.Checklist(options=state_options, id="state-checklist", inline=True),
                            html.Hr(),
                            dbc.RadioItems(
                                options=[{"label": "Ponto", "value": "."}, {"label": "Vírgula", "value": ","}],
                                value=".",
                                id="decimal-separator",
                                inline=True,
                            ),
                            dbc.Checkbox(label="Sem acentuação", id="remove-accents", value=False),
                        ]
                    ),
                    dbc.ModalFooter(
                        [
                            dbc.Button("Download", id="download-button", color="success"),
                            dbc.Button("Fechar", id="close-modal-button", color="danger"),
                        ]
                    ),
                ],
                id="modal",
                is_open=False,
            ),
        ],
        fluid=True,
    )

    # ------------------------------ utils ----------------------------------
    def preencher(df_local, anos, areas):
        g = df_local.groupby(["ano", "terrai_nom"], as_index=False).sum()
        full = pd.MultiIndex.from_product([anos, areas], names=["ano", "terrai_nom"])
        return g.set_index(["ano", "terrai_nom"]).reindex(full, fill_value=0).reset_index()

    def centroid(gdf, name):
        try:
            sel = gdf[gdf["terrai_nom"] == name]
            if not sel.empty:
                c = sel.geometry.centroid.iloc[0]
                return c.y, c.x
        except Exception:
            pass
        return -14, -55

    # ------------------------------ callback principal ----------------------
    @app.callback(
        [
            Output("bar-graph-yearly", "figure"),
            Output("choropleth-map", "figure"),
            Output("line-graph", "figure"),
            Output("selected-states", "data"),
            Output("state-dropdown-modal", "value"),
            Output("selected-area", "data"),
            Output("area-dropdown", "options"),
            Output("area-dropdown", "value"),
            Output("selected-areas-store", "data"),
        ],
        [
            Input("start-year-dropdown", "value"),
            Input("end-year-dropdown", "value"),
            Input("category-dropdown", "value"),
            Input("choropleth-map", "clickData"),
            Input("bar-graph-yearly", "clickData"),
            Input("state-dropdown-modal", "value"),
            Input("area-dropdown", "value"),
            Input("reset-button-top", "n_clicks"),
            Input("refresh-button", "n_clicks"),
        ],
        [
            State("selected-states", "data"),
            State("selected-area", "data"),
            State("selected-areas-store", "data"),
        ],
    )
    def update(
        y0,
        y1,
        cat,
        map_click,
        bar_click,
        state_sel,
        area_sel,
        reset_clicks,
        _r,
        sel_states,
        sel_areas,
        sel_store,
    ):
        trig = callback_context.triggered[0]["prop_id"]

        if trig == "reset-button-top.n_clicks":
            state_sel, sel_states, sel_areas, sel_store, cat, y0, y1 = None, [], [], [], None, 2016, 2023

        if trig == "bar-graph-yearly.clickData" and bar_click:
            area = bar_click["points"][0]["y"]
            sel_store = [a for a in sel_store if a != area] if area in sel_store else sel_store + [area]

        if trig == "choropleth-map.clickData" and map_click:
            area = map_click["points"][0]["location"]
            if area in df["terrai_nom"].values:
                sel_areas = [a for a in sel_areas if a != area] if area in sel_areas else sel_areas + [area]

        if area_sel:
            sel_areas = area_sel

        df_local = df.copy()
        if cat is not None:
            df_local = df_local[df_local["categoria"] == cat]

        df_local = df_local[(df_local["ano"] >= int(y0)) & (df_local["ano"] <= int(y1))]

        if state_sel:
            df_local = df_local[df_local["sigla_uf"].isin(state_sel)]
        if sel_areas:
            df_local = df_local[df_local["terrai_nom"].isin(sel_areas)]

        area_opts = [{"label": a, "value": a} for a in df_local["terrai_nom"].unique()]
        title = f"Categoria: {cat or 'Todas'}"

        top = (
            df_local.groupby("terrai_nom")["area_ha"].sum().reset_index().sort_values("area_ha", ascending=False).head(10)
        )
        bar_fig = go.Figure(
            go.Bar(
                y=top["terrai_nom"],
                x=top["area_ha"],
                orientation="h",
                marker_color=["darkcyan" if n in sel_store else "lightgray" for n in top["terrai_nom"]],
                text=[f"{v:.2f} ha" for v in top["area_ha"]],
                textposition="auto",
            )
        )
        bar_fig.update_layout(
            title={"text": f"Área Acumulada de Exploração Madeireira – {title}", "x": 0.5},
            xaxis_title="Hectares (ha)",
            yaxis_title="Terras Indígenas",
            bargap=0.1,
            yaxis=dict(
                categoryorder="array",
                categoryarray=top.sort_values("area_ha", ascending=True)["terrai_nom"].tolist(),
            ),
        )

        roi_sel = roi[roi["terrai_nom"].isin(sel_store or top["terrai_nom"])]
        if sel_areas:
            lat, lon = centroid(roi, sel_areas[0])
            zoom = 6
        else:
            lat, lon, zoom = -14, -55, 4

        map_fig = px.choropleth_mapbox(
            top,
            geojson=roi_sel,
            color="area_ha",
            locations="terrai_nom",
            featureidkey="properties.terrai_nom",
            mapbox_style="carto-positron",
            center={"lat": lat, "lon": lon},
            color_continuous_scale="YlOrRd",
            zoom=zoom,
        )
        map_fig.update_layout(
            coloraxis_colorbar=dict(title="Hectares"),
            margin={"r": 0, "t": 50, "l": 0, "b": 0},
            title={"text": f"Mapa de Exploração Madeireira (ha) – {title}", "x": 0.5},
        )

        areas_plot = sel_store or top["terrai_nom"]
        line = (
            df_local[df_local["terrai_nom"].isin(areas_plot)]
            .groupby(["ano", "terrai_nom"], as_index=False)["area_ha"]
            .sum()
        )
        line_full = preencher(line, sorted(df_local["ano"].unique()), areas_plot)
        line_fig = px.line(
            line_full,
            x="ano",
            y="area_ha",
            color="terrai_nom",
            title=f"Série Histórica de Área de Exploração Madeireira – {title}",
            labels={"area_ha": "Área por ano (ha)", "ano": "Ano"},
            template="plotly_white",
        )
        line_fig.update_traces(mode="lines+markers")
        line_fig.update_layout(yaxis=dict(tickformat=".0f"), title_x=0.5)

        return bar_fig, map_fig, line_fig, sel_states, state_sel, sel_areas, area_opts, None, sel_store

    # -------------------- toggles & download -------------------------------
    for o, c, m in [
        ("open-state-modal-button", "close-state-modal-button", "state-modal"),
        ("open-area-modal-button", "close-area-modal-button", "area-modal"),
        ("open-modal-button", "close-modal-button", "modal"),
    ]:

        @app.callback(Output(m, "is_open"), [Input(o, "n_clicks"), Input(c, "n_clicks")], State(m, "is_open"))
        def _toggle(n1, n2, open_):
            return not open_ if n1 or n2 else open_

    @app.callback(
        Output("download-dataframe-csv", "data"),
        Input("download-button", "n_clicks"),
        State("state-checklist", "value"),
        State("decimal-separator", "value"),
        State("remove-accents", "value"),
        prevent_initial_call=True,
    )
    def download(nc, states, sep, no_acc):
        out = df.copy()
        if states:
            out = out[out["sigla_uf"].isin(states)]
        if no_acc:
            out = out.applymap(lambda v: unidecode.unidecode(v) if isinstance(v, str) else v)
        return dcc.send_data_frame(out.to_csv, "simex_ti.csv", sep=sep, index=False)

    # ----------------------------------------------------------------------
    return app
