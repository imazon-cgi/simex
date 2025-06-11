# app/dashboards/simex_uc.py
"""
Dashboard – SIMEX • Exploração Madeireira em Unidades de Conservação
Rota Flask: /simex/uc/
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
def _temp(url: str, suf: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=45, stream=True); r.raise_for_status()
    f = tempfile.NamedTemporaryFile(delete=False, suffix=suf)
    for ch in r.iter_content(1024 * 1024): f.write(ch)
    f.close(); return f.name

def read_geo(url: str):
    try: return gpd.read_file(url)
    except Exception:
        try:
            p = _temp(url, ".geojson"); g = gpd.read_file(p)
            os.unlink(p); return g
        except Exception: return None

def read_parq(url: str):
    try: return pd.read_parquet(url)
    except Exception:
        try:
            buf = io.BytesIO(requests.get(url, headers=HEADERS, timeout=45).content)
            return pd.read_parquet(buf)
        except Exception: return None

# ───────────────────────── dados ──────────────────────────
GEO = (
    "https://cdn.jsdelivr.net/gh/imazon-cgi/simex@main/"
    "datasets/geojson/simex_amazonia_PAMT2007_2023_UC.geojson"
)
PARQ = (
    "https://cdn.jsdelivr.net/gh/imazon-cgi/simex@main/"
    "datasets/csv/simex_amazonia_PAMT2007_2023_UC.parquet"
)

roi = read_geo(GEO)
roi["nome_1"] = roi["nome_1"].str.encode("latin1","ignore").str.decode("utf-8","ignore")
df  = read_parq(PARQ)
df["nome_1"] = (df["nome_1"].str.encode("latin1","ignore")
                               .str.decode("utf-8","ignore")
                               .astype(str))

list_states = df["sigla_uf"].unique()
list_anual  = sorted(df["ano"].unique())
state_options = [{"label": s, "value": s} for s in list_states]
year_options  = [{"label": a, "value": a} for a in list_anual]

category_options = [
    {"label":"Não autorizada","value":"não autorizada"},
    {"label":"Autorizada","value":"autorizada"},
    {"label":"Análise","value":"análise"},
    {"label":"Todas","value":None},
]

# ───────────────────── CSS global ─────────────────────
GLOBAL_CSS = """
/* rótulos (‘Ano Inicial’, etc.) ocupam apenas o necessário */
.label-fit{
  white-space:nowrap;
  font-weight:600;
  font-size:.86rem;
}

/* botões verdes – sem sombra extra */
.custom-button{box-shadow:none!important}

/*
  Cada card (.graph-block) vira flex-container.
  O dcc.Graph dentro dele cresce e o Plotly RECEBE altura 100 %.
*/
.graph-block{
  min-height:380px;        /* base desktop */
  display:flex;
  flex-direction:column;
}
.graph-block .dash-graph{
  flex:1 1 auto;
  width:100%!important;
}
/* força o elemento plotly interno a ocupar toda a altura */
.graph-block .dash-graph .js-plotly-plot{
  height:100%!important;
}

/* Telas estreitas (< 576 px) – aumenta altura mínima */
@media (max-width:576px){
  /* cards comuns */
  .graph-block{min-height:420px}
  /* se quiser donuts ainda maiores, só descomentar: */
  /* .graph-block .js-plotly-plot{min-height:450px} */
}
"""


# ╭──────────────────────────────────────────────────────────╮
# │ Registro do dashboard                                   │
# ╰──────────────────────────────────────────────────────────╯
def register_simex_uc_dashboard(server):
    app = dash.Dash(
        __name__, server=server, url_base_pathname="/simex/uc/",
        external_stylesheets=[dbc.themes.BOOTSTRAP,
                              "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css"],
        suppress_callback_exceptions=True,
        title="SIMEX – UCs",
    )

    # injeção de CSS
    app.clientside_callback(
        f"""function(x){{const t=document.createElement('style');
                        t.innerHTML={repr(GLOBAL_CSS)};
                        document.head.appendChild(t);return null}}""",
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
                        xs=12, className="mb-4")
            ]),
            dbc.Row([
                dbc.Col(dbc.Card(dcc.Graph(id="pie-chart",
                                           config={"responsive": True}),
                                 className="graph-block shadow-sm"),
                        xs=12, lg=6, className="mb-4"),
                dbc.Col(dbc.Card(dcc.Graph(id="pie-chart-uf-esfera",
                                           config={"responsive": True}),
                                 className="graph-block shadow-sm"),
                        xs=12, lg=6, className="mb-4"),
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
                    dcc.Dropdown(id="state-dropdown-modal",
                                 options=state_options,
                                 placeholder="Selecione o(s) Estado(s)",
                                 multi=True)
                ),
                dbc.ModalFooter(
                    dbc.Button("Fechar", id="close-state-modal-button",
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
                    dbc.Button("Fechar", id="close-area-modal-button",
                               color="danger")
                )
            ], id="area-modal", is_open=False, size="lg", scrollable=True),

            dbc.Modal([
                dbc.ModalHeader(dbc.ModalTitle("Configurações para gerar o CSV")),
                dbc.ModalBody([
                    dbc.Checklist(options=state_options, id="state-checklist",
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
        idx = pd.MultiIndex.from_product([anos, areas], names=["ano","nome_1"])
        return (df_in.groupby(["ano","nome_1"], as_index=False)["area_ha"]
                  .sum()
                  .set_index(["ano","nome_1"])
                  .reindex(idx, fill_value=0)
                  .reset_index())

    def get_centroid(gjson, nm):
        try:
            g = gjson.loc[gjson["nome_1"] == nm]
            if not g.empty:
                c = g.geometry.centroid.iloc[0]
                return c.y, c.x
        except Exception: pass
        return -14, -55

    # Funções de callback do Dash para atualizar gráficos e manipular filtros e seleção de áreas.
    @app.callback(
        # Define as saídas dos callbacks.
        [Output('bar-graph-yearly', 'figure'),
         Output('choropleth-map', 'figure'),
         Output('line-graph', 'figure'),
         Output('pie-chart', 'figure'),  # Nova saída
         Output('pie-chart-uf-esfera', 'figure'),  # Novo gráfico
         Output('selected-states', 'data'),
         Output('state-dropdown-modal', 'value'),
         Output('selected-area', 'data'),
         Output('area-dropdown', 'options'),
         Output('area-dropdown', 'value'),
         Output('selected-areas-store', 'data')],

        # Define as entradas dos callbacks.
        [Input('start-year-dropdown', 'value'),
         Input('end-year-dropdown', 'value'),
         Input('category-dropdown', 'value'),
         Input('choropleth-map', 'clickData'),
         Input('bar-graph-yearly', 'clickData'),
         Input('state-dropdown-modal', 'value'),
         Input('area-dropdown', 'value'),
         Input('reset-button-top', 'n_clicks'),
         Input('refresh-button', 'n_clicks')],

        # Define os estados dos callbacks.
        [State('selected-states', 'data'),
         State('selected-area', 'data'),
         State('selected-areas-store', 'data')]
    )
    def update_graphs(start_year, end_year, selected_category, map_click_data, bar_click_data, selected_state, selected_area, reset_clicks, refresh_clicks, selected_states, selected_area_state, selected_areas_store):
        """
        Função de callback para atualizar os gráficos e seleções de área de interesse com base nos filtros aplicados.
        """
        # Obtenção do ID do elemento que desencadeou o callback.
        triggered_id = [p['prop_id'] for p in callback_context.triggered][0]

        # Atribuição de valores padrão para o ano inicial e final.
        if start_year is None:
            start_year = 2016
        if end_year is None:
            end_year = 2023

        start_year = int(start_year)  # Converte ano inicial para inteiro.
        end_year = int(end_year)  # Converte ano final para inteiro.

        df['ano'] = df['ano'].astype(int)  # Converte a coluna 'ano' do DataFrame para inteiro.

        # Reseta as seleções ao clicar no botão de reset.
        if triggered_id == 'reset-button-top.n_clicks':
            selected_states = []
            selected_state = None
            selected_area_state = []
            selected_category = None
            start_year = 2016
            end_year = 2023
            selected_areas_store = []

        # Manipulação do clique no gráfico de barras.
        if triggered_id == 'bar-graph-yearly.clickData' and bar_click_data:
            clicked_area = bar_click_data['points'][0]['y']  # Identifica o assentamento clicado.
            if clicked_area in selected_areas_store:
                selected_areas_store.remove(clicked_area)  # Remove a área caso esteja selecionada.
            else:
                selected_areas_store.append(clicked_area)  # Adiciona a área caso não esteja.

        # Manipulação do clique no mapa.
        if triggered_id == 'choropleth-map.clickData' and map_click_data:
            selected_municipio = map_click_data['points'][0]['location']  # Identifica o assentamento clicado no mapa.
            if selected_municipio in df['nome_1'].values:
                if selected_municipio in selected_area_state:
                    selected_area_state.remove(selected_municipio)  # Remove a área caso esteja selecionada.
                else:
                    selected_area_state.append(selected_municipio)  # Adiciona a área caso não esteja.

        # Define a seleção de áreas e categoria com base nos filtros.
        if selected_area:
            selected_area_state = selected_area
        if selected_category:
            if selected_category is not None:
                df_filtered = df[df['categoria'] == selected_category]  # Filtra o DataFrame pela categoria selecionada.
            else:
                df_filtered = df
        else:
            df_filtered = df

        # Filtra o DataFrame pelo intervalo de anos.
        df_filtered = df_filtered[(df_filtered['ano'] >= start_year) & (df_filtered['ano'] <= end_year)]

        # Converte a seleção de áreas para lista.
        if isinstance(selected_area_state, str):
            selected_area_state = [selected_area_state]
        elif selected_area_state is None:
            selected_area_state = []

        # Filtra o DataFrame por estado e áreas selecionadas.
        if selected_state:
            df_filtered = df_filtered[df_filtered['sigla_uf'].isin(selected_state)]
        if selected_area_state:
            df_filtered = df_filtered[df_filtered['nome_1'].isin(selected_area_state)]

        # Define as opções de áreas para o dropdown de áreas de interesse.
        area_options = [{'label': nome_1, 'value': nome_1} for nome_1 in df_filtered['nome_1'].unique()]
        title_text = f"Categoria: {selected_category or 'Todas'}"

        # Seleção das top 10 áreas por ordem decrescente de exploração.
        df_acumulado_municipio = df_filtered.groupby(['nome_1'], as_index=False).agg({
            'area_ha': 'sum',  # Soma as áreas por `nome_1`.
            'nome': 'first'    # Mantém o primeiro valor de `nome` correspondente a cada `nome_1`.
        })
        df_top_10 = df_acumulado_municipio.sort_values(by='area_ha', ascending=False).head(10)

        # Remove caracteres inválidos e normaliza a codificação
        df_top_10['nome_1'] = df_top_10['nome_1'].str.encode('latin1', errors='ignore').str.decode('utf-8', errors='ignore')
        df_top_10['nome_1'] = df_top_10['nome_1'].str.replace(r'[^\x00-\x7F]+', '', regex=True)  # Remove caracteres não-ASCII

         # Truncar os nomes das áreas para até 10 caracteres
        df_top_10['short_nome_1'] = df_top_10['nome_1'].apply(lambda x: x[:10] + '...' if len(x) > 10 else x)

        # Cria o gráfico de barras com top 10 áreas.
        marker_colors = ['darkcyan' if nome in selected_areas_store else 'lightgray' for nome in df_top_10['nome_1']]
        # Cria o gráfico de barras com top 10 áreas.
        bar_yearly_fig = go.Figure(go.Bar(
            y=df_top_10['nome_1'],  # Usa os nomes originais como identificadores.
            x=df_top_10['area_ha'],
            orientation='h',
            marker_color=marker_colors,
            # text=df_top_10['nome'],  # Exibe os nomes truncados como rótulos.
            textposition='auto',
            customdata=df_top_10['nome'],  # Inclui os dados originais como referência para interação.
            hovertemplate=(
                "<b>Área:</b> %{x:.2f} ha<br>"
                "<b>Assentamento:</b> %{y}<br>"  # Mostra o rótulo truncado.
                "<b>Nome completo:</b> %{customdata}"  # Mostra o nome completo.
                "<extra></extra>"
            )
    ))
        # Ajusta o layout do gráfico de barras para exibir valores maiores em cima e configura a legenda.
        bar_yearly_fig.update_layout(
            title={'text': f"Área Acumulada de Exploração Madeireira - {title_text}", 'x': 0.5,"font": {"size": 12}},
            xaxis_title='Hectares (ha)',
            yaxis_title='Área de Interesse',
            bargap=0.1,
            legend=dict(
                orientation="h",  # Configura a orientação da legenda para horizontal
                yanchor="top",  # Alinha ao topo da área de legenda
                y=-0.2,  # Posiciona a legenda abaixo do gráfico
                xanchor="center",  # Centraliza a legenda horizontalmente
                x=0.5,  # Posiciona a legenda no centro da largura do gráfico
                font=dict(
                    size=8  # Ajusta o tamanho da fonte das legendas
                )
            ),
             yaxis=dict(
            categoryorder='array',
            categoryarray=df_top_10.sort_values(by='area_ha', ascending=True)['nome_1'].tolist(),
            tickfont=dict(size=8)  # Reduz o tamanho da fonte
                         ),
        )

        # Mapa com top 10 áreas usando GeoJSON.
        if selected_areas_store:
            roi_selected = roi[roi['nome_1'].isin(selected_areas_store)]
        else:
            roi_selected = roi[roi['nome_1'].isin(df_top_10['nome_1'])]

        # Define o centro do mapa com base na seleção.
        if selected_area_state:
            lat, lon = get_centroid(roi, selected_area_state[0])
            zoom = 6
        else:
            lat, lon = -14, -55
            zoom = 4

        # Configura o mapa coroplético.
        map_fig = px.choropleth_mapbox(
            df_top_10, geojson=roi_selected, color='area_ha',
            locations="nome_1",
            featureidkey="properties.nome_1",
            mapbox_style="carto-positron",
            center={"lat": lat, "lon": lon},
            color_continuous_scale='YlOrRd',
            hover_data={"nome": True, "nome_1": True, "area_ha": True},  # Adiciona 'nome_1' ao tooltip
            zoom=zoom
        )

        # Ajusta o layout do mapa.
        map_fig.update_layout(
            coloraxis_colorbar=dict(title="Hectares"),
            margin={"r": 0, "t": 50, "l": 0, "b": 0},
            title={'text': f"Mapa de Exploração Madeireira (ha) - {title_text}", 'x': 0.5}
        )

        # Gráfico de linha para áreas selecionadas ou top 10.
        if selected_areas_store:
            areas_to_plot = selected_areas_store
        else:
            areas_to_plot = df_top_10['nome_1']

        # Agrupamento de dados para gráfico de linhas.
        df_line = df_filtered[df_filtered['nome_1'].isin(areas_to_plot)].groupby(['ano', 'nome_1', 'sigla_uf'])['area_ha'].sum().reset_index()
        df_line_full = preencher_anos_faltantes(df_line, sorted(df_filtered['ano'].unique()), areas_to_plot)
        line_fig = px.line(df_line_full, x='ano', y='area_ha', color='nome_1',
                        title=f'Série Histórica de Área de Exploração Madeireira - {title_text}',
                        labels={'area_ha': 'Área por ano (ha)', 'ano': 'Ano'},
                        template='plotly_white', line_shape='linear')

        line_fig.update_traces(mode='lines+markers')

        line_fig.update_layout(
            xaxis_title='Ano',
            yaxis_title='Área por ano (ha)',
            font=dict(size=10),
            yaxis=dict(tickformat=".0f"),
            legend_title_text='Assentamento',
            title_x=0.5,
            legend=dict(
                orientation="h",  # Configura a orientação da legenda para horizontal
                yanchor="top",  # Alinha ao topo da área de legenda
                y=-0.2,  # Posiciona a legenda abaixo do gráfico
                xanchor="center",  # Centraliza a legenda horizontalmente
                x=0.5  # Posiciona a legenda no centro da largura do gráfico
            )
    )

        # Agrupar os dados pela coluna 'grupo' e somar as áreas.
        df_grouped = df_filtered.groupby('grupo')['area_ha'].sum().reset_index()

        # Criar o gráfico de pizza.
        pie_fig = px.pie(
            df_grouped,
            names='grupo',
            values='area_ha',
            title=f'Proporção de Áreas Acumuladas por Grupo ({start_year} - {end_year})',
            hole=0.4,  # Gráfico do tipo "donut"
            color_discrete_sequence=px.colors.sequential.RdBu
        )

        # Agrupar os dados por sigla_uf e esfera.
        df_grouped_uf_esfera = df_filtered.groupby(['sigla_uf', 'esfera'])['area_ha'].sum().reset_index()

        # Criar o gráfico de pizza por sigla_uf e esfera.
        pie_fig_uf_esfera = px.pie(
            df_grouped_uf_esfera,
            names='sigla_uf',
            values='area_ha',
            color='esfera',
            title=f'Proporção de Área por Estado e Esfera ({start_year} - {end_year})',
            hole=0.3,  # Gráfico do tipo "donut"
            color_discrete_sequence=px.colors.diverging.RdBu
        )

        # Retorno das figuras e dados para armazenar.
        return bar_yearly_fig, map_fig, line_fig, pie_fig,pie_fig_uf_esfera,selected_states, selected_state, selected_area_state, area_options, None, selected_areas_store


    # Callback para abrir e fechar o modal de seleção de estado.
    @app.callback(
        Output("state-modal", "is_open"),
        [Input("open-state-modal-button", "n_clicks"), Input("close-state-modal-button", "n_clicks")],
        [State("state-modal", "is_open")]
    )
    def toggle_state_modal(n1, n2, is_open):
        if n1 or n2:
            return not is_open
        return is_open

    # Callback para abrir e fechar o modal de seleção de áreas.
    @app.callback(
        Output("area-modal", "is_open"),
        [Input("open-area-modal-button", "n_clicks"), Input("close-area-modal-button", "n_clicks")],
        [State("area-modal", "is_open")]
    )
    def toggle_area_modal(n1, n2, is_open):
        if n1 or n2:
            return not is_open
        return is_open

    # Callback para abrir e fechar o modal de download.
    @app.callback(
        Output("modal", "is_open"),
        [Input("open-modal-button", "n_clicks"), Input("close-modal-button", "n_clicks")],
        [State("modal", "is_open")]
    )
    def toggle_modal(n1, n2, is_open):
        if n1 or n2:
            return not is_open
        return is_open

    # Callback para gerar e fazer download do CSV filtrado.
    @app.callback(
        Output("download-dataframe-csv", "data"),
        [Input("download-button", "n_clicks")],
        [State("state-checklist", "value"), State("decimal-separator", "value"), State("remove-accents", "value")]
    )
    def download_csv(n_clicks, selected_states, decimal_separator, remove_accents):
        if n_clicks is None or n_clicks == 0:
            return dash.no_update

        print(f"Download button clicked {n_clicks} times")
        print(f"Selected States: {selected_states}")

        if selected_states:
            filtered_df = df[df['sigla_uf'].isin(selected_states)]  # Filtra pelo estado selecionado.
        else:
            filtered_df = df

        print(f"Filtered DataFrame shape: {filtered_df.shape}")

        if remove_accents:
            filtered_df = filtered_df.applymap(lambda x: unidecode.unidecode(x) if isinstance(x, str) else x)  # Remove acentos se selecionado.

        return dcc.send_data_frame(filtered_df.to_csv, "degradacao_amazonia.csv", sep=decimal_separator, index=False)


