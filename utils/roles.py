"""
Canonical column roles: the fixed, small vocabulary a Data-tab dataset column can be
mapped to, so model code can read "the Css column" regardless of what the user actually
named it. Referenced by constant everywhere, never as a bare string.
"""

ROLE_UNASSIGNED = ""
ROLE_CSS = "css"
ROLE_PHIW_S = "phiw_s"
ROLE_CSMW_MEAS = "csmw_meas"

ROLE_OPTIONS = [
    {"label": "Unassigned", "value": ROLE_UNASSIGNED},
    {"label": "External concentration, Css (m)", "value": ROLE_CSS},
    {"label": "Water volume fraction, φw,s (–)", "value": ROLE_PHIW_S},
    {"label": "Measured membrane concentration, Csm,w (m)", "value": ROLE_CSMW_MEAS},
]
