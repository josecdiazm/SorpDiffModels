"""Small dependency-free ipywidgets helpers shared by the Ideal Donnan and
Donnan-Manning notebooks: a labeled scalar-input form and an editable table
for entering per-concentration-point data (Css, phiw_s, Csmw measured)."""

import ipywidgets as widgets


class EditableTable:
    """A minimal editable data-entry grid: text cells (blank = not provided),
    with add/remove row buttons. Values are parsed to float on read."""

    def __init__(self, columns, n_rows=3, col_width="150px"):
        self.columns = columns
        self.col_width = col_width
        self.rows = []

        header_cells = [
            widgets.Label(value=c, layout=widgets.Layout(width=col_width))
            for c in columns
        ] + [widgets.Label(value="", layout=widgets.Layout(width="36px"))]
        self.header = widgets.HBox(header_cells)
        self.rows_box = widgets.VBox([])
        self.add_button = widgets.Button(description="+ Add row", layout=widgets.Layout(width="100px"))
        self.add_button.on_click(lambda _btn: self.add_row())

        for _ in range(n_rows):
            self.add_row()

        self.widget = widgets.VBox([self.header, self.rows_box, self.add_button])

    def add_row(self, values=None):
        cells = [
            widgets.Text(
                value="" if values is None else str(values[i]),
                layout=widgets.Layout(width=self.col_width),
            )
            for i in range(len(self.columns))
        ]
        remove_btn = widgets.Button(description="x", layout=widgets.Layout(width="36px"))
        row_box = widgets.HBox(cells + [remove_btn])

        def remove(_btn, row_box=row_box):
            self.rows.remove(row_box)
            self.rows_box.children = tuple(self.rows)

        remove_btn.on_click(remove)
        self.rows.append(row_box)
        self.rows_box.children = tuple(self.rows)

    def get_rows(self):
        """Returns list of rows (each a list of float-or-None), skipping fully-blank rows.
        Raises ValueError with a row/column-specific message if a cell has unparseable text."""
        data = []
        for i, row_box in enumerate(self.rows):
            cells = row_box.children[:-1]
            vals = []
            any_filled = False
            for j, cell in enumerate(cells):
                s = cell.value.strip()
                if s == "":
                    vals.append(None)
                    continue
                any_filled = True
                try:
                    vals.append(float(s))
                except ValueError:
                    raise ValueError(f"Row {i + 1}, column '{self.columns[j]}': '{s}' is not a valid number.")
            if any_filled:
                data.append(vals)
        return data

    def get_column(self, col_index):
        """One column across non-blank rows. Raises if the column is only partially filled."""
        rows = self.get_rows()
        vals = [r[col_index] for r in rows]
        filled = [v for v in vals if v is not None]
        if filled and len(filled) != len(vals):
            raise ValueError(
                f"Column '{self.columns[col_index]}' is only partially filled in — "
                "either provide a value in every row or leave the whole column blank."
            )
        return vals if filled else []


def labeled(widget, label, label_width="170px"):
    return widgets.HBox([widgets.Label(value=label, layout=widgets.Layout(width=label_width)), widget])


def scalar_form(fields):
    """fields: list of (key, ipywidget). Returns (VBox, dict[key] -> widget)."""
    box = widgets.VBox([labeled(w, lbl) for key, lbl, w in fields])
    return box, {key: w for key, lbl, w in fields}
