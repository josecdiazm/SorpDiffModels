"""
Python port of the MATLAB Donnan-Manning Sorption Analysis code
(originally: MasterCode.m, Import.m, Export.m, Donnan_Ideal.m, Donnan_Manning.m,
Manning.m, Manning_b_Fitter.m, Pitzer.m, PitzerConstants.m, PitzerTemp.m,
PitzerTempConstants.m, Bjerrum.m, WaterDielectric.m, RMSLE.m, isnumber.m)

Used by Ideal_Donnan_Model.ipynb and Donnan_Manning_Model.ipynb.

Known fix vs. the original MATLAB: Pitzer.m sets a variable named "alhpa2"
(typo) instead of "alpha2" for non-monovalent salts, which left alpha2
undefined and would crash MATLAB's fsolve for any salt where neither ion is
+/-1 valent. This port sets alpha2 = 10 there, matching the clear intent
(and the Kim & Frederick / Simoes et al. references cited in Pitzer.m).
"""

import os
import warnings
from contextlib import contextmanager
from math import lcm
import numpy as np
import pandas as pd
from scipy.optimize import fsolve, brentq

_DEFAULT_PITZER_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "Pitzer Params.xlsx"
)


def _nu(zg, zc):
    """Stoichiometric coefficients (nug, nuc). Valences arrive as floats from GUI
    widgets (e.g. -1.0), but math.lcm requires ints."""
    zg_i, zc_i = int(round(abs(zg))), int(round(abs(zc)))
    l = lcm(zg_i, zc_i)
    return l // zg_i, l // zc_i


@contextmanager
def _quiet_solver():
    """fsolve explores extreme guesses before converging; those transient steps can
    overflow exp() or trip scipy's 'not making good progress' notice even when the
    final answer is fine (mirrors MATLAB's optimset('Display','off') behavior)."""
    with warnings.catch_warnings(), np.errstate(over="ignore", invalid="ignore"):
        warnings.simplefilter("ignore", RuntimeWarning)
        yield


# ---------------------------------------------------------------------------
# Water / membrane dielectric properties
# ---------------------------------------------------------------------------

def water_dielectric(T):
    """Dielectric constant of pure water. T in degC. Valid for 0-100 degC."""
    T = np.asarray(T, dtype=float)
    if np.max(T) > 100 or np.min(T) < 0:
        raise ValueError("Temperature exceeds the viable range of water dielectric constants.")
    return 87.740 - 0.40008 * T + 9.398e-4 * T**2 - 1.410e-6 * T**3


def bjerrum_length(phiw, T):
    """Bjerrum length (Angstrom) of the membrane, assuming continuous water phase."""
    e = 1.60217662e-19
    ep0 = 8.85418782e-12
    kB = 1.38064852e-23
    constant = e**2 / (4 * np.pi * ep0 * kB) * 1e10

    ep_polymer = 6
    ep_water = water_dielectric(T)
    ep_membrane = np.asarray(phiw, dtype=float) * ep_water + (1 - np.asarray(phiw, dtype=float)) * ep_polymer
    return constant / ep_membrane / (T + 273.15)


# ---------------------------------------------------------------------------
# Pitzer solution activity coefficients
# ---------------------------------------------------------------------------

def load_pitzer_params(path=_DEFAULT_PITZER_PATH):
    """Load the Pitzer parameter lookup table. Returns a DataFrame indexed by column position."""
    return pd.read_excel(path, header=0)


def list_salts(params_df):
    return sorted(params_df.iloc[:, 0].dropna().astype(str).unique().tolist()) + ["MM"]


def _pitzer_row(params_df, salt):
    row = params_df[params_df.iloc[:, 0] == salt]
    if row.empty:
        raise ValueError(f"Salt '{salt}' not found in Pitzer Params.xlsx")
    return row.iloc[0]


def _pitzer_constants_25C(params_df, salt):
    r = _pitzer_row(params_df, salt)
    B0, B1, B2, Cphi, mmax = r.iloc[1], r.iloc[2], r.iloc[3], r.iloc[4], r.iloc[5]
    return B0, B1, B2, Cphi, mmax


def _pitzer_temp_constants(params_df, salt):
    r = _pitzer_row(params_df, salt)
    dB0, dB1, dB2, dCphi, mmax, Tmax = r.iloc[7], r.iloc[8], r.iloc[9], r.iloc[10], r.iloc[11], r.iloc[12]
    if pd.isna(Tmax):
        raise ValueError(f"Temperature derivatives not reported for {salt}.")
    return dB0, dB1, dB2, dCphi, mmax, Tmax


def _pitzer_constants(params_df, salt, T):
    if T == 25:
        return _pitzer_constants_25C(params_df, salt)

    B0, B1, B2, Cphi, mmax_orig = _pitzer_constants_25C(params_df, salt)
    dB0, dB1, dB2, dCphi, mmax_temp, Tmax = _pitzer_temp_constants(params_df, salt)
    if T > Tmax:
        raise ValueError(f"Temperature exceeds the viable range of {Tmax} ºC.")
    mmax = min(mmax_orig, mmax_temp)
    dT = T - 25
    return B0 + dB0 * dT, B1 + dB1 * dT, B2 + dB2 * dT, Cphi + dCphi * dT, mmax


def pitzer_gamma(zA, zc, salt, m, T, params_df):
    """Mean salt activity coefficient in the external solution (Pitzer model).
    zA, zc are the salt's OWN co-ion/counter-ion valences (i.e. its anion and cation) --
    this function describes bulk solution thermodynamics and has nothing to do with the
    membrane's fixed-charge valence. (Fix vs. the original MATLAB Pitzer.m: it took the
    membrane's zg here instead of zA, which is only numerically harmless for chloride-type
    monovalent co-ions; for e.g. a divalent co-ion like SO4^2- it silently mis-set the
    "all monovalent" branch, the ionic strength, and the Debye-Huckel/Cgamma terms.)"""
    m = np.asarray(m, dtype=float)

    # Modified Manning: solution activity coefficient is folded into the ratio, set to 1
    if salt == "MM":
        return np.ones_like(m)

    ep = water_dielectric(T)
    rho_solvent = 1.0

    B0, B1, B2, Cphi, mmax = _pitzer_constants(params_df, salt, T)
    if np.max(m) > mmax:
        raise ValueError(f"Concentration {np.max(m):.3f} m exceeds the maximum Pitzer concentration of {mmax:.3f} m.")

    all_monovalent = abs(zA) == 1 or abs(zc) == 1
    b = 1.2
    if all_monovalent:
        alpha1, alpha2 = 2.0, 0.0
    else:
        alpha1, alpha2 = 1.4, 10.0  # fixes the MATLAB "alhpa2" typo bug, see module docstring

    nuX, nuM = _nu(zA, zc)
    I = 0.5 * (zc**2 * nuM * m + zA**2 * nuX * m)

    NAv = 6.0221409e23
    e = 1.60217662e-19
    ep0 = 8.85418782e-12
    kB = 1.38064852e-23

    A = (2 * np.pi * NAv * rho_solvent) ** 0.5 / 3 * (
        10 * e**2 / (4 * np.pi * ep0 * ep * kB * (273.15 + T))
    ) ** 1.5

    def f(x):
        return 2 * (1 - (1 + x) * np.exp(-x)) / x**2

    def fPrime(x):
        return -2 * (1 - (1 + x + 0.5 * x**2) * np.exp(-x)) / x**2

    Bg1 = B1 * f(alpha1 * I**0.5)
    Bg2 = B2 * f(alpha2 * I**0.5) if alpha2 != 0 else np.zeros_like(I)
    if all_monovalent:
        Bg2 = np.zeros_like(I)
    Bg = B0 + Bg1 + Bg2

    BgPrime1 = B1 * fPrime(alpha1 * I**0.5) / I
    BgPrime2 = B2 * fPrime(alpha2 * I**0.5) / I if alpha2 != 0 else np.zeros_like(I)
    if all_monovalent:
        BgPrime2 = np.zeros_like(I)
    BgPrime = BgPrime1 + BgPrime2

    Cgamma = Cphi / 2 / abs(zA * zc) ** 0.5

    DH = -abs(zA * zc) * A * (I**0.5 / (1 + b * I**0.5) + 2 / b * np.log(1 + b * I**0.5))
    B = 4 * m * (nuX * nuM / (nuX + nuM)) * (Bg + I / 2 * BgPrime)
    C = 6 * m**2 * (nuX * nuM / (nuX + nuM)) * nuX * abs(zA) * Cgamma

    return np.exp(DH + B + C)


# ---------------------------------------------------------------------------
# Manning membrane-phase activity coefficients
# ---------------------------------------------------------------------------

def _gamma_g(xi, X, zg_M, zp_M, zc_M, nu_g, nu_c):
    """Counter-ion activity coefficient in the membrane -- the ORIGINAL Manning/Donnan
    model, i.e. Kamcev et al. 2016 (Phys. Chem. Chem. Phys. 18:6021-6031) Eq. 8, generalized
    to arbitrary fixed-charge valence per Kitto & Kamcev 2022 (J. Polym. Sci. 60:2929-2973)
    Eq. 11 (Kamcev is a co-author of both). Valid for xi > xicrit = 1/|zg_M*zp_M| (the
    counter-ion condensation regime, which covers essentially all real IEM systems). zg_M,
    zc_M, zp_M are the counter-ion, co-ion, and fixed-charge valence (unsigned) -- "M" for
    Manning-theory notation, since this is a different pairing from this module's zg
    (fixed-charge valence, i.e. zp_M = |zg| here).

    Note: a related but distinct source (Sujanani, UT Austin dissertation 2022, Eq. 2.21,
    not co-authored by Kamcev) uses z_g*nu_g in the exponent term below instead of z_g*z_c
    -- identical whenever gcd(counter-ion valence, co-ion valence)=1 (true for NaCl, CaCl2,
    MgCl2, Na2SO4 -- verified exact agreement), but not for e.g. MgSO4 (~1-2% difference).
    This module follows Kamcev's own two papers as "the original Manning/Donnan model.\""""
    term1 = (X / (zg_M * xi) + zg_M * nu_g) / (X * zp_M + zg_M * nu_g)
    term2 = np.exp(-0.5 * X / (X + zg_M * zc_M * xi * (nu_g + nu_c)))
    return term1 * term2


def _gamma_c(xi, X, zg_M, zc_M, nu_g, nu_c):
    """Co-ion activity coefficient in the membrane, Kamcev et al. 2016 Eq. 9 / Kitto &
    Kamcev 2022 Eq. 12. zc_M is the co-ion valence (unsigned)."""
    return np.exp(-0.5 * (zc_M / zg_M) ** 2 * X / (X + zg_M * zc_M * xi * (nu_g + nu_c)))


def manning_gamma(b, phiw, CAmw, Csmw, zg, zc, zA, T):
    """Mean ion activity coefficient in the membrane (Manning counter-ion condensation
    theory), i.e. the geometric mean gamma_MX^m = [(gamma_g^m)^nuM * (gamma_c^m)^nuX]^(1/(nuM+nuX))
    used in donnan_manning()'s Gamma (mirroring Galizia et al. 2017 Eq. 6's construction for
    the external solution). Directly implements the original Manning/Donnan model, Kamcev
    et al. 2016 Eqs. 7-9, generalized to arbitrary fixed-charge valence per Kitto & Kamcev
    2022 Eqs. 6-7, 11-12 -- cross-checked against both papers' worked equations for 1:1, 2:1
    and 2:2 salts (NaCl, CaCl2/MgCl2/Na2SO4, MgSO4 respectively), all exact. See module
    docstring for why this replaced the original MATLAB Manning.m's formula, which mixed up
    Manning-theory "z_g" (counter-ion valence) with this module's zg (fixed-charge valence)."""
    nuX, nuM = _nu(zA, zc)  # co-ion, counter-ion counts per formula unit
    X = CAmw / Csmw

    lb = bjerrum_length(phiw, T)
    xi = lb / b
    zg_M, zc_M, zp_M = abs(zc), abs(zA), abs(zg)  # Manning-theory counter-ion, co-ion, fixed-charge valence
    xicrit = 1 / (zg_M * zp_M)

    if xi > xicrit:
        gg_ = _gamma_g(xi, X, zg_M, zp_M, zc_M, nuM, nuX)
        gc_ = _gamma_c(xi, X, zg_M, zc_M, nuM, nuX)
    else:
        # Uncondensed regime (xi <= xicrit): not covered by Eqs. 2.21-2.22 above (which the
        # dissertation states apply above xicrit) and not independently verified here --
        # not expected for typical IEMs, where xicrit is usually well below a real membrane's
        # Manning parameter. Falls back to the pre-fix formula's structure as a placeholder;
        # treat results here with caution.
        gg_ = np.exp(-0.5 / (X + zc_M * (nuM + nuX)) * X * (xi / xicrit))
        gc_ = np.exp(-0.5 / (X + zc_M * (nuM + nuX)) * X * (xi / xicrit) * (zc_M / zg_M) ** 2)

    gammatot = gg_**nuM * gc_**nuX
    return gammatot ** (1 / (nuM + nuX))


# ---------------------------------------------------------------------------
# Donnan equilibrium solvers
# ---------------------------------------------------------------------------

def _check_positive(Css):
    if np.any(np.asarray(Css) <= 0):
        raise ValueError("External solution concentrations are zero or negative, check the input.")


_LOG_BRACKET = (-70.0, 12.0)  # Csmw search range in ln-space: ~4e-31 to ~1.6e5 mol/kg water


def _solve_log_csmw(resid):
    """resid(log_csmw) is monotonically increasing (mass-action LHS grows with Csmw,
    RHS is constant in Csmw), so there's exactly one root; brentq needs a bracket that
    spans it. The default range covers all physically sane cases, but manning_b_fitter's
    exploratory search over b can transiently push the root outside it, so expand
    geometrically outward from the default range if needed."""
    lo, hi = _LOG_BRACKET
    for _ in range(6):
        f_lo, f_hi = resid(lo), resid(hi)
        if np.isfinite(f_lo) and np.isfinite(f_hi) and f_lo * f_hi < 0:
            return brentq(resid, lo, hi, xtol=1e-13)
        lo, hi = lo - 40, hi + 40
    raise RuntimeError("Could not bracket a root for the Donnan equilibrium equation.")


def donnan_ideal(Css, CAmw, zg, zc, zA):
    """Ideal Donnan model. Css, CAmw: arrays (mol/kg water), per concentration point.

    Solves the mass-action + electroneutrality system directly (Galizia et al. 2017,
    J. Membr. Sci. 535:132-142, Eqs. 3 & 9, with Gamma=1):
        (C_M^m)^nuM * (C_X^m)^nuX = nuM^nuM * nuX^nuX * Css^(nuM+nuX)
        zc*C_M^m - zA*C_X^m = CAmw
    where nuM, nuX are the salt's own cation/anion stoichiometric coefficients (from zc, zA
    -- NOT the membrane's fixed-charge valence zg, which plays no role in how the external
    salt dissociates). Fix vs. the original MATLAB Donnan_Ideal.m: its general-valence
    branch (the Cg/Cg_salt/Csmnew chain, and its zg-derived stoichiometry) does not actually
    satisfy this system for any non-1:1-valence salt (verified against the paper's own
    equations); it only ever matched for 1:1 salts like NaCl, which is why this was never
    caught -- this is the case that matters for CaCl2/MgCl2 comparisons to Galizia et al.
    """
    Css = np.asarray(Css, dtype=float)
    CAmw = np.asarray(CAmw, dtype=float)
    _check_positive(Css)

    nuX, nuM = _nu(zA, zc)
    a, c = abs(zA), abs(zc)

    Csmw = np.zeros(len(Css))
    for p in range(len(Css)):
        Css_p, CAmw_p = Css[p], CAmw[p]

        def resid(log_csmw, Css_p=Css_p, CAmw_p=CAmw_p):
            CX = nuX * np.exp(log_csmw)
            CM = (CAmw_p + a * CX) / c
            lhs = nuM * np.log(CM) + nuX * np.log(CX)
            rhs = np.log(nuM**nuM * nuX**nuX) + (nuX + nuM) * np.log(Css_p)
            return lhs - rhs

        with _quiet_solver():
            sol = _solve_log_csmw(resid)
        Csmw[p] = np.exp(sol)
    return Csmw


def donnan_manning(salt, Css, b, phiw, CAmw, zg, zc, zA, T, params_df):
    """Donnan-Manning model. Css, phiw, CAmw: arrays, per concentration point.

    Same system as donnan_ideal, but with Gamma = nuM^nuM*nuX^nuX*(gspm/gmpm)^(nuM+nuX)
    (Galizia et al. 2017 Eqs. 7-8, generalized to arbitrary valence) in place of Gamma=1.
    See donnan_ideal() docstring for the fix vs. the original MATLAB Donnan_Manning.m.
    """
    Css = np.asarray(Css, dtype=float)
    phiw = np.asarray(phiw, dtype=float)
    CAmw = np.asarray(CAmw, dtype=float)
    _check_positive(Css)

    nuX, nuM = _nu(zA, zc)
    a, c = abs(zA), abs(zc)
    gspm = pitzer_gamma(zA, zc, salt, Css, T, params_df)

    Csmw = np.zeros(len(Css))
    for p in range(len(Css)):
        gspm_p, Css_p, phiw_p, CAmw_p = gspm[p], Css[p], phiw[p], CAmw[p]

        def resid(log_csmw, gspm_p=gspm_p, Css_p=Css_p, phiw_p=phiw_p, CAmw_p=CAmw_p):
            Csmw_g = np.exp(log_csmw)
            CX = nuX * Csmw_g
            CM = (CAmw_p + a * CX) / c
            gmpm = manning_gamma(b, phiw_p, CAmw_p, Csmw_g, zg, zc, zA, T)
            lhs = nuM * np.log(CM) + nuX * np.log(CX)
            rhs = (
                np.log(nuM**nuM * nuX**nuX)
                + (nuX + nuM) * np.log(gspm_p / gmpm)
                + (nuX + nuM) * np.log(Css_p)
            )
            return lhs - rhs

        with _quiet_solver():
            sol = _solve_log_csmw(resid)
        Csmw[p] = np.exp(sol)
    return Csmw


def manning_b_fitter(salt, Css, phiw, Csmw, CAmw, zg, zc, zA, T, params_df):
    """Fit the Manning parameter b (Angstrom) to measured sorption data via RMS log error."""
    Css = np.asarray(Css, dtype=float)
    _check_positive(Css)

    def error_fitter(x):
        b_guess = x[0]
        if b_guess <= 0:
            return [1e10]  # b (Angstrom) must be positive; steer the search back
        try:
            pred = donnan_manning(salt, Css, b_guess, phiw, CAmw, zg, zc, zA, T, params_df)
            LE = np.log10(pred) - np.log10(Csmw)
            return [float((np.sum(LE**2) / len(LE)) ** 0.5)]
        except (RuntimeError, FloatingPointError):
            # extreme b transiently explored by fsolve can push manning_gamma out of its
            # numerically valid range; treat as a bad fit rather than crashing the search
            return [1e10]

    with _quiet_solver():
        sol = fsolve(error_fitter, x0=[10.0], full_output=False)
    return sol[0]


def rmsle(Csmw_theoretical, Csmw_actual):
    Csmw_theoretical = np.asarray(Csmw_theoretical, dtype=float)
    Csmw_actual = np.asarray(Csmw_actual, dtype=float)
    if len(Csmw_theoretical) != len(Csmw_actual):
        raise ValueError("Number of theoretical and actual partitioning data points disagree.")
    LE = np.log10(Csmw_actual / Csmw_theoretical)
    return float((np.sum(LE**2) / len(LE)) ** 0.5)


def compute_CAmw_series(phiw_DI, CAmw_DI, phiw_s):
    """Fixed-charge concentration at each external concentration point, from phiw_s and the
    DI-water-equilibrated reference values (CAmw_DI, phiw_DI)."""
    phiw_s = np.asarray(phiw_s, dtype=float)
    CAlim = CAmw_DI * phiw_DI / (1 - phiw_DI)
    return CAlim * (1 - phiw_s) / phiw_s


# ---------------------------------------------------------------------------
# High-level entry points used by the notebook GUIs
# ---------------------------------------------------------------------------

def run_ideal_donnan(zg, zc, zA, phiw_DI, CAmw_DI, Css, phiw_s=None, Csmw_meas=None):
    """Run the Ideal Donnan model for one membrane. Returns (results DataFrame, RMSLE or None)."""
    Css = np.asarray(Css, dtype=float)
    n = len(Css)
    phiw_s_arr = np.full(n, phiw_DI) if phiw_s is None or len(phiw_s) == 0 else np.asarray(phiw_s, dtype=float)

    CAmw_s = compute_CAmw_series(phiw_DI, CAmw_DI, phiw_s_arr)
    Csmw_pred = donnan_ideal(Css, CAmw_s, zg, zc, zA)

    result = pd.DataFrame({
        "Css (m)": Css,
        "phiw_s (-)": phiw_s_arr,
        "CAm,w (m)": CAmw_s,
        "Csm,w Ideal Donnan (m)": Csmw_pred,
    })

    rmsle_val = None
    if Csmw_meas is not None and len(Csmw_meas) == n:
        Csmw_meas = np.asarray(Csmw_meas, dtype=float)
        result["Csm,w measured (m)"] = Csmw_meas
        rmsle_val = rmsle(Csmw_pred, Csmw_meas)

    return result, rmsle_val


def run_donnan_manning(salt, zg, zc, zA, phiw_DI, CAmw_DI, T, Css, params_df,
                        phiw_s=None, Csmw_meas=None, b=None):
    """Run the Donnan-Manning model for one membrane: predictive (if b given) and/or fitted
    (if measured Csmw given). Returns a dict with whichever of 'predictive'/'fitted' apply."""
    Css = np.asarray(Css, dtype=float)
    n = len(Css)
    phiw_s_arr = np.full(n, phiw_DI) if phiw_s is None or len(phiw_s) == 0 else np.asarray(phiw_s, dtype=float)
    CAmw_s = compute_CAmw_series(phiw_DI, CAmw_DI, phiw_s_arr)

    have_meas = Csmw_meas is not None and len(Csmw_meas) == n
    Csmw_meas_arr = np.asarray(Csmw_meas, dtype=float) if have_meas else None

    out = {"CAmw_s": CAmw_s, "phiw_s": phiw_s_arr}

    if b is not None:
        Csmw_pred = donnan_manning(salt, Css, b, phiw_s_arr, CAmw_s, zg, zc, zA, T, params_df)
        df = pd.DataFrame({
            "Css (m)": Css, "phiw_s (-)": phiw_s_arr, "CAm,w (m)": CAmw_s,
            "Csm,w DM Predicted (m)": Csmw_pred,
        })
        rmsle_val = None
        if have_meas:
            df["Csm,w measured (m)"] = Csmw_meas_arr
            rmsle_val = rmsle(Csmw_pred, Csmw_meas_arr)
        out["predictive"] = {"b": b, "table": df, "rmsle": rmsle_val}

    if have_meas:
        b_fit = manning_b_fitter(salt, Css, phiw_s_arr, Csmw_meas_arr, CAmw_s, zg, zc, zA, T, params_df)
        Csmw_fit = donnan_manning(salt, Css, b_fit, phiw_s_arr, CAmw_s, zg, zc, zA, T, params_df)
        xip_fit = bjerrum_length(phiw_DI, T) * abs(zg * zA) / b_fit
        df = pd.DataFrame({
            "Css (m)": Css, "phiw_s (-)": phiw_s_arr, "CAm,w (m)": CAmw_s,
            "Csm,w DM Fitted (m)": Csmw_fit, "Csm,w measured (m)": Csmw_meas_arr,
        })
        rmsle_val = rmsle(Csmw_fit, Csmw_meas_arr)
        out["fitted"] = {"b_fit": b_fit, "xip_fit": xip_fit, "table": df, "rmsle": rmsle_val}

    return out
