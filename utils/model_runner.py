"""
Normalizes the three sorption models' differing signatures/return shapes into one
interface, so callback code can loop over (dataset, model) pairs uniformly instead of
branching on which model it's dealing with.

Every model's run_* function returns a dict of {"predictive": {...} | None,
"fitted": {...} | None}, each holding {"b": float|None, "table": DataFrame, "rmsle":
float|None}. Ideal Donnan has no free parameter, so it only ever populates "predictive".
"""

from utils.sorption_models import (
    log_r_squared,
    run_donnan_manning,
    run_donnan_manning_modified,
    run_ideal_donnan,
)


def run_model(model_key, dataset, css, phiw_s, csmw_meas, params_df,
              fit_metric="rmsle", csmw_uncertainty=None):
    """b is read from the dataset's own membrane_params (a structural property of that
    membrane, set once in the Data tab) rather than passed in per call: set -> predicts
    with it, blank -> fits it from csmw_meas instead. Ideal Donnan has no b at all, so
    fit_metric/csmw_uncertainty (which only affect *fitting*) don't apply to it.
    fit_metric picks which objective b is fit by; see utils.sorption_models.fit_error()."""
    mp = dataset["membrane_params"]
    zg, zc, zA = mp["zg"], mp["zc"], mp["zA"]
    phiw_DI, CAmw_DI, T = mp["phiw_DI"], mp["CAmw_DI"], mp["T"]

    if model_key == "ideal_donnan":
        df, rmsle_val = run_ideal_donnan(
            zg, zc, zA, phiw_DI, CAmw_DI, css, phiw_s=phiw_s, Csmw_meas=csmw_meas
        )
        df = df.rename(columns={"Csm,w Ideal Donnan (m)": "Csm,w Predicted (m)"})
        log_r2_val = (
            log_r_squared(df["Csm,w Predicted (m)"], df["Csm,w measured (m)"])
            if "Csm,w measured (m)" in df.columns else None
        )
        return {"predictive": {"b": None, "table": df, "rmsle": rmsle_val, "log_r2": log_r2_val},
                "fitted": None}

    b = mp.get("b")

    if model_key == "donnan_manning":
        salt = mp.get("salt")
        if not salt:
            raise ValueError(f"Dataset '{dataset['name']}': Donnan-Manning needs a salt selected in the Data tab.")
        return run_donnan_manning(
            salt, zg, zc, zA, phiw_DI, CAmw_DI, T, css, params_df,
            phiw_s=phiw_s, Csmw_meas=csmw_meas, b=b,
            fit_metric=fit_metric, csmw_uncertainty=csmw_uncertainty,
        )

    if model_key == "donnan_manning_modified":
        return run_donnan_manning_modified(
            zg, zc, zA, phiw_DI, CAmw_DI, T, css,
            phiw_s=phiw_s, Csmw_meas=csmw_meas, b=b,
            fit_metric=fit_metric, csmw_uncertainty=csmw_uncertainty,
        )

    raise ValueError(f"Unknown model key: {model_key!r}")
