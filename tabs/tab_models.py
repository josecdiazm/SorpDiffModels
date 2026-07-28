"""
The Sorption Models tab: pick one or more datasets built in the Data tab, pick a model
(or compare all of them), predict and/or fit, and see the isotherm plot, results table,
and the model's derivation (LaTeX, from the companion derivation notes).
"""

import dash_bootstrap_components as dbc
from dash import dash_table, dcc, html

ELECTRONEUTRALITY_MD = r"Membrane electroneutrality: $$z_g C_g^m + z_c C_c^m + z_A C_A^m = 0$$"

# Order here is also the order models are computed in "Compare all models" mode.
MODEL_REGISTRY = {
    "ideal_donnan": {
        "label": "Ideal Donnan",
        "needs_salt": False,
        "needs_b": False,
        "equation_md": r"""
$$(C_g^m)^{\nu_g}(C_c^m)^{\nu_c} = \nu_g^{\nu_g}\,\nu_c^{\nu_c}\,(C_s^s)^{\nu_g+\nu_c}$$
""",
        "note": "Γ = 1: the membrane is assumed exactly as nonideal as the external "
                "solution. No fitted parameter — always computed directly from the "
                "membrane's fixed-charge concentration and valences.",
    },
    "donnan_manning": {
        "label": "Donnan–Manning (Kamcev et al. 2015/2016)",
        "needs_salt": True,
        "needs_b": True,
        "equation_md": r"""
$$(C_g^m)^{\nu_g}(C_c^m)^{\nu_c} = \frac{(\gamma_\pm^{s})^{\nu_g+\nu_c}}
{(\gamma_g^{m})^{\nu_g}(\gamma_c^{m})^{\nu_c}}\,\nu_g^{\nu_g}\,\nu_c^{\nu_c}\,(C_s^s)^{\nu_g+\nu_c}$$
""",
        "note": r"Membrane activity coefficients $\gamma_g^m,\gamma_c^m$ come from Manning "
                r"counter-ion condensation theory (chain spacing $b$); the external "
                r"$\gamma_\pm^s$ comes from the Pitzer model. Predict with a known $b$, "
                r"and/or fit $b$ to measured Csm,w data.",
    },
    "donnan_manning_modified": {
        "label": "Modified Donnan–Manning (Galizia et al.)",
        "needs_salt": False,
        "needs_b": True,
        "equation_md": r"""
$$(C_g^m)^{\nu_g}(C_c^m)^{\nu_c} = \frac{\nu_g^{\nu_g}\,\nu_c^{\nu_c}\,(C_s^s)^{\nu_g+\nu_c}}
{(\gamma_{g,M}^{m})^{\nu_g}(\gamma_{c,M}^{m})^{\nu_c}}$$
""",
        "note": r"Assumes membrane ions carry all the nonideality they'd have in a "
                r"solution of the same composition, on top of the Manning polymer "
                r"contribution — this cancels $\gamma_\pm^s$ out of the working equation "
                r"entirely, so no salt/Pitzer table is needed here.",
    },
}

MODEL_OPTIONS = [{"label": m["label"], "value": key} for key, m in MODEL_REGISTRY.items()]

_LABEL_STYLE = {"fontSize": "12px", "marginRight": "6px", "fontWeight": "bold"}


def build_equation_content(model_key):
    m = MODEL_REGISTRY[model_key]
    return html.Div([
        dcc.Markdown(m["equation_md"], mathjax=True),
        dcc.Markdown(ELECTRONEUTRALITY_MD, mathjax=True),
        html.P(m["note"], style={"fontSize": "12px", "color": "#666", "marginTop": "6px"}),
    ])


def build_per_dataset_controls(dataset_ids, datasets):
    rows = []
    for ds_id in dataset_ids:
        ds = (datasets or {}).get(ds_id)
        if not ds:
            continue
        rows.append(html.Div([
            html.Span(ds["name"], style={"fontSize": "12px", "fontWeight": "bold",
                                          "width": "180px", "display": "inline-block"}),
            dbc.Checkbox(
                id={"type": "model-predict-check", "index": ds_id},
                label="Predict with a known b", value=False,
                style={"display": "inline-block", "marginRight": "10px"},
            ),
            dcc.Input(
                id={"type": "model-b-input", "index": ds_id},
                type="number", placeholder="b (Å)", step="any",
                style={"width": "90px", "display": "none"},
            ),
        ], style={"display": "flex", "alignItems": "center", "marginBottom": "6px"}))
    if not rows:
        rows = [html.Span("Select one or more datasets above.",
                           style={"fontSize": "12px", "color": "#888"})]
    return rows


layout = dbc.Container(
    fluid=True,
    className="mt-3",
    children=[
        dbc.Card(dbc.CardBody([
            html.Div([
                html.Span("Datasets:", style=_LABEL_STYLE),
                dcc.Dropdown(id="model-dataset-picker", options=[], value=[], multi=True,
                             style={"flex": "1", "minWidth": "320px"}),
            ], style={"display": "flex", "alignItems": "center", "gap": "8px",
                      "marginBottom": "10px"}),

            html.Div([
                html.Span("Model:", style=_LABEL_STYLE),
                dbc.Select(id="model-select", options=MODEL_OPTIONS, value="ideal_donnan",
                           size="sm", style={"width": "340px", "marginRight": "20px"}),
                dbc.Checkbox(id="model-compare-check", value=False,
                             label="Compare all models"),
            ], style={"display": "flex", "alignItems": "center", "marginBottom": "10px"}),

            html.Div("Per-dataset settings (unchecked = fit b from measured data)",
                      style={"fontWeight": "bold", "fontSize": "13px", "marginBottom": "4px"}),
            html.Div(id="model-per-dataset-controls",
                      children=build_per_dataset_controls([], {})),

            dbc.Button("Run Models", id="model-run-btn", color="primary", size="sm",
                       className="mt-2"),
        ]), className="mb-3"),

        dbc.Card(dbc.CardBody([
            dbc.Button("Show/Hide Derivation", id="model-eq-toggle-btn", color="secondary",
                       outline=True, size="sm", className="mb-2"),
            dbc.Collapse(
                id="model-eq-collapse", is_open=False,
                children=html.Div(build_equation_content("ideal_donnan"), id="model-eq-content"),
            ),
        ]), className="mb-3"),

        dbc.Card(dbc.CardBody([
            html.Div(id="model-alert"),
            dcc.Graph(id="model-plot", style={"height": "560px"},
                      config={"displayModeBar": True}),
        ]), className="mb-3"),

        dbc.Card(dbc.CardBody([
            html.Div(id="model-results-table"),
        ]), className="mb-3"),
    ],
)
