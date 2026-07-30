"""
Bridges a Data-tab dataset dict (user-named columns + a column-id -> role map) to the
plain concentration-series arrays the sorption models expect. Model code should always
go through extract_series() and never look at a column's display name -- the whole point
of the role map is that the display name is unreliable/user-chosen.
"""

import numpy as np

from utils.roles import ROLE_CSMW_MEAS, ROLE_CSMW_UNCERTAINTY, ROLE_CSS, ROLE_PHIW_S


def _column_id_for_role(dataset, role):
    for col_id, r in dataset["roles"].items():
        if r == role:
            return col_id
    return None


def _collect_optional_column(rows, col_id, css_mask):
    """Values (or None) for a column, aligned to the rows that had a usable Css value."""
    if col_id is None:
        return []
    return [row.get(col_id, "") for row, keep in zip(rows, css_mask) if keep]


def _finish_optional(raw_values, label, dataset_name):
    """Returns a float array, or None if the whole column is blank. Raises if it's
    partially filled in -- mirrors the original notebooks' EditableTable.get_column()."""
    if not raw_values:
        return None
    filled = [v for v in raw_values if v not in (None, "")]
    if not filled:
        return None
    if len(filled) != len(raw_values):
        raise ValueError(
            f"Dataset '{dataset_name}': the {label} column is only partially filled in — "
            "either provide a value in every row that has a Css value, or leave the whole "
            "column blank."
        )
    try:
        return np.array([float(v) for v in raw_values], dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Dataset '{dataset_name}': non-numeric value in the {label} column ({exc}).")


def extract_series(dataset):
    """Returns (css, phiw_s, csmw_meas, csmw_uncertainty) as numpy arrays; all but css are
    None if their role isn't mapped to any column (or the column is entirely blank).
    Raises ValueError with a user-facing message on missing/invalid/partially-filled data.
    """
    name = dataset["name"]
    css_col = _column_id_for_role(dataset, ROLE_CSS)
    if css_col is None:
        raise ValueError(f"Dataset '{name}': no column is mapped to External concentration (Css).")

    rows = dataset["rows"]
    css_mask, css = [], []
    for i, row in enumerate(rows):
        raw = row.get(css_col, "")
        if raw in (None, ""):
            css_mask.append(False)
            continue
        try:
            css.append(float(raw))
        except (TypeError, ValueError):
            raise ValueError(f"Dataset '{name}', row {i + 1}: '{raw}' is not a valid Css number.")
        css_mask.append(True)

    if not css:
        raise ValueError(f"Dataset '{name}': no rows have a value in the Css column.")

    phiw_s_col = _column_id_for_role(dataset, ROLE_PHIW_S)
    csmw_col = _column_id_for_role(dataset, ROLE_CSMW_MEAS)
    csmw_unc_col = _column_id_for_role(dataset, ROLE_CSMW_UNCERTAINTY)

    phiw_s_raw = _collect_optional_column(rows, phiw_s_col, css_mask)
    csmw_raw = _collect_optional_column(rows, csmw_col, css_mask)
    csmw_unc_raw = _collect_optional_column(rows, csmw_unc_col, css_mask)

    phiw_s = _finish_optional(phiw_s_raw, "water volume fraction (phiw,s)", name)
    csmw_meas = _finish_optional(csmw_raw, "measured membrane concentration (Csm,w)", name)
    csmw_uncertainty = _finish_optional(
        csmw_unc_raw, "measured concentration uncertainty (sigma Csm,w)", name)

    return np.array(css, dtype=float), phiw_s, csmw_meas, csmw_uncertainty
