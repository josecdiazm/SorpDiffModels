"""
Dash callbacks for the Sorption Models tab.
"""

import colorsys

import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import Input, Output, State, callback, dcc, html

from tabs.tab_data import PITZER_PARAMS
from tabs.tab_models import MODEL_REGISTRY, build_equation_content
from utils.dataset_utils import extract_series
from utils.model_runner import run_model
from utils.sorption_models import bjerrum_length

# Plotly's default qualitative sequence, assigned explicitly (one color *family* per
# dataset, reused across every model/mode for that dataset) so measured points and model
# curves for the same dataset are always visually related.
_PALETTE = ["#636EFA", "#EF553B", "#00CC96", "#AB63FA", "#FFA15A",
            "#19D3F3", "#FF6692", "#B6E880", "#FF97FF", "#FECB52"]

# Stable per-model index (from MODEL_REGISTRY's fixed order), independent of which subset
# is selected in a given run, so a given model always gets the same shade/dash.
_MODEL_INDEX = {key: i for i, key in enumerate(MODEL_REGISTRY.keys())}

# 3 models x 2 modes (predicted/fitted) = 6, matching Plotly's 6 built-in dash values
# exactly; degrades gracefully (cycles) once more models are registered.
_DASH_STYLES = ["solid", "dash", "dot", "dashdot", "longdash", "longdashdot"]


def _dash_for(model_key, predicted):
    idx = _MODEL_INDEX.get(model_key, 0) * 2 + (0 if predicted else 1)
    return _DASH_STYLES[idx % len(_DASH_STYLES)]


def _xi_values(dataset, b):
    """(xi, xi_crit) for a Manning-family row's b: xi = Bjerrum length / b (companion
    derivation notes Eq. 14), xi_crit = 1/|zA*zg|, the theory-only threshold above which
    counter-ion condensation sets in. None, None when there's no b (Ideal Donnan)."""
    if b is None:
        return None, None
    mp = dataset["membrane_params"]
    lb = bjerrum_length(mp["phiw_DI"], mp["T"])
    xi = lb / b
    xi_crit = 1 / abs(mp["zA"] * mp["zg"])
    return xi, xi_crit


def _shade_color(hex_color, model_index):
    """Same hue/dataset family, lightness nudged per model so curves for the same
    dataset are still individually easy to pick out: base, then alternating
    lighter/darker steps (+0.14, -0.14, +0.28, -0.28, ...)."""
    r, g, b = (int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    step = ((model_index + 1) // 2) * 0.14
    direction = 1 if model_index % 2 else -1
    l = min(0.92, max(0.08, l + direction * step))
    r2, g2, b2 = colorsys.hls_to_rgb(h, l, s)
    return "#{:02x}{:02x}{:02x}".format(round(r2 * 255), round(g2 * 255), round(b2 * 255))


# ─────────────────────────────────────────────────────────────────────────────
# 1.  Keep the dataset picker's options in sync with the Data tab's store
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("model-dataset-picker", "options"),
    Input("datasets-store", "data"),
    prevent_initial_call=True,
)
def sync_dataset_options(datasets):
    return [{"label": ds["name"], "value": ds_id} for ds_id, ds in (datasets or {}).items()]


# ─────────────────────────────────────────────────────────────────────────────
# 2.  Derivation panel: collapse toggle + content keyed to the selected model
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("model-eq-collapse", "is_open"),
    Input("model-eq-toggle-btn", "n_clicks"),
    State("model-eq-collapse", "is_open"),
    prevent_initial_call=True,
)
def toggle_equations(n_clicks, is_open):
    return not is_open


@callback(
    Output("model-eq-content", "children"),
    Input("model-select", "value"),
    prevent_initial_call=True,
)
def update_equation_content(model_key):
    return build_equation_content(model_key)


# ─────────────────────────────────────────────────────────────────────────────
# 3.  Run Models: the main compute callback
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("model-plot", "figure"),
    Output("model-results-table", "children"),
    Output("model-alert", "children"),
    Input("model-run-btn", "n_clicks"),
    State("model-dataset-picker", "value"),
    State("model-compare-picker", "value"),
    State("datasets-store", "data"),
    prevent_initial_call=True,
)
def run_models(n_clicks, dataset_ids, model_keys, datasets):
    dataset_ids = dataset_ids or []
    model_keys = model_keys or []
    datasets = datasets or {}

    warnings = []
    fig = go.Figure()
    result_rows = []

    for ds_i, ds_id in enumerate(dataset_ids):
        dataset = datasets.get(ds_id)
        if not dataset:
            continue
        color = _PALETTE[ds_i % len(_PALETTE)]

        try:
            css, phiw_s, csmw_meas = extract_series(dataset)
        except ValueError as exc:
            warnings.append(str(exc))
            continue

        if csmw_meas is not None:
            fig.add_trace(go.Scatter(
                x=css, y=csmw_meas, mode="markers", name=f"{dataset['name']} — measured",
                marker=dict(color=color, symbol="circle-open", size=9),
            ))

        for model_key in model_keys:
            model_label = MODEL_REGISTRY[model_key]["label"]
            try:
                out = run_model(model_key, dataset, css, phiw_s, csmw_meas, PITZER_PARAMS)
            except ValueError as exc:
                warnings.append(str(exc))
                continue

            predictive = out.get("predictive")
            fitted = out.get("fitted")
            if predictive is None and fitted is None:
                warnings.append(
                    f"Dataset '{dataset['name']}', {model_label}: nothing to compute — "
                    "set b in the Data tab, or provide measured Csm,w data."
                )
                continue

            model_shade = _shade_color(color, _MODEL_INDEX.get(model_key, 0))

            if predictive is not None:
                df = predictive["table"]
                pred_col = [c for c in df.columns if "Predicted" in c][0]
                fig.add_trace(go.Scatter(
                    x=df["Css (m)"], y=df[pred_col], mode="lines",
                    name=f"{dataset['name']} — {model_label} (predicted)",
                    line=dict(color=model_shade, dash=_dash_for(model_key, True)),
                ))
                xi, xi_crit = _xi_values(dataset, predictive["b"])
                result_rows.append([dataset["name"], model_label, "Predicted",
                                     f"{predictive['b']:.4g}" if predictive["b"] is not None else "—",
                                     f"{predictive['rmsle']:.4g}" if predictive["rmsle"] is not None else "—",
                                     f"{xi:.4g}" if xi is not None else "—",
                                     f"{xi_crit:.4g}" if xi_crit is not None else "—"])

            if fitted is not None:
                df = fitted["table"]
                fit_col = [c for c in df.columns if "Fitted" in c][0]
                fig.add_trace(go.Scatter(
                    x=df["Css (m)"], y=df[fit_col], mode="lines",
                    name=f"{dataset['name']} — {model_label} (fitted)",
                    line=dict(color=model_shade, dash=_dash_for(model_key, False)),
                ))
                xi, xi_crit = _xi_values(dataset, fitted["b_fit"])
                result_rows.append([dataset["name"], model_label, "Fitted",
                                     f"{fitted['b_fit']:.4g}", f"{fitted['rmsle']:.4g}",
                                     f"{xi:.4g}" if xi is not None else "—",
                                     f"{xi_crit:.4g}" if xi_crit is not None else "—"])

    fig.update_layout(
        title="Sorption Isotherm",
        xaxis_title="Css (m)", yaxis_title="Csm,w (m)",
        xaxis_type="log", yaxis_type="log",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(l=60, r=20, t=80, b=60),
        template="plotly_white",
    )

    if result_rows:
        plain_cols = ["Dataset", "Model", "Mode", "b (Å)", "RMSLE"]
        header_cells = [html.Th(c) for c in plain_cols]
        header_cells += [
            html.Th(dcc.Markdown(r"Predicted $\xi$", mathjax=True)),
            html.Th(dcc.Markdown(r"Theoretical $\xi$", mathjax=True)),
        ]
        table = dbc.Table(
            [html.Thead(html.Tr(header_cells))] +
            [html.Tbody([html.Tr([html.Td(cell) for cell in row]) for row in result_rows])],
            bordered=True, hover=True, responsive=True, size="sm",
        )
    else:
        table = dbc.Alert("No results yet — select at least one dataset and click Run Models.",
                           color="info")

    alert = dbc.Alert([html.Div(w) for w in warnings], color="warning") if warnings else None

    return fig, table, alert
