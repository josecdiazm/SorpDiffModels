"""
The Data tab: build up one or more named datasets, each an accordion item that
collapses to a one-line summary (its name) and expands back into an editable
per-membrane parameter block + a user-columned data table.

Column *names* are whatever the user types; column *roles* (which model
parameter a column feeds) are tracked separately via the role-mapping row
under each table, keyed by the column's stable id rather than its label, so
renaming a column never breaks its mapping and two datasets can name the same
physical quantity differently without colliding.
"""

import uuid

import dash_bootstrap_components as dbc
from dash import dash_table, dcc, html

from utils.roles import ROLE_CSMW_MEAS, ROLE_CSS, ROLE_OPTIONS, ROLE_PHIW_S
from utils.sorption_models import list_salts, load_pitzer_params

PITZER_PARAMS = load_pitzer_params()
SALT_OPTIONS = [{"label": s, "value": s} for s in list_salts(PITZER_PARAMS)]

DEFAULT_COLUMNS = [
    {"id": "col-css", "name": "Css (m)", "renamable": True, "deletable": True},
    {"id": "col-phiws", "name": "phiw_s (-)", "renamable": True, "deletable": True},
    {"id": "col-csmw", "name": "Csm,w measured (m)", "renamable": True, "deletable": True},
]
DEFAULT_ROLES = {"col-css": ROLE_CSS, "col-phiws": ROLE_PHIW_S, "col-csmw": ROLE_CSMW_MEAS}
DEFAULT_ROWS = [{"col-css": "", "col-phiws": "", "col-csmw": ""} for _ in range(3)]

# (field id, display name, LaTeX symbol (no $ delimiters), default value)
MEMBRANE_PARAM_FIELDS = [
    ("zg",      "Counter-ion Valence",        "z_g",                    1),
    ("zc",      "Co-ion Valence",             "z_c",                    -1),
    ("zA",      "Fixed-charge Valence",       "z_A",                    -1),
    ("phiw_DI", "Water Volume Fraction",      r"\phi_{w,DI}",           0.3),
    ("CAmw_DI", "Fixed-charge Concentration", r"C^{m,w}_{A,DI}",        1.0),
    ("T",       "Temperature",                "T",                      25),
]

_LABEL_STYLE = {"fontSize": "14px", "marginRight": "3px"}
_INPUT_STYLE = {"width": "90px", "marginRight": "14px"}
_SECTION_HEADER_STYLE = {"fontWeight": "bold", "fontSize": "16px", "marginBottom": "4px"}


def new_dataset_id():
    return uuid.uuid4().hex[:8]


def new_dataset(name):
    return {
        "name": name,
        "membrane_params": {field: default for field, _, _, default in MEMBRANE_PARAM_FIELDS} | {"salt": ""},
        "columns": [dict(c) for c in DEFAULT_COLUMNS],
        "rows": [dict(r) for r in DEFAULT_ROWS],
        "roles": dict(DEFAULT_ROLES),
    }


def build_rolemap_children(dataset_id, columns, roles):
    """One small role-select per current column, keyed by the column's stable id.
    Stacked vertically (label above select) since this now lives in a narrow sidebar."""
    items = []
    for col in columns:
        col_id = col["id"]
        items.append(
            html.Div([
                html.Span(col["name"], style={"fontSize": "11px", "color": "#666",
                                               "display": "block", "marginBottom": "2px",
                                               "wordBreak": "break-word"}),
                dbc.Select(
                    id={"type": "dataset-role-select", "index": dataset_id, "col": col_id},
                    options=ROLE_OPTIONS,
                    value=roles.get(col_id, ""),
                    size="sm",
                    style={"width": "100%", "fontSize": "11px"},
                ),
            ], style={"marginBottom": "10px"})
        )
    return items


# zg, zc (the salt's own ion valences) are "Salt Parameters"; zA, phiw_DI, CAmw_DI, T
# (properties of the membrane itself) are "Membrane parameters".
_SALT_PARAM_FIELD_IDS = {"zg", "zc"}

_ROW_STYLE = {"display": "flex", "alignItems": "center", "flexWrap": "wrap", "marginBottom": "10px"}


def _build_param_inputs(dataset_id, membrane_params, field_specs):
    return [
        html.Div([
            dcc.Markdown(f"{name} (${symbol}$)", mathjax=True, className="param-label"),
            dcc.Input(
                id={"type": "dataset-param", "index": dataset_id, "field": field},
                type="number", value=membrane_params.get(field, default), step="any",
                style=_INPUT_STYLE,
            ),
        ], style={"display": "flex", "alignItems": "center"})
        for field, name, symbol, default in field_specs
    ]


def build_salt_field(dataset_id, membrane_params, style=None):
    return html.Div([
        html.Span("Salt:", style=_LABEL_STYLE),
        dbc.Select(
            id={"type": "dataset-param", "index": dataset_id, "field": "salt"},
            options=SALT_OPTIONS,
            value=membrane_params.get("salt", ""),
            size="sm",
            style={"width": "160px"},
        ),
    ], style={"display": "flex", "alignItems": "center", **(style or {})})


def build_membrane_params_block(dataset_id, membrane_params):
    salt_param_fields = [f for f in MEMBRANE_PARAM_FIELDS if f[0] in _SALT_PARAM_FIELD_IDS]
    membrane_fields = [f for f in MEMBRANE_PARAM_FIELDS if f[0] not in _SALT_PARAM_FIELD_IDS]

    salt_param_row = html.Div(
        _build_param_inputs(dataset_id, membrane_params, salt_param_fields), style=_ROW_STYLE)
    membrane_row = html.Div(
        _build_param_inputs(dataset_id, membrane_params, membrane_fields), style=_ROW_STYLE)

    return html.Div([
        html.Div("Salt Parameters", style=_SECTION_HEADER_STYLE),
        salt_param_row,
        html.Div("Membrane parameters", style=_SECTION_HEADER_STYLE),
        membrane_row,
    ])


def build_dataset_item(dataset_id, dataset):
    left = html.Div([
        html.Div([
            html.Span("Dataset Name:", style=_LABEL_STYLE),
            dcc.Input(
                id={"type": "dataset-name", "index": dataset_id},
                type="text", value=dataset["name"], debounce=True,
                style={"width": "220px", "marginRight": "14px"},
            ),
            dbc.Button("Delete Dataset", id={"type": "dataset-delete", "index": dataset_id},
                       color="danger", outline=True, size="sm"),
            build_salt_field(dataset_id, dataset["membrane_params"], style={"marginLeft": "48px"}),
        ], style={"display": "flex", "alignItems": "center", "marginBottom": "10px"}),

        build_membrane_params_block(dataset_id, dataset["membrane_params"]),

        html.Div("Concentration-dependent data", style=_SECTION_HEADER_STYLE),
        dash_table.DataTable(
            id={"type": "dataset-table", "index": dataset_id},
            columns=dataset["columns"],
            data=dataset["rows"],
            editable=True,
            row_deletable=True,
            style_table={"overflowX": "auto"},
            style_cell={"fontSize": "12px", "padding": "4px 8px", "textAlign": "center",
                        "border": "1px solid #ccc", "minWidth": "110px"},
            style_header={"fontWeight": "bold", "backgroundColor": "#f8f9fa"},
        ),
        html.Div([
            dbc.Button("+ Add Row", id={"type": "dataset-addrow", "index": dataset_id},
                       color="secondary", size="sm", outline=True, className="mt-2 me-2"),
            dbc.Button("+ Add Column", id={"type": "dataset-addcol", "index": dataset_id},
                       color="secondary", size="sm", outline=True, className="mt-2"),
        ]),
    ], style={"width": "calc(85% - 1px)"})

    right = html.Div([
        html.Div("Column → model parameter mapping",
                  style={**_SECTION_HEADER_STYLE, "marginBottom": "8px"}),
        html.Div(
            build_rolemap_children(dataset_id, dataset["columns"], dataset["roles"]),
            id={"type": "dataset-rolemap", "index": dataset_id},
        ),
    ], style={"width": "calc(15% - 13px)", "paddingLeft": "12px"})

    divider = html.Div(style={"width": "1px", "backgroundColor": "#dee2e6",
                               "alignSelf": "stretch"})

    return dbc.AccordionItem(
        title=dataset["name"],
        item_id=dataset_id,
        children=[
            html.Div([left, divider, right],
                      style={"display": "flex", "alignItems": "flex-start"}),
        ],
    )


layout = dbc.Container(
    fluid=True,
    className="mt-3",
    children=[
        dbc.Card(dbc.CardBody([
            html.P(
                "Build one dataset per membrane/salt system: set its membrane parameters, "
                "enter concentration-dependent data with whatever column names you like, "
                "and map each column to the model parameter it represents. Click a dataset's "
                "title to collapse or reopen it.",
                style={"fontSize": "13px", "color": "#666", "marginBottom": "0px"},
            ),
        ]), className="mb-3 py-1"),

        dbc.Button("+ Add Dataset", id="add-dataset-btn", color="primary", size="sm",
                   className="mb-3"),

        dbc.Accordion(id="datasets-accordion", children=[], active_item=[], always_open=True),

        dcc.Store(id="datasets-store", data={}),
    ],
)
