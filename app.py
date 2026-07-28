
import dash
import dash_bootstrap_components as dbc
from dash import html

# ── Tab layouts ───────────────────────────────────────────────────────────────
from tabs.tab_data import layout as data_layout

# ── Register callbacks ────────────────────────────────────────────────────────
import callbacks.callbacks_data

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.FLATLY],
    suppress_callback_exceptions=True,
)

app.title = "Sorption & Diffusion Models"

app.layout = dbc.Container(
    fluid=True,
    className="pb-4",
    children=[
        dbc.Row(
            dbc.Col(
                html.H2(
                    "Sorption & Diffusion Models",
                    className="text-center my-3"
                )
            )
        ),
        dbc.Tabs(
            id="main-tabs",
            active_tab="tab-data",
            children=[
                dbc.Tab(label="Data", tab_id="tab-data", children=data_layout),
            ],
        ),
    ],
)

if __name__ == "__main__":
    app.run(debug=True, port=8060)
