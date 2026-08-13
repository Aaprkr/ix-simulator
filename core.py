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

def simulate(selected, cin_df, Q=1000.0, EBED=0.35, L=14.76, v=0.123,
             rb=0.03375, kL=0.0021, nr=7, nz=13, npts=400):
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
        d=PFAS_DB[n]
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
        curves[n]=u[0,names.index(n),-1,:]/(C0/(PFAS_DB[n]["mw"]*1e6))
    return td,(v*td*86400)/L,curves

def analyze(curves, td, BV, cin_df, thresh):
    """Returns per-species breakthrough records and the limiting species."""
    recs=[]; first=None; first_sp=None
    for n in sorted(curves,key=lambda k:PFAS_DB[k]["KxA"]):
        s=curves[n]; C0=float(cin_df.iloc[0][n])
        i=np.where(s>=thresh)[0]
        if len(i):
            d,b=td[i[0]],BV[i[0]]
            if first is None or d<first: first,first_sp=d,n
            ds,bs=f"{d:,.0f}",f"{b:,.0f}"
        else: ds,bs="not reached","-"
        m=MCL.get(n); mh="no limit"
        if m and C0>0:
            mi=np.where(s*C0>=m)[0]
            mh=f"{td[mi[0]]:,.0f}" if len(mi) else "not reached"
        recs.append({"Species":n,"Class":PFAS_DB[n]["cls"],"Chain":f"C{PFAS_DB[n]['c']}",
            "Influent ppt":f"{C0:.1f}","Selectivity":f"{PFAS_DB[n]['KxA']:,.0f}",
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
