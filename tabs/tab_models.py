"""
The Sorption Models tab: pick one or more datasets built in the Data tab, pick a model
(or compare all of them), predict and/or fit, and see the isotherm plot, results table,
and the model's derivation (LaTeX, from the companion derivation notes).
"""

import dash_bootstrap_components as dbc
from dash import dcc, html

from utils.sorption_models import FIT_METRICS

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
                r"counter-ion condensation theory (chain spacing $b$, set per-dataset in "
                r"the Data tab); the external $\gamma_\pm^s$ comes from the Pitzer model. "
                r"A dataset with $b$ set predicts with it; left blank, $b$ is fit from "
                r"that dataset's measured Csm,w data instead.",
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

# Only models with a free parameter b can be fit at all -- Ideal Donnan has none, so it's
# excluded from both the fit-objective selector's relevance and the uncertainty panel.
FITTABLE_MODEL_OPTIONS = [
    {"label": m["label"], "value": key} for key, m in MODEL_REGISTRY.items() if m["needs_b"]
]
FIT_METRIC_OPTIONS = [{"label": label, "value": key} for key, label in FIT_METRICS.items()]

_LABEL_STYLE = {"fontSize": "12px", "marginRight": "6px", "fontWeight": "bold"}


def build_equation_content(model_key):
    m = MODEL_REGISTRY[model_key]
    return html.Div([
        dcc.Markdown(m["equation_md"], mathjax=True),
        dcc.Markdown(ELECTRONEUTRALITY_MD, mathjax=True),
        dcc.Markdown(m["note"], mathjax=True,
                      style={"fontSize": "12px", "color": "#666", "marginTop": "6px"}),
    ])


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
                html.Span("Models to compare:", style=_LABEL_STYLE),
                dcc.Dropdown(id="model-compare-picker", options=MODEL_OPTIONS,
                             value=["ideal_donnan"], multi=True,
                             style={"flex": "1", "minWidth": "320px"}),
            ], style={"display": "flex", "alignItems": "center", "gap": "8px",
                      "marginBottom": "10px"}),

            html.Div([
                html.Span("Show derivation for:", style=_LABEL_STYLE),
                dbc.Select(id="model-select", options=MODEL_OPTIONS, value="ideal_donnan",
                           size="sm", style={"width": "340px", "marginRight": "20px"}),
                html.Span("Fit objective:", style=_LABEL_STYLE),
                dbc.Select(id="model-fit-metric", options=FIT_METRIC_OPTIONS, value="rmsle",
                           size="sm", style={"width": "340px"}),
            ], style={"display": "flex", "alignItems": "center", "marginBottom": "10px"}),

            html.P("A dataset predicts with its Data-tab b if set, or fits b from its "
                   "measured data otherwise, using the fit objective above. \"Weighted RMS "
                   "Log Error\" needs a column mapped to measurement uncertainty in the "
                   "Data tab -- datasets without one are skipped with a warning.",
                   style={"fontSize": "12px", "color": "#666", "marginBottom": "6px"}),

            dbc.Button("Run Models", id="model-run-btn", color="primary", size="sm",
                       className="mt-2"),
        ]), className="mb-3"),

        dbc.Card(dbc.CardBody([
            html.Div("Uncertainty on b", style={"fontWeight": "bold", "fontSize": "14px",
                                                  "marginBottom": "6px"}),
            html.P("Bootstrap and Bayesian analysis aren't alternative fit objectives -- "
                   "they repeatedly apply whichever objective is selected above to see how "
                   "tightly the data actually constrains b, for one dataset/model at a time.",
                   style={"fontSize": "12px", "color": "#666", "marginBottom": "8px"}),
            html.Div([
                html.Span("Dataset:", style=_LABEL_STYLE),
                dbc.Select(id="uncertainty-dataset-picker", options=[], value=None,
                           size="sm", style={"width": "260px", "marginRight": "20px"}),
                html.Span("Model:", style=_LABEL_STYLE),
                dbc.Select(id="uncertainty-model-picker", options=FITTABLE_MODEL_OPTIONS,
                           value="donnan_manning_modified", size="sm",
                           style={"width": "300px"}),
            ], style={"display": "flex", "alignItems": "center", "marginBottom": "10px"}),
            html.Div([
                html.Span("Method:", style=_LABEL_STYLE),
                dbc.RadioItems(
                    id="uncertainty-method",
                    options=[{"label": "Bootstrap", "value": "bootstrap"},
                             {"label": "Bayesian (flat prior)", "value": "bayesian"}],
                    value="bootstrap", inline=True,
                    style={"display": "inline-block", "marginRight": "20px"},
                ),
                html.Span("Resamples:", style=_LABEL_STYLE),
                dcc.Input(id="uncertainty-n-resamples", type="number", value=200,
                          min=20, max=2000, step=10, style={"width": "80px", "marginRight": "20px"}),
                html.Span("b max (Å), Bayesian prior range:", style=_LABEL_STYLE),
                dcc.Input(id="uncertainty-b-max", type="number", value=30,
                          min=1, max=1000, step="any", style={"width": "80px"}),
            ], style={"display": "flex", "alignItems": "center", "marginBottom": "10px"}),
            dbc.Button("Run Uncertainty Analysis", id="uncertainty-run-btn",
                       color="primary", size="sm", outline=True),
            html.Div(id="uncertainty-alert", className="mt-2"),
            dcc.Graph(id="uncertainty-plot", style={"height": "380px"},
                      config={"displayModeBar": True}),
            html.Div(id="uncertainty-summary"),
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
            html.Div([
                html.Div(
                    dcc.Graph(id="model-plot", style={"height": "560px"},
                              config={"displayModeBar": True}),
                    style={"width": "calc(50% - 0.5rem)"},
                ),
                html.Div(
                    dcc.Graph(id="model-ks-plot", style={"height": "560px"},
                              config={"displayModeBar": True}),
                    style={"width": "calc(50% - 0.5rem)"},
                ),
            ], style={"display": "flex", "gap": "1rem", "alignItems": "flex-start"}),
        ]), className="mb-3"),

        dbc.Card(dbc.CardBody([
            html.Div(id="model-results-table"),
        ]), className="mb-3"),
    ],
)
