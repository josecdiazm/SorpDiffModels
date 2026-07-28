"""
Dash callbacks for the Sorption Models tab.
"""

import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import ALL, MATCH, Input, Output, State, callback, html

from tabs.tab_data import PITZER_PARAMS
from tabs.tab_models import MODEL_REGISTRY, build_equation_content, build_per_dataset_controls
from utils.dataset_utils import extract_series
from utils.model_runner import run_model

# Plotly's default qualitative sequence, assigned explicitly (one color per dataset,
# reused across every model/mode for that dataset) so measured points and model curves
# for the same dataset always match.
_PALETTE = ["#636EFA", "#EF553B", "#00CC96", "#AB63FA", "#FFA15A",
            "#19D3F3", "#FF6692", "#B6E880", "#FF97FF", "#FECB52"]


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
# 2.  Regenerate the per-dataset predict/b controls when the selection changes
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("model-per-dataset-controls", "children"),
    Input("model-dataset-picker", "value"),
    State("datasets-store", "data"),
    prevent_initial_call=True,
)
def rebuild_per_dataset_controls(dataset_ids, datasets):
    return build_per_dataset_controls(dataset_ids or [], datasets)


# ─────────────────────────────────────────────────────────────────────────────
# 3.  Show the b input only when that dataset's Predict checkbox is on
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output({"type": "model-b-input", "index": MATCH}, "style"),
    Input({"type": "model-predict-check", "index": MATCH}, "value"),
    prevent_initial_call=True,
)
def toggle_b_input(predict_on):
    base = {"width": "90px"}
    base["display"] = "inline-block" if predict_on else "none"
    return base


# ─────────────────────────────────────────────────────────────────────────────
# 4.  Derivation panel: collapse toggle + content keyed to the selected model
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
# 5.  Run Models: the main compute callback
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("model-plot", "figure"),
    Output("model-results-table", "children"),
    Output("model-alert", "children"),
    Input("model-run-btn", "n_clicks"),
    State("model-dataset-picker", "value"),
    State("model-select", "value"),
    State("model-compare-check", "value"),
    State({"type": "model-predict-check", "index": ALL}, "value"),
    State({"type": "model-predict-check", "index": ALL}, "id"),
    State({"type": "model-b-input", "index": ALL}, "value"),
    State({"type": "model-b-input", "index": ALL}, "id"),
    State("datasets-store", "data"),
    prevent_initial_call=True,
)
def run_models(n_clicks, dataset_ids, primary_model, compare_all,
                predict_vals, predict_ids, b_vals, b_ids, datasets):
    dataset_ids = dataset_ids or []
    datasets = datasets or {}
    predict_map = {i["index"]: v for i, v in zip(predict_ids, predict_vals)}
    b_map = {i["index"]: v for i, v in zip(b_ids, b_vals)}

    model_keys = list(MODEL_REGISTRY.keys()) if compare_all else [primary_model]

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

        predict_on = predict_map.get(ds_id, False)
        b_val = b_map.get(ds_id)
        if predict_on and b_val is None:
            warnings.append(f"Dataset '{dataset['name']}': Predict is checked but no b value was entered.")
            predict_on = False

        for model_key in model_keys:
            model_label = MODEL_REGISTRY[model_key]["label"]
            try:
                out = run_model(model_key, dataset, css, phiw_s, csmw_meas,
                                 predict_on, b_val, PITZER_PARAMS)
            except ValueError as exc:
                warnings.append(str(exc))
                continue

            predictive = out.get("predictive")
            fitted = out.get("fitted")
            if predictive is None and fitted is None:
                warnings.append(
                    f"Dataset '{dataset['name']}', {model_label}: nothing to compute — "
                    "check Predict with a b value, or provide measured Csm,w data."
                )
                continue

            if predictive is not None:
                df = predictive["table"]
                pred_col = [c for c in df.columns if "Predicted" in c][0]
                fig.add_trace(go.Scatter(
                    x=df["Css (m)"], y=df[pred_col], mode="lines",
                    name=f"{dataset['name']} — {model_label} (predicted)",
                    line=dict(color=color, dash="solid"),
                ))
                result_rows.append([dataset["name"], model_label, "Predicted",
                                     f"{predictive['b']:.4g}" if predictive["b"] is not None else "—",
                                     f"{predictive['rmsle']:.4g}" if predictive["rmsle"] is not None else "—"])

            if fitted is not None:
                df = fitted["table"]
                fit_col = [c for c in df.columns if "Fitted" in c][0]
                fig.add_trace(go.Scatter(
                    x=df["Css (m)"], y=df[fit_col], mode="lines",
                    name=f"{dataset['name']} — {model_label} (fitted)",
                    line=dict(color=color, dash="dash"),
                ))
                result_rows.append([dataset["name"], model_label, "Fitted",
                                     f"{fitted['b_fit']:.4g}", f"{fitted['rmsle']:.4g}"])

    fig.update_layout(
        title="Sorption Isotherm",
        xaxis_title="Css (m)", yaxis_title="Csm,w (m)",
        xaxis_type="log", yaxis_type="log",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(l=60, r=20, t=80, b=60),
        template="plotly_white",
    )

    if result_rows:
        cols = ["Dataset", "Model", "Mode", "b (Å)", "RMSLE"]
        table = dbc.Table(
            [html.Thead(html.Tr([html.Th(c) for c in cols]))] +
            [html.Tbody([html.Tr([html.Td(cell) for cell in row]) for row in result_rows])],
            bordered=True, hover=True, responsive=True, size="sm",
        )
    else:
        table = dbc.Alert("No results yet — select at least one dataset and click Run Models.",
                           color="info")

    alert = dbc.Alert([html.Div(w) for w in warnings], color="warning") if warnings else None

    return fig, table, alert
