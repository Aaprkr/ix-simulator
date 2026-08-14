import numpy as np, pandas as pd, io, sys
sys.path.append('Water_Treatment_Models/IonExchangeModel')
from ixpy import hsdmix

# PFCA selectivity: EPA Shiny-IEX/Examples/example_input_medium.xlsx
# MW: EPA PSDM/PFAS_properties.xlsx
# PFSA selectivity: 100x same-chain PFCA (ACS ES&T Water 2023, sulfonates ~2 orders higher)
# PFNA: extrapolated from EPA PFCA regression, R2=0.963
PFAS_DB = {
 "PFBA": {"mw":214.039,"KxA":363.0,    "c":4,"cls":"PFCA","src":"EPA measured"},
 "PFPeA":{"mw":264.047,"KxA":513.0,    "c":5,"cls":"PFCA","src":"EPA measured"},
 "PFHxA":{"mw":314.054,"KxA":1778.0,   "c":6,"cls":"PFCA","src":"EPA measured"},
 "PFHpA":{"mw":364.062,"KxA":3311.0,   "c":7,"cls":"PFCA","src":"EPA measured"},
 "PFOA": {"mw":414.070,"KxA":14791.0,  "c":8,"cls":"PFCA","src":"EPA measured"},
 "PFNA": {"mw":464.080,"KxA":28248.0,  "c":9,"cls":"PFCA","src":"Extrapolated"},
 "PFBS": {"mw":300.100,"KxA":36300.0,  "c":4,"cls":"PFSA","src":"Derived"},
 "PFHxS":{"mw":400.110,"KxA":177800.0, "c":6,"cls":"PFSA","src":"Derived"},
 "PFOS": {"mw":500.130,"KxA":1479100.0,"c":8,"cls":"PFSA","src":"Derived"},
}
BG_IONS = {
 "CHLORIDE":   {"mw":35.45,"KxA":1.0,  "val":1,"default":4.99},
 "SULFATE":    {"mw":96.06,"KxA":0.028,"val":2,"default":3.12},
 "BICARBONATE":{"mw":12.00,"KxA":0.370,"val":1,"default":3.75},
 "NITRATE":    {"mw":14.00,"KxA":13.0, "val":1,"default":0.714},
}
MCL = {"PFOA":4.0,"PFOS":4.0,"PFHxS":10.0,"PFNA":10.0,
       "PFBS":None,"PFBA":None,"PFPeA":None,"PFHxA":None,"PFHpA":None}
CARY = {"PFBA":18.1,"PFPeA":11.0,"PFHxA":11.0,"PFHpA":4.9,"PFOA":7.4,
        "PFNA":0.0,"PFBS":5.1,"PFHxS":3.4,"PFOS":11.0}


# ============================================================
# RESIN PRESETS - all values from manufacturer product data sheets
# CalRes 2301   : Calgon Carbon PDS (macroporous, tributylamine)
# AmberLite PSR2 Plus : DuPont Form No. 45-D00899-en Rev.3 Feb 2025
# Purofine PFA694E    : Purolite PDS Oct 7 2022
# ============================================================
RESINS = {
 "Custom / manual entry": None,
 "CalRes 2301 (Calgon Carbon)": {
    "Q": 510.0, "rb": 0.0290, "EBED": 0.35,
    "matrix": "Macroporous", "func": "Tributylamine", "form": "Chloride",
    "dia_um": 580, "cap_note": "min 0.51 eq/L", "wrc": "48-60 wt%",
    "note": "Only PFAS resin the vendor recommends for surface water; tolerates low-level chlorine disinfection."},
 "AmberLite PSR2 Plus (DuPont)": {
    "Q": 700.0, "rb": 0.0350, "EBED": 0.35,
    "matrix": "Gel", "func": "Quaternary amine", "form": "Chloride",
    "dia_um": 700, "cap_note": "min 0.7 eq/L", "wrc": "25-35%",
    "note": "Uniform particle size, UC <=1.1. Shipping density 690 g/L. NSF/ANSI/CAN 61 certified."},
 "Purofine PFA694E (Purolite)": {
    "Q": 700.0, "rb": 0.03375, "EBED": 0.35,
    "matrix": "Gel", "func": "Complex amino", "form": "Chloride",
    "dia_um": 675, "cap_note": "not published on PDS - 0.7 assumed", "wrc": "n/a",
    "note": "Mean diameter 675 +/- 75 um, UC max 1.3, SG 1.05. Capacity not published; verify with vendor."},
}

# LFER fitted to EPA's own PFCA selectivity series (R2 = 0.963)
LFER_SLOPE = 0.403      # log10 units per CF2
LFER_INTERCEPT = 0.824
PFSA_FACTOR = 100.0     # sulfonate vs carboxylate at equal chain, ACS ES&T Water 2023

def estimate_KxA(carbons, head="PFCA"):
    """Estimate selectivity from chain length using the LFER fitted to EPA data."""
    k = 10 ** (LFER_SLOPE * carbons + LFER_INTERCEPT)
    return k * PFSA_FACTOR if head == "PFSA" else k

def KxA_from_bedvolumes(bv_observed, bv_reference, KxA_reference):
    """Back-calculate selectivity from an observed bed-volume result.
    Bed life scales close to linearly with KxA over the practical range."""
    if bv_reference <= 0 or KxA_reference <= 0: return None
    return KxA_reference * (bv_observed / bv_reference)


def simulate(selected, cin_df, Q=1000.0, EBED=0.35, L=14.76, v=0.123,
             rb=0.03375, kL=0.0021, nr=7, nz=13, npts=400, db=None):
    db = db or PFAS_DB
    params = pd.DataFrame([
        {"name":"Q","value":Q,"units":"meq/L"},
        {"name":"EBED","value":EBED,"units":None},
        {"name":"L","value":L,"units":"cm"},
        {"name":"v","value":v,"units":"cm/s"},
        {"name":"rb","value":rb,"units":"cm"},
        {"name":"kL","value":kL,"units":"cm/s"},
        {"name":"Ds","value":0.0,"units":"cm2/s"},
        {"name":"nr","value":nr,"units":None},
        {"name":"nz","value":nz,"units":None},
        {"name":"time","value":"day","units":"day"}])
    rows=[]
    for n,d in BG_IONS.items():
        rows.append({"name":n,"mw":d["mw"],"KxA":d["KxA"],"valence":d["val"],
            "kL":1.0 if n=="CHLORIDE" else 0.0021,"kL_units":"cm/s",
            "Ds":1.0 if n=="CHLORIDE" else 2e-7,"Ds_units":"cm^2/s",
            "Dp":1.0 if n=="CHLORIDE" else 2e-6,"Dp_units":"cm^2/s","conc_units":"meq"})
    for n in selected:
        d=db[n]
        rows.append({"name":n,"mw":d["mw"],"KxA":d["KxA"],"valence":1,
            "kL":0.0021,"kL_units":"cm/s","Ds":2e-7,"Ds_units":"cm^2/s",
            "Dp":2e-6,"Dp_units":"cm^2/s","conc_units":"ng"})
    buf=io.BytesIO()
    with pd.ExcelWriter(buf,engine="openpyxl") as w:
        params.to_excel(w,sheet_name="params",index=False)
        pd.DataFrame(rows).to_excel(w,sheet_name="ions",index=False)
        cin_df.to_excel(w,sheet_name="Cin",index=False)
    buf.seek(0)
    days=float(cin_df["time"].max())
    IEX=hsdmix.HSDMIX(buf)
    t,u=IEX.solve(t_eval=np.linspace(0,days,num=npts),const_Cin=True)
    td=t/IEX.time_mult; names=list(IEX.names)
    curves={}
    for n in selected:
        C0=float(cin_df.iloc[0][n])
        if C0<=0: continue
        curves[n]=u[0,names.index(n),-1,:]/(C0/(db[n]["mw"]*1e6))
    return td,(v*td*86400)/L,curves

def analyze(curves, td, BV, cin_df, thresh, db=None, mcl=None):
    db = db or PFAS_DB
    mcl = mcl if mcl is not None else MCL
    """Returns per-species breakthrough records and the limiting species."""
    recs=[]; first=None; first_sp=None
    for n in sorted(curves,key=lambda k:db[k]["KxA"]):
        s=curves[n]; C0=float(cin_df.iloc[0][n])
        i=np.where(s>=thresh)[0]
        if len(i):
            d,b=td[i[0]],BV[i[0]]
            if first is None or d<first: first,first_sp=d,n
            ds,bs=f"{d:,.0f}",f"{b:,.0f}"
        else: ds,bs="not reached","-"
        m=mcl.get(n); mh="no limit"
        if m and C0>0:
            mi=np.where(s*C0>=m)[0]
            mh=f"{td[mi[0]]:,.0f}" if len(mi) else "not reached"
        recs.append({"Species":n,"Class":db[n]["cls"],"Chain":f"C{db[n]['c']}",
            "Influent ppt":f"{C0:.1f}","Selectivity":f"{db[n]['KxA']:,.0f}",
            "Days to threshold":ds,"Bed volumes":bs,"Days to MCL":mh,
            "Peak C/C0":f"{s.max():.3f}","Displaced":"yes" if s.max()>1.02 else "no"})
    return recs, first, first_sp


def bed_life(selected, cin_df, L, **kw):
    """Bed life in days for a given bed depth. Returns (days, limiting_species) or (None, None)."""
    thr = kw.pop("thresh", 0.10)
    td, BV, curves = simulate(selected, cin_df, L=L, **kw)
    first = None; sp = None
    for n, s in curves.items():
        i = np.where(s >= thr)[0]
        if len(i) and (first is None or td[i[0]] < first):
            first, sp = td[i[0]], n
    return first, sp


def solve_depth(selected, cin_df, target_days, lo=5.0, hi=400.0, tol=0.05,
                max_iter=6, **kw):
    """Inverse solve: bed depth L that delivers target_days of bed life.

    Bed life is very close to linear in depth, so rather than blind bisection we
    take one reference run, extrapolate linearly, then refine. Typically converges
    in 3-4 solver calls instead of ~18.
    Returns (depth_cm, achieved_days, limiting_species, converged).
    """
    kw = dict(kw); kw["npts"] = kw.get("npts", 150)   # coarser grid while searching

    L_ref = 30.0
    d_ref, sp = bed_life(selected, cin_df, L_ref, **kw)
    if d_ref is None or d_ref <= 0:
        # nothing breaks through even at a shallow bed
        return lo, None, sp, True

    L = L_ref * (target_days / d_ref)                 # linear first guess
    L = float(np.clip(L, lo, hi))
    best = (L, d_ref, sp)

    for _ in range(max_iter):
        d, sp = bed_life(selected, cin_df, L, **kw)
        if d is None:                                  # overshot into no-breakthrough
            hi = L; L = max(lo, L * 0.75); continue
        best = (L, d, sp)
        err = (d - target_days) / target_days
        if abs(err) < tol:
            return L, d, sp, True
        L_new = float(np.clip(L * (target_days / d), lo, hi))
        if abs(L_new - L) < 0.5:
            break
        L = L_new
        if L >= hi * 0.999:                            # pinned at ceiling
            d, sp = bed_life(selected, cin_df, hi, **kw)
            if d is not None and d < target_days:
                return None, d, sp, False
    return best[0], best[1], best[2], False


def sweep_depth(selected, cin_df, depths, **kw):
    """Bed life across a range of depths. Returns list of (depth, days, species)."""
    out = []
    for L in depths:
        d, sp = bed_life(selected, cin_df, L, **kw)
        out.append((L, d, sp))
    return out


# ============================================================
#  LEAD-LAG  (two vessels in series, standard IX practice)
# ============================================================
def lead_lag_life(selected, cin_df, thresh, **kw):
    """Lead-lag operation: two vessels in series. The lag vessel polishes the
    lead's effluent, so the lead can run to full exhaustion before changeout.
    Usable throughput is set by when the LAG effluent crosses the threshold.
    Modelled as a single bed of twice the depth, which is the standard
    simplification for two identical vessels in series."""
    L1 = kw.pop("L", 14.76)
    td, BV, c = simulate(selected, cin_df, L=L1, **kw)
    _, single, sp1 = analyze(c, td, BV, cin_df, thresh, db=kw.get("db"))
    td2, BV2, c2 = simulate(selected, cin_df, L=L1*2, **kw)
    _, dual, sp2 = analyze(c2, td2, BV2, cin_df, thresh, db=kw.get("db"))
    return {"single_days": single, "single_sp": sp1,
            "leadlag_days": dual, "leadlag_sp": sp2,
            "gain": (dual/single) if (single and dual) else None}


def mass_captured(curves, td, cin_df, flow_gpm, db=None):
    """Total contaminant mass retained on the resin over the run, in grams.
    Integrates (influent - effluent) x flow over time."""
    db = db or PFAS_DB
    L_per_day = flow_gpm * 3.785 * 60 * 24
    out = {}
    for n, s in curves.items():
        C0 = float(cin_df.iloc[0][n])          # ng/L
        removed_ngL = C0 * (1.0 - np.clip(s, 0, None))
        # trapezoidal integration over days -> ng, then to grams
        ng = np.trapezoid(removed_ngL, td) * L_per_day if hasattr(np, "trapezoid") \
             else np.trapz(removed_ngL, td) * L_per_day
        out[n] = ng / 1e9
    return out
