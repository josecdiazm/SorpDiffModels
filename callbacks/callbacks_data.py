"""
Dash callbacks for the Data tab.

Split into two concerns, deliberately kept separate:
  - "structural" changes (add/delete a dataset, rename one) rebuild the whole
    accordion from the store, since Dash has to inject/remove real components.
  - "content" changes (table cell/column edits, add row/column, role picks,
    membrane-parameter edits) never touch the accordion's structure, so they
    write straight into the store (or, for add row/column, straight into the
    one DataTable that changed via MATCH) without forcing a full re-render.
"""

from dash import ALL, MATCH, Input, Output, State, callback, ctx

from tabs.tab_data import (
    build_dataset_item,
    build_rolemap_children,
    new_dataset,
    new_dataset_id,
)


# ─────────────────────────────────────────────────────────────────────────────
# 1.  Structural: add / delete / rename a dataset → rebuild the accordion
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("datasets-store", "data"),
    Output("datasets-accordion", "children"),
    Output("datasets-accordion", "active_item"),
    Input("add-dataset-btn", "n_clicks"),
    Input({"type": "dataset-delete", "index": ALL}, "n_clicks"),
    Input({"type": "dataset-name", "index": ALL}, "value"),
    State({"type": "dataset-name", "index": ALL}, "id"),
    State("datasets-store", "data"),
    State("datasets-accordion", "active_item"),
    prevent_initial_call=True,
)
def manage_datasets(n_add, n_delete, names, name_ids, store, active_item):
    store = dict(store or {})
    active_item = list(active_item or [])
    triggered = ctx.triggered_id

    if triggered == "add-dataset-btn":
        new_id = new_dataset_id()
        store[new_id] = new_dataset(f"Dataset {len(store) + 1}")
        active_item.append(new_id)

    elif isinstance(triggered, dict) and triggered.get("type") == "dataset-delete":
        del_id = triggered["index"]
        store.pop(del_id, None)
        active_item = [a for a in active_item if a != del_id]

    else:
        # A name field fired (debounced). Sync every current name into the store.
        for id_dict, value in zip(name_ids, names):
            ds_id = id_dict["index"]
            if ds_id in store and value:
                store[ds_id]["name"] = value

    children = [build_dataset_item(ds_id, ds) for ds_id, ds in store.items()]
    active_item = [a for a in active_item if a in store]
    return store, children, active_item


# ─────────────────────────────────────────────────────────────────────────────
# 2.  Content: table cell/column edits → store (no accordion rebuild)
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("datasets-store", "data", allow_duplicate=True),
    Input({"type": "dataset-table", "index": ALL}, "data"),
    Input({"type": "dataset-table", "index": ALL}, "columns"),
    State({"type": "dataset-table", "index": ALL}, "id"),
    State("datasets-store", "data"),
    prevent_initial_call=True,
)
def sync_table_content(all_rows, all_columns, table_ids, store):
    store = dict(store or {})
    for id_dict, rows, columns in zip(table_ids, all_rows, all_columns):
        ds_id = id_dict["index"]
        if ds_id in store:
            store[ds_id]["rows"] = rows
            store[ds_id]["columns"] = columns
    return store


# ─────────────────────────────────────────────────────────────────────────────
# 3.  "+ Add Row" (per dataset, MATCH — no store round-trip needed)
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output({"type": "dataset-table", "index": MATCH}, "data"),
    Input({"type": "dataset-addrow", "index": MATCH}, "n_clicks"),
    State({"type": "dataset-table", "index": MATCH}, "data"),
    State({"type": "dataset-table", "index": MATCH}, "columns"),
    prevent_initial_call=True,
)
def add_row(n_clicks, rows, columns):
    rows = list(rows or [])
    rows.append({c["id"]: "" for c in columns})
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# 4.  "+ Add Column" (per dataset, MATCH)
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output({"type": "dataset-table", "index": MATCH}, "columns"),
    Input({"type": "dataset-addcol", "index": MATCH}, "n_clicks"),
    State({"type": "dataset-table", "index": MATCH}, "columns"),
    prevent_initial_call=True,
)
def add_column(n_clicks, columns):
    columns = list(columns or [])
    new_col_id = f"col-{n_clicks}-{len(columns)}"
    columns.append({"id": new_col_id, "name": "New Column", "renamable": True, "deletable": True})
    return columns


# ─────────────────────────────────────────────────────────────────────────────
# 5.  Regenerate the role-mapping row whenever that dataset's columns change
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output({"type": "dataset-rolemap", "index": MATCH}, "children"),
    Input({"type": "dataset-table", "index": MATCH}, "columns"),
    State({"type": "dataset-table", "index": MATCH}, "id"),
    State("datasets-store", "data"),
    prevent_initial_call=True,
)
def rebuild_rolemap(columns, table_id, store):
    ds_id = table_id["index"]
    roles = (store or {}).get(ds_id, {}).get("roles", {})
    return build_rolemap_children(ds_id, columns, roles)


# ─────────────────────────────────────────────────────────────────────────────
# 6.  Role-select value changes → store
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("datasets-store", "data", allow_duplicate=True),
    Input({"type": "dataset-role-select", "index": ALL, "col": ALL}, "value"),
    State({"type": "dataset-role-select", "index": ALL, "col": ALL}, "id"),
    State("datasets-store", "data"),
    prevent_initial_call=True,
)
def sync_roles(values, ids, store):
    store = dict(store or {})
    for id_dict, value in zip(ids, values):
        ds_id = id_dict["index"]
        col_id = id_dict["col"]
        if ds_id in store:
            store[ds_id]["roles"][col_id] = value
    return store


# ─────────────────────────────────────────────────────────────────────────────
# 7.  Membrane-parameter field changes → store
# ─────────────────────────────────────────────────────────────────────────────

@callback(
    Output("datasets-store", "data", allow_duplicate=True),
    Input({"type": "dataset-param", "index": ALL, "field": ALL}, "value"),
    State({"type": "dataset-param", "index": ALL, "field": ALL}, "id"),
    State("datasets-store", "data"),
    prevent_initial_call=True,
)
def sync_membrane_params(values, ids, store):
    store = dict(store or {})
    for id_dict, value in zip(ids, values):
        ds_id = id_dict["index"]
        field = id_dict["field"]
        if ds_id in store:
            store[ds_id]["membrane_params"][field] = value
    return store
