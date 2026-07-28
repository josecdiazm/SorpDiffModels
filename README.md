# SorpDiffModels

A Dash web app for modeling and predicting ion sorption in ion-exchange membranes, implementing the Ideal Donnan, Donnan–Manning, and Modified Donnan–Manning frameworks, plus a (planned) companion Manning–Meares diffusion model.

The underlying physics follows Kitto & Kamcev, *J. Polym. Sci.* **2022**, *60*, 2929–2973.

## Tabs

| Tab | Description |
|---|---|
| **Data** | Build one or more named datasets, each collapsible to a one-line summary and reopenable for editing.<ul><li>Per-dataset membrane parameters (zg, zc, zA, φw,DI, CAm,w,DI, T, salt)</li><li>A user-columned data table (add/remove/rename rows and columns freely) for concentration-dependent data</li><li>A column → model-parameter role mapping under each table, so arbitrarily-named columns (e.g. "Css (m)" vs "External conc.") still resolve unambiguously to what the model needs — the free-text column name is just for your own bookkeeping</li></ul> |
| **Sorption Models** | Pick one or more datasets and one or more models — Ideal Donnan, Donnan–Manning (Kamcev et al.), Modified Donnan–Manning (Galizia et al.) — to compare, then predict and/or fit.<ul><li>Per-dataset Predict checkbox + b input: unchecked fits b from that dataset's measured Csm,w; checked forward-predicts from a known b (both can run together)</li><li>Collapsible LaTeX derivation panel per model, from the companion derivation notes</li><li>Log-log isotherm plot — color per dataset, a distinct line shade + dash style per model — plus a results table (b, RMSLE, predicted ξ, theoretical ξ)</li></ul> |

A Manning–Meares diffusion tab is planned — see `utils/sorption_models.py` for the underlying computation already ported from the original MATLAB code.

## Setup

Requires Python 3.

```bash
git clone https://github.com/josecdiazm/SorpDiffModels.git
cd SorpDiffModels
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Running

```bash
python app.py
```

The app runs at [http://127.0.0.1:8060](http://127.0.0.1:8060).

## Notes

- `utils/sorption_models.py` implements the Donnan sorption models (Pitzer activity coefficients for the external solution, Manning counter-ion condensation theory for the membrane phase).
- `data/Pitzer Params.xlsx` is the Pitzer parameter lookup table used for solution-phase activity coefficients.
- `notebooks/` holds the original Jupyter/ipywidgets notebooks (`Ideal_Donnan_Model.ipynb`, `Donnan_Manning_Model.ipynb`) that predate this web app; kept as a reference implementation.
- **If a dataset's φw,s (water volume fraction) column is left blank**, every model falls back to holding it constant at that dataset's φw,DI for every concentration point — i.e. no osmotic deswelling correction is applied, and CAm,w works out constant at CAm,w,DI too rather than varying with concentration. Fill in φw,s per point if you want that correction. The column is all-or-nothing: partially filling it in (some rows but not others) raises a validation error rather than silently mixing measured and defaulted values.
- This is a local-only tool (server and browser on the same machine) — it is not hardened for exposure on a network.
