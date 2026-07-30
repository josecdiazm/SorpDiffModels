"""
Bootstrap and Bayesian uncertainty quantification for the Manning chain-spacing
parameter b. These are NOT alternative fit objectives alongside RMSE/RMSLE/weighted RMSLE
(utils.sorption_models.fit_error) -- they're resampling/probabilistic methods layered on
top of whichever objective is chosen, repeatedly applying it to see how tightly the data
actually constrains b, rather than reporting a single point estimate.

Only donnan_manning and donnan_manning_modified have a free parameter b to analyze this
way; Ideal Donnan has none.
"""

import numpy as np

from utils.sorption_models import (
    compute_CAmw_series,
    donnan_manning,
    donnan_manning_modified,
    fit_error,
    manning_b_fitter,
    manning_b_fitter_modified,
)

DEFAULT_B_GRID = np.linspace(0.5, 50.0, 400)  # Angstrom


def _fit_b(model_key, mp, salt, params_df, css, phiw_s, CAmw, csmw_meas, metric, csmw_uncertainty):
    zg, zc, zA, T = mp["zg"], mp["zc"], mp["zA"], mp["T"]
    if model_key == "donnan_manning":
        return manning_b_fitter(salt, css, phiw_s, csmw_meas, CAmw, zg, zc, zA, T, params_df,
                                 metric=metric, csmw_uncertainty=csmw_uncertainty)
    if model_key == "donnan_manning_modified":
        return manning_b_fitter_modified(css, phiw_s, csmw_meas, CAmw, zg, zc, zA, T,
                                          metric=metric, csmw_uncertainty=csmw_uncertainty)
    raise ValueError(
        f"Uncertainty analysis needs a fittable model (donnan_manning or "
        f"donnan_manning_modified), got {model_key!r}."
    )


def _predict(model_key, mp, salt, params_df, b, css, phiw_s, CAmw):
    zg, zc, zA, T = mp["zg"], mp["zc"], mp["zA"], mp["T"]
    if model_key == "donnan_manning":
        return donnan_manning(salt, css, b, phiw_s, CAmw, zg, zc, zA, T, params_df)
    if model_key == "donnan_manning_modified":
        return donnan_manning_modified(css, b, phiw_s, CAmw, zg, zc, zA, T)
    raise ValueError(
        f"Uncertainty analysis needs a fittable model (donnan_manning or "
        f"donnan_manning_modified), got {model_key!r}."
    )


def _prep_series(dataset, css, phiw_s, csmw_meas):
    mp = dataset["membrane_params"]
    css = np.asarray(css, dtype=float)
    n = len(css)
    phiw_s_arr = np.full(n, mp["phiw_DI"]) if phiw_s is None else np.asarray(phiw_s, dtype=float)
    CAmw = compute_CAmw_series(mp["phiw_DI"], mp["CAmw_DI"], phiw_s_arr)
    csmw_meas = np.asarray(csmw_meas, dtype=float)
    return mp, css, phiw_s_arr, CAmw, csmw_meas


def bootstrap_b(model_key, dataset, css, phiw_s, csmw_meas, params_df,
                 metric="rmsle", csmw_uncertainty=None, n_resamples=200, seed=None):
    """Resample the (css, phiw_s, csmw_meas[, uncertainty]) points with replacement
    n_resamples times, refitting b each time with the given metric. Returns an array of
    n_resamples fitted b values; their spread is the bootstrap uncertainty on b."""
    mp, css, phiw_s_arr, CAmw, csmw_meas = _prep_series(dataset, css, phiw_s, csmw_meas)
    salt = mp.get("salt")
    n = len(css)
    unc = np.asarray(csmw_uncertainty, dtype=float) if csmw_uncertainty is not None else None

    rng = np.random.default_rng(seed)
    b_samples = np.empty(n_resamples)
    for i in range(n_resamples):
        idx = rng.integers(0, n, size=n)
        unc_i = unc[idx] if unc is not None else None
        try:
            b_samples[i] = _fit_b(model_key, mp, salt, params_df, css[idx], phiw_s_arr[idx],
                                   CAmw[idx], csmw_meas[idx], metric, unc_i)
        except (RuntimeError, FloatingPointError, ValueError):
            b_samples[i] = np.nan
    return b_samples


def bayesian_b_posterior(model_key, dataset, css, phiw_s, csmw_meas, params_df,
                          metric="rmsle", csmw_uncertainty=None, b_grid=None):
    """Flat-prior posterior over b via dense 1-D grid evaluation: treats n * error(b)^2 as
    -2*log-likelihood (i.e. i.i.d. Gaussian residuals in whatever space `metric` measures),
    normalized over b_grid -- a flat prior just cancels out of Bayes' rule, so the
    posterior shape here is entirely the likelihood's. Returns (b_grid, posterior_density),
    density integrating to 1 over b_grid via the trapezoid rule.
    """
    mp, css, phiw_s_arr, CAmw, csmw_meas = _prep_series(dataset, css, phiw_s, csmw_meas)
    salt = mp.get("salt")
    n = len(css)
    b_grid = DEFAULT_B_GRID if b_grid is None else np.asarray(b_grid, dtype=float)

    errors = np.empty_like(b_grid)
    for i, b in enumerate(b_grid):
        try:
            pred = _predict(model_key, mp, salt, params_df, b, css, phiw_s_arr, CAmw)
            errors[i] = fit_error(pred, csmw_meas, metric=metric, csmw_uncertainty=csmw_uncertainty)
        except (RuntimeError, FloatingPointError):
            errors[i] = np.inf

    log_L = -0.5 * n * errors**2
    finite = np.isfinite(log_L)
    if not finite.any():
        raise RuntimeError("Could not evaluate the likelihood anywhere on the b grid.")
    log_L = log_L - log_L[finite].max()
    likelihood = np.where(finite, np.exp(log_L), 0.0)
    area = np.trapezoid(likelihood, b_grid)
    posterior = likelihood / area if area > 0 else likelihood
    return b_grid, posterior


def posterior_summary(b_grid, posterior, credible=0.95):
    """Mean, median, mode, and a central credible interval from a discretized posterior.
    Report all three location statistics, not just the mean: with few data points and a
    flat prior, the likelihood can decay slowly enough that real probability mass sits far
    from the best-fit b, dragging the mean toward that tail even when the mode is sharply
    localized. That divergence is a genuine, honest signal that the data only weakly
    constrains b -- not a bug to average away."""
    mean = float(np.trapezoid(b_grid * posterior, b_grid))
    mode = float(b_grid[np.argmax(posterior)])
    cdf = np.concatenate(([0.0], np.cumsum((posterior[1:] + posterior[:-1]) / 2 * np.diff(b_grid))))
    cdf = cdf / cdf[-1]
    median = float(np.interp(0.5, cdf, b_grid))
    lo_q, hi_q = (1 - credible) / 2, 1 - (1 - credible) / 2
    lo = float(np.interp(lo_q, cdf, b_grid))
    hi = float(np.interp(hi_q, cdf, b_grid))
    return {"mean": mean, "median": median, "mode": mode, "ci_lo": lo, "ci_hi": hi}
