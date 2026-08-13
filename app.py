import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import io
import sys

sys.path.append('Water_Treatment_Models/IonExchangeModel')
from ixpy import hsdmix
from ixpy.paramsheets import conv_length, conv_vel

st.set_page_config(page_title="Breakthrough | PFAS Ion Exchange Simulator",
                   page_icon="◍", layout="wide", initial_sidebar_state="collapsed")

# ============================================================
#  DESIGN SYSTEM  ·  water column by depth
#  abyss #04121F · deep #072133 · mid #0B2A3D · glass rgba(255,255,255,.06)
#  accent #3DE0D0 (dissolved oxygen) · amber #FFB454 · coral #FF6B6B
# ============================================================
st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@200;300;400;600&family=Inter:wght@300;400;500&family=JetBrains+Mono:wght@300;400;600&display=swap" rel="stylesheet">
<style>
:root{
  --abyss:#04121F; --deep:#072133; --mid:#0B2A3D;
  --glass:rgba(255,255,255,.055); --glass-hi:rgba(255,255,255,.10);
  --edge:rgba(255,255,255,.14); --edge-lo:rgba(255,255,255,.07);
  --ink:#E6F3F7; --ink-dim:#8FA9B8; --ink-faint:#5F7A8A;
  --o2:#3DE0D0; --amber:#FFB454; --coral:#FF6B6B;
}
.stApp{
  background:
    radial-gradient(1200px 700px at 15% -10%, #10425C 0%, transparent 55%),
    radial-gradient(900px 600px at 90% 5%, #0A3348 0%, transparent 50%),
    linear-gradient(180deg,#072133 0%,#04121F 60%,#020A12 100%);
  background-attachment:fixed;
  color:var(--ink);
  font-family:'Inter',-apple-system,sans-serif;
}
/* caustic light drift */
.stApp::before{
  content:'';position:fixed;inset:0;pointer-events:none;z-index:0;opacity:.32;
  background:
    radial-gradient(600px 300px at 20% 20%, rgba(61,224,208,.10), transparent 60%),
    radial-gradient(500px 260px at 80% 60%, rgba(61,224,208,.06), transparent 60%);
  animation:drift 26s ease-in-out infinite alternate;
}
@keyframes drift{to{transform:translate3d(0,-26px,0) scale(1.05)}}
@media (prefers-reduced-motion:reduce){.stApp::before{animation:none}}
.block-container{position:relative;z-index:1;padding-top:2.2rem;max-width:1500px}
h1,h2,h3{font-family:'Outfit',sans-serif!important;letter-spacing:-.02em;color:var(--ink)!important}
h1{font-weight:200!important;font-size:3.1rem!important;line-height:1.02!important}
h2{font-weight:300!important;font-size:1.45rem!important;margin-top:.4rem!important}
h3{font-weight:400!important;font-size:1.05rem!important;color:var(--ink-dim)!important;
   text-transform:uppercase;letter-spacing:.13em!important;font-size:.76rem!important}
p,li,label,.stMarkdown{color:var(--ink-dim);font-size:.93rem;line-height:1.62}
strong{color:var(--ink);font-weight:500}
code{font-family:'JetBrains Mono',monospace!important;background:rgba(61,224,208,.10)!important;
     color:var(--o2)!important;padding:.12em .42em!important;border-radius:5px!important;font-size:.85em!important}

/* ---------- glass tabs ---------- */
.stTabs [data-baseweb="tab-list"]{
  gap:5px;background:var(--glass);backdrop-filter:blur(30px) saturate(170%);
  -webkit-backdrop-filter:blur(30px) saturate(170%);
  padding:6px;border-radius:17px;border:1px solid var(--edge-lo);
  box-shadow:0 8px 32px rgba(0,0,0,.32), inset 0 1px 0 rgba(255,255,255,.09);
}
.stTabs [data-baseweb="tab"]{
  background:transparent;border-radius:12px;color:var(--ink-faint);
  font-family:'Outfit',sans-serif;font-weight:400;font-size:.87rem;letter-spacing:.01em;
  padding:9px 17px;border:1px solid transparent;transition:.24s cubic-bezier(.4,0,.2,1);
}
.stTabs [data-baseweb="tab"]:hover{color:var(--ink-dim);background:rgba(255,255,255,.04)}
.stTabs [aria-selected="true"]{
  background:linear-gradient(180deg,rgba(61,224,208,.17),rgba(61,224,208,.07))!important;
  color:var(--o2)!important;border:1px solid rgba(61,224,208,.30)!important;
  box-shadow:0 2px 14px rgba(61,224,208,.16), inset 0 1px 0 rgba(255,255,255,.13);
}
.stTabs [data-baseweb="tab-highlight"],.stTabs [data-baseweb="tab-border"]{display:none}

/* ---------- inputs ---------- */
.stNumberInput input,.stTextInput input,.stSelectbox div[data-baseweb="select"]>div{
  background:rgba(255,255,255,.045)!important;border:1px solid var(--edge-lo)!important;
  border-radius:11px!important;color:var(--ink)!important;
  font-family:'JetBrains Mono',monospace!important;font-size:.87rem!important;
  backdrop-filter:blur(12px);transition:.2s;
}
.stNumberInput input:focus,.stTextInput input:focus{
  border-color:rgba(61,224,208,.5)!important;box-shadow:0 0 0 3px rgba(61,224,208,.11)!important}
.stNumberInput button{background:rgba(255,255,255,.05)!important;border:1px solid var(--edge-lo)!important;color:var(--ink-dim)!important}
[data-testid="stWidgetLabel"] p{color:var(--ink-faint)!important;font-size:.74rem!important;
  text-transform:uppercase;letter-spacing:.09em;font-weight:500}

/* ---------- buttons ---------- */
.stButton>button{
  background:linear-gradient(180deg,rgba(255,255,255,.10),rgba(255,255,255,.035))!important;
  border:1px solid var(--edge)!important;border-radius:13px!important;color:var(--ink)!important;
  font-family:'Outfit',sans-serif!important;font-weight:400!important;letter-spacing:.02em;
  padding:.58rem 1.35rem!important;backdrop-filter:blur(20px);transition:.24s cubic-bezier(.4,0,.2,1);
  box-shadow:0 4px 18px rgba(0,0,0,.22), inset 0 1px 0 rgba(255,255,255,.12);
}
.stButton>button:hover{transform:translateY(-1px);border-color:rgba(61,224,208,.38)!important;
  box-shadow:0 8px 26px rgba(61,224,208,.15), inset 0 1px 0 rgba(255,255,255,.16)}
.stButton>button[kind="primary"]{
  background:linear-gradient(180deg,rgba(61,224,208,.26),rgba(61,224,208,.11))!important;
  border:1px solid rgba(61,224,208,.42)!important;color:#BFFFF6!important;font-weight:500!important}
.stButton>button[kind="primary"]:hover{box-shadow:0 8px 30px rgba(61,224,208,.30)!important}

/* ---------- metrics as dive-computer readouts ---------- */
[data-testid="stMetric"]{
  background:var(--glass);backdrop-filter:blur(28px) saturate(170%);
  -webkit-backdrop-filter:blur(28px) saturate(170%);
  border:1px solid var(--edge-lo);border-radius:17px;padding:1.05rem 1.15rem;
  box-shadow:0 8px 30px rgba(0,0,0,.26), inset 0 1px 0 rgba(255,255,255,.09);
  transition:.28s;
}
[data-testid="stMetric"]:hover{border-color:rgba(61,224,208,.24);transform:translateY(-2px)}
[data-testid="stMetricLabel"] p{color:var(--ink-faint)!important;font-size:.68rem!important;
  text-transform:uppercase;letter-spacing:.13em!important;font-weight:500!important}
[data-testid="stMetricValue"]{font-family:'JetBrains Mono',monospace!important;
  font-weight:300!important;font-size:1.72rem!important;color:var(--o2)!important;
  letter-spacing:-.02em;text-shadow:0 0 26px rgba(61,224,208,.34)}

/* ---------- alerts ---------- */
[data-testid="stAlert"]{background:var(--glass)!important;backdrop-filter:blur(24px);
  border:1px solid var(--edge-lo)!important;border-radius:15px!important;color:var(--ink-dim)!important}
[data-testid="stAlert"] p{color:var(--ink-dim)!important}

/* ---------- dataframes ---------- */
[data-testid="stDataFrame"],[data-testid="stDataEditor"]{
  background:var(--glass);backdrop-filter:blur(24px);border:1px solid var(--edge-lo);
  border-radius:15px;padding:5px;box-shadow:0 8px 28px rgba(0,0,0,.24)}

/* ---------- expander ---------- */
[data-testid="stExpander"]{background:var(--glass);backdrop-filter:blur(22px);
  border:1px solid var(--edge-lo)!important;border-radius:15px!important;overflow:hidden}
[data-testid="stExpander"] summary{color:var(--ink-dim)!important;font-family:'Outfit',sans-serif;font-size:.86rem}

/* ---------- checkbox ---------- */
[data-testid="stCheckbox"]{background:rgba(255,255,255,.032);border:1px solid var(--edge-lo);
  border-radius:11px;padding:.5rem .7rem;margin-bottom:.4rem;transition:.2s}
[data-testid="stCheckbox"]:hover{background:rgba(61,224,208,.06);border-color:rgba(61,224,208,.22)}
[data-testid="stCheckbox"] label p{color:var(--ink)!important;font-family:'JetBrains Mono',monospace!important;
  font-size:.8rem!important;text-transform:none!important;letter-spacing:0!important}

/* slider */
.stSlider [data-baseweb="slider"] div[role="slider"]{background:var(--o2)!important;
  box-shadow:0 0 14px rgba(61,224,208,.55)!important;border:none!important}

/* radio */
.stRadio [role="radiogroup"]{gap:.35rem}
.stRadio label p{color:var(--ink-dim)!important;font-size:.85rem!important;
  text-transform:none!important;letter-spacing:0!important}

hr{border-color:var(--edge-lo)!important;margin:1.6rem 0!important}
#MainMenu,footer,header{visibility:hidden}

/* ---------- custom components ---------- */
.hero{padding:.4rem 0 1.4rem 0}
.hero .eyebrow{font-family:'JetBrains Mono',monospace;font-size:.71rem;letter-spacing:.28em;
  color:var(--o2);text-transform:uppercase;margin-bottom:.7rem;opacity:.85}
.hero h1{margin:0 0 .55rem 0}
.hero .sub{color:var(--ink-faint);font-size:.97rem;max-width:74ch;line-height:1.68}
.hero .accent{color:var(--o2);font-weight:400}

.panel{background:var(--glass);backdrop-filter:blur(30px) saturate(175%);
  -webkit-backdrop-filter:blur(30px) saturate(175%);
  border:1px solid var(--edge-lo);border-radius:19px;padding:1.5rem 1.65rem;margin:.9rem 0;
  box-shadow:0 10px 38px rgba(0,0,0,.28), inset 0 1px 0 rgba(255,255,255,.08)}
.panel h4{font-family:'Outfit',sans-serif;font-weight:400;color:var(--ink);
  margin:0 0 .7rem 0;font-size:1.02rem;letter-spacing:-.01em}
.panel p{margin:0 0 .55rem 0;font-size:.9rem}

/* the signature: limiting-species readout */
.readout{background:linear-gradient(145deg,rgba(61,224,208,.13),rgba(61,224,208,.035));
  border:1px solid rgba(61,224,208,.30);border-radius:21px;padding:1.7rem 1.9rem;
  backdrop-filter:blur(34px) saturate(190%);-webkit-backdrop-filter:blur(34px) saturate(190%);
  box-shadow:0 14px 48px rgba(0,0,0,.34), 0 0 60px rgba(61,224,208,.09),
             inset 0 1px 0 rgba(255,255,255,.15);
  position:relative;overflow:hidden;margin:.6rem 0 1.1rem 0}
.readout::after{content:'';position:absolute;top:-52%;right:-14%;width:230px;height:230px;
  background:radial-gradient(circle,rgba(61,224,208,.22),transparent 68%);pointer-events:none}
.readout .lbl{font-family:'JetBrains Mono',monospace;font-size:.68rem;letter-spacing:.22em;
  text-transform:uppercase;color:var(--o2);opacity:.9;margin-bottom:.5rem}
.readout .sp{font-family:'Outfit',sans-serif;font-size:2.7rem;font-weight:200;color:#fff;
  line-height:1;letter-spacing:-.03em;margin-bottom:.45rem}
.readout .meta{font-family:'JetBrains Mono',monospace;font-size:.85rem;color:var(--ink-dim)}
.readout .meta b{color:var(--o2);font-weight:600}

.src{font-family:'JetBrains Mono',monospace;font-size:.7rem;color:var(--ink-faint);
  letter-spacing:.02em;line-height:1.75;padding:.85rem 1.05rem;
  background:rgba(0,0,0,.22);border-left:2px solid rgba(61,224,208,.36);border-radius:0 11px 11px 0}
.src b{color:var(--o2);font-weight:400}

.chip{display:inline-block;font-family:'JetBrains Mono',monospace;font-size:.66rem;
  padding:.2rem .55rem;border-radius:6px;letter-spacing:.06em;margin-left:.4rem}
.chip-epa{background:rgba(61,224,208,.16);color:var(--o2);border:1px solid rgba(61,224,208,.3)}
.chip-der{background:rgba(255,180,84,.14);color:var(--amber);border:1px solid rgba(255,180,84,.28)}
</style>
""", unsafe_allow_html=True)

PLOT_LAYOUT = dict(
    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(255,255,255,0.018)',
    font=dict(family='JetBrains Mono, monospace', color='#8FA9B8', size=11),
    xaxis=dict(gridcolor='rgba(255,255,255,.055)', zerolinecolor='rgba(255,255,255,.09)',
               linecolor='rgba(255,255,255,.12)'),
    yaxis=dict(gridcolor='rgba(255,255,255,.055)', zerolinecolor='rgba(255,255,255,.09)',
               linecolor='rgba(255,255,255,.12)'),
    legend=dict(bgcolor='rgba(4,18,31,.62)', bordercolor='rgba(255,255,255,.10)',
                borderwidth=1, font=dict(size=10)),
    margin=dict(l=58, r=26, t=52, b=52), hovermode='x unified',
    title=dict(font=dict(family='Outfit, sans-serif', size=15, color='#E6F3F7')),
)
# depth-graded series colours: short chain = surface/warm, long chain = deep/cool
SERIES = ['#FFB454','#FFD98A','#7BE8B4','#3DE0D0','#39B8E5','#5B8DEF','#8B6FE8','#C77DFF','#FF6B9D']

# ============================================================
#  PFAS PARAMETER DATABASE
#  PFCA KxA  : EPA Water_Treatment_Models/Shiny-IEX/Examples/example_input_medium.xlsx
#  MW        : EPA Water_Treatment_Models/PSDM/PFAS_properties.xlsx
#  PFSA KxA  : 100x same-chain PFCA per ACS ES&T Water (2023) "Strong Base Anion
#              Exchange Selectivity of Nine Perfluoroalkyl Chemicals Relevant to
#              Drinking Water" (sulfonate selectivity ~2 orders higher at equal chain)
#  PFNA      : extrapolated from EPA PFCA regression, R2=0.963, 0.403 log10/CF2
#  Ordering validated against NEWMOA published breakthrough sequence.
# ============================================================
PFAS_DB = {
    "PFBA":  {"mw":214.039,"KxA":363.0,     "c":4,"cls":"PFCA","src":"EPA"},
    "PFPeA": {"mw":264.047,"KxA":513.0,     "c":5,"cls":"PFCA","src":"EPA"},
    "PFHxA": {"mw":314.054,"KxA":1778.0,    "c":6,"cls":"PFCA","src":"EPA"},
    "PFHpA": {"mw":364.062,"KxA":3311.0,    "c":7,"cls":"PFCA","src":"EPA"},
    "PFOA":  {"mw":414.070,"KxA":14791.0,   "c":8,"cls":"PFCA","src":"EPA"},
    "PFNA":  {"mw":464.080,"KxA":28248.0,   "c":9,"cls":"PFCA","src":"Extrapolated"},
    "PFBS":  {"mw":300.100,"KxA":36300.0,   "c":4,"cls":"PFSA","src":"Derived"},
    "PFHxS": {"mw":400.110,"KxA":177800.0,  "c":6,"cls":"PFSA","src":"Derived"},
    "PFOS":  {"mw":500.130,"KxA":1479100.0, "c":8,"cls":"PFSA","src":"Derived"},
}
BACKGROUND_IONS = {
    "CHLORIDE":   {"mw":35.45,"KxA":1.0,  "val":1,"default":4.99},
    "SULFATE":    {"mw":96.06,"KxA":0.028,"val":2,"default":3.12},
    "BICARBONATE":{"mw":12.00,"KxA":0.370,"val":1,"default":3.75},
    "NITRATE":    {"mw":14.00,"KxA":13.0, "val":1,"default":0.714},
}
# EPA 2024 National Primary Drinking Water Regulation, ng/L
MCL = {"PFOA":4.0,"PFOS":4.0,"PFHxS":10.0,"PFNA":10.0,"PFBS":None,
       "PFBA":None,"PFPeA":None,"PFHxA":None,"PFHpA":None}
CARY_NC = {"PFBA":18.1,"PFPeA":11.0,"PFHxA":11.0,"PFHpA":4.9,"PFOA":7.4,
           "PFNA":0.0,"PFBS":5.1,"PFHxS":3.4,"PFOS":11.0}

LENGTH_UNITS=["cm","mm","in","m","ft"]; VEL_UNITS=["cm/s","m/s","in/s","ft/s"]
FLOW_UNITS=["cm3/s","L/min","gal/min","gpm","ml/min"]; TIME_UNITS=["hr","hour","day","min","sec"]


def run_pfas_model(selected, cin_df, Q=1000.0, EBED=0.35, L=14.76, v=0.123,
                   rb=0.03375, kL=0.0021, nr=7, nz=13, npts=400):
    """Multi-component competitive ion exchange via EPA's HSDM engine.
    Returns (days, bed_volumes, {species: C/C0}). Input workbook built in memory."""
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
        {"name":"time","value":"day","units":"day"},
    ])
    rows=[]
    for n,d in BACKGROUND_IONS.items():
        rows.append({"name":n,"mw":d["mw"],"KxA":d["KxA"],"valence":d["val"],
                     "kL":1.0 if n=="CHLORIDE" else 0.0021,"kL_units":"cm/s",
                     "Ds":1.0 if n=="CHLORIDE" else 2e-7,"Ds_units":"cm^2/s",
                     "Dp":1.0 if n=="CHLORIDE" else 2e-6,"Dp_units":"cm^2/s",
                     "conc_units":"meq"})
    for n in selected:
        d=PFAS_DB[n]
        rows.append({"name":n,"mw":d["mw"],"KxA":d["KxA"],"valence":1,
                     "kL":0.0021,"kL_units":"cm/s","Ds":2e-7,"Ds_units":"cm^2/s",
                     "Dp":2e-6,"Dp_units":"cm^2/s","conc_units":"ng"})
    ions=pd.DataFrame(rows)

    buf=io.BytesIO()
    with pd.ExcelWriter(buf,engine="openpyxl") as w:
        params.to_excel(w,sheet_name="params",index=False)
        ions.to_excel(w,sheet_name="ions",index=False)
        cin_df.to_excel(w,sheet_name="Cin",index=False)
    buf.seek(0)

    sim_days=float(cin_df["time"].max())
    IEX=hsdmix.HSDMIX(buf)
    t,u=IEX.solve(t_eval=np.linspace(0,sim_days,num=npts),const_Cin=True)
    t_days=t/IEX.time_mult
    names=list(IEX.names)

    curves={}
    for n in selected:
        C0=float(cin_df.iloc[0][n])
        if C0<=0: continue
        j=names.index(n)
        curves[n]=u[0,j,-1,:]/(C0/(PFAS_DB[n]["mw"]*1e6))
    return t_days,(v*t_days*86400)/L,curves

st.markdown("""
<div class="hero">
  <div class="eyebrow">EPA HSDM · Multi-Component Ion Exchange</div>
  <h1>Breakthrough</h1>
  <div class="sub">Predicts when a PFAS ion exchange bed stops meeting your limit, species by species.
  Short-chain compounds break through first and can be <span class="accent">displaced off the resin</span>
  by longer-chain compounds arriving behind them, pushing effluent temporarily above influent.
  A single-species model cannot see that.</div>
</div>
""", unsafe_allow_html=True)

tab_sim, tab_col, tab_ions, tab_alk, tab_kl = st.tabs(
    ["PFAS Simulator", "Column", "Ions", "Alkalinity", "kL Estimator"])

# ============================================================
#  TAB · PFAS SIMULATOR + FEASIBILITY
# ============================================================
with tab_sim:
    st.markdown("""<div class="src">
    <b>PFCA selectivity</b> — EPA Water_Treatment_Models / Shiny-IEX / Examples / example_input_medium.xlsx<br>
    <b>Molecular weights</b> — EPA Water_Treatment_Models / PSDM / PFAS_properties.xlsx<br>
    <b>PFSA selectivity</b> — 100x same-chain PFCA, per ACS ES&amp;T Water (2023), sulfonate selectivity
    reported ~2 orders of magnitude higher at equal carbon chain length<br>
    <b>PFNA</b> — extrapolated from EPA PFCA regression, R<sup>2</sup>=0.963, 0.403 log10 per CF<sub>2</sub><br>
    <b>Validation</b> — reproduces NEWMOA published order: PFBA &lt; PFPeA &lt; PFHxA &lt; PFHpA &lt; PFOA &lt; PFNA &lt; PFBS &lt; PFHxS &lt; PFOS
    </div>""", unsafe_allow_html=True)

    st.markdown("### Species measured")
    st.caption("Uncheck anything absent from your lab report. Only selected species enter the simulation.")

    ca,cb=st.columns(2)
    selected=[]
    with ca:
        st.markdown("**Carboxylates · PFCA**")
        for k in ["PFBA","PFPeA","PFHxA","PFHpA","PFOA","PFNA"]:
            d=PFAS_DB[k]
            if st.checkbox(f"{k}   C{d['c']}   K {d['KxA']:,.0f}",
                           value=k!="PFNA", key=f"s_{k}"): selected.append(k)
    with cb:
        st.markdown("**Sulfonates · PFSA**")
        for k in ["PFBS","PFHxS","PFOS"]:
            d=PFAS_DB[k]
            if st.checkbox(f"{k}   C{d['c']}   K {d['KxA']:,.0f}",
                           value=True, key=f"s_{k}"): selected.append(k)

    if not selected:
        st.info("Select at least one species to run a simulation.")
    else:
        st.markdown("### Influent")
        st.caption("PFAS in ng/L (ppt). Background ions in meq/L. Add rows for a changing source. "
                   "The final row's time sets simulation length.")

        if st.button("Load Town of Cary, NC sample"):
            base={"time":[0,3000]}
            for n,d in BACKGROUND_IONS.items(): base[n]=[d["default"]]*2
            for n in selected: base[n]=[CARY_NC.get(n,0.0)]*2
            st.session_state.pf_cin=pd.DataFrame(base)

        cols=["time"]+list(BACKGROUND_IONS.keys())+selected
        if "pf_cin" not in st.session_state or list(st.session_state.pf_cin.columns)!=cols:
            base={"time":[0,3000]}
            for n,d in BACKGROUND_IONS.items(): base[n]=[d["default"]]*2
            for n in selected: base[n]=[10.0,10.0]
            st.session_state.pf_cin=pd.DataFrame(base)

        pf_cin=st.data_editor(st.session_state.pf_cin,num_rows="dynamic",
                              key="pf_cin_ed",use_container_width=True)

        st.markdown("### Vessel, flow, cost")
        q1,q2,q3,q4=st.columns(4)
        with q1:
            pQ=st.number_input("Resin capacity Q · meq/L",value=1000.0,key="pQ")
            pEBED=st.number_input("Bed porosity",value=0.35,key="pE")
        with q2:
            pL=st.number_input("Bed depth · cm",value=14.76,key="pL")
            pDiam=st.number_input("Vessel diameter · cm",value=60.0,key="pD")
        with q3:
            pv=st.number_input("Velocity · cm/s",value=0.123,key="pv")
            pFlow=st.number_input("Flow rate · gpm",value=50.0,key="pF")
        with q4:
            pCost=st.number_input("Resin cost · $/L",value=25.0,key="pC")
            pBT=st.slider("Breakthrough threshold · %",1,50,10,key="pB")/100.0

        if st.button("Run simulation",type="primary",key="pf_run"):
            try:
                t_days,BV,curves=run_pfas_model(selected,pf_cin,Q=pQ,EBED=pEBED,L=pL,v=pv)
                if not curves:
                    st.warning("Every selected species has zero influent concentration. Enter values above.")
                else:
                    order=sorted(curves,key=lambda k:PFAS_DB[k]["KxA"])
                    first_bt=first_sp=None
                    recs=[]
                    for n in order:
                        s=curves[n]; C0=float(pf_cin.iloc[0][n])
                        idx=np.where(s>=pBT)[0]
                        if len(idx):
                            d_bt,bv_bt=t_days[idx[0]],BV[idx[0]]
                            if first_bt is None or d_bt<first_bt: first_bt,first_sp=d_bt,n
                            ds,bs=f"{d_bt:,.0f}",f"{bv_bt:,.0f}"
                        else: ds,bs="not reached","—"
                        m=MCL.get(n); mh="—"
                        if m and C0>0:
                            mi=np.where(s*C0>=m)[0]
                            mh=f"{t_days[mi[0]]:,.0f} d" if len(mi) else "not reached"
                        recs.append({"Species":n,"Class":PFAS_DB[n]["cls"],"C0 ppt":f"{C0:.1f}",
                                     "KxA":f"{PFAS_DB[n]['KxA']:,.0f}",
                                     f"Days to {pBT*100:.0f}%":ds,"Bed volumes":bs,
                                     "Days to MCL":mh,"Peak C/C0":f"{s.max():.3f}",
                                     "Displaced":"yes" if s.max()>1.02 else "no"})

                    # ---- signature readout ----
                    if first_sp:
                        bv_lim=(pv*first_bt*86400)/pL
                        st.markdown(f"""<div class="readout">
                          <div class="lbl">Limiting species · governs changeout</div>
                          <div class="sp">{first_sp}</div>
                          <div class="meta">bed life <b>{first_bt:,.0f} days</b> &nbsp;·&nbsp;
                          <b>{bv_lim:,.0f}</b> bed volumes &nbsp;·&nbsp; C{PFAS_DB[first_sp]['c']}
                          {PFAS_DB[first_sp]['cls']}</div></div>""",unsafe_allow_html=True)
                    else:
                        st.markdown(f"""<div class="readout">
                          <div class="lbl">No breakthrough in simulated window</div>
                          <div class="sp">Clear</div>
                          <div class="meta">No species reached <b>{pBT*100:.0f}%</b> within
                          {t_days[-1]:,.0f} days. Extend the influent time range to find bed life.</div>
                          </div>""",unsafe_allow_html=True)

                    fig=go.Figure()
                    for i,n in enumerate(order):
                        fig.add_trace(go.Scatter(x=BV/1000,y=curves[n],mode="lines",
                            name=f"{n} · C{PFAS_DB[n]['c']}",
                            line=dict(width=2.2,color=SERIES[i%len(SERIES)])))
                    fig.add_hline(y=1.0,line_dash="dot",line_color="rgba(255,255,255,.28)",
                                  annotation_text="influent",annotation_font_size=10)
                    fig.add_hline(y=pBT,line_dash="dash",line_color="#FF6B6B",
                                  annotation_text=f"{pBT*100:.0f}% breakthrough",annotation_font_size=10)
                    fig.update_layout(title="Competitive breakthrough",
                        xaxis_title="throughput · 1000 × bed volumes",yaxis_title="C / C₀",**PLOT_LAYOUT)
                    st.plotly_chart(fig,use_container_width=True)

                    st.markdown("### Breakthrough by species")
                    st.dataframe(pd.DataFrame(recs),use_container_width=True,hide_index=True)

                    over=[n for n,s in curves.items() if s.max()>1.02]
                    if over:
                        st.warning(f"**Chromatographic displacement — {', '.join(over)}.** "
                                   "Stronger-binding species are pushing these off the resin. Effluent is "
                                   "temporarily worse than raw water for them. Single-species models miss this.")

                    if first_bt:
                        st.markdown("### Feasibility")
                        st.caption("Bed life is set by the first species to break through, since that governs changeout.")
                        bed_L=np.pi*(pDiam/2)**2*pL/1000
                        ebct=bed_L/(pFlow*3.785); chg=365/first_bt
                        charge=bed_L*pCost; annual=charge*chg
                        gal=pFlow*60*24*365; bv_lim=(pv*first_bt*86400)/pL

                        f1,f2,f3,f4=st.columns(4)
                        f1.metric("Bed life",f"{first_bt:,.0f} d")
                        f2.metric("Bed volumes",f"{bv_lim:,.0f}")
                        f3.metric("EBCT",f"{ebct:.2f} min")
                        f4.metric("Changeouts / yr",f"{chg:.2f}")
                        g1,g2,g3=st.columns(3)
                        g1.metric("Resin charge",f"${charge:,.0f}")
                        g2.metric("Annual media",f"${annual:,.0f}")
                        g3.metric("Per 1,000 gal",f"${1000*annual/gal:.3f}")
                        st.caption(f"Treating {gal:,.0f} gal/yr. Media only — excludes vessels, "
                                   "installation, labour, and spent-resin disposal.")

                        if bv_lim<20000:
                            st.error("Short bed life. Check competing anion levels — sulfate and nitrate "
                                     "occupy the same sites PFAS needs.")
                        elif bv_lim<50000:
                            st.warning("Below the range published PFAS IX studies report. Pilot testing advised.")
                        else:
                            st.success("Within the 50,000–300,000 bed volume range published studies report.")
                        if ebct<2.0:
                            st.info(f"EBCT {ebct:.2f} min sits below the 2–5 min range typical for PFAS IX. "
                                    "A deeper bed or wider vessel raises contact time.")

                    exp=pd.DataFrame({"Days":t_days,"BedVolumes":BV})
                    for n,s in curves.items():
                        exp[f"{n}_C_C0"]=s; exp[f"{n}_ppt"]=s*float(pf_cin.iloc[0][n])
                    b=io.BytesIO(); exp.to_excel(b,index=False,engine="openpyxl"); b.seek(0)
                    st.download_button("Download results · xlsx",data=b,
                                       file_name="breakthrough_results.xlsx",key="pf_dl")
            except Exception as e:
                st.error(f"Simulation stopped: {e}")

# ============================================================
#  TAB · COLUMN  (full EPA parameter surface)
# ============================================================
with tab_col:
    st.markdown("### Resin")
    c1,c2=st.columns(2)
    with c1:
        q_mode=st.radio("Capacity basis",["Direct (Q)","From Qm + density"],key="qmode")
        if q_mode=="Direct (Q)":
            Q_val=st.number_input("Resin capacity Q",value=1400.0,key="cQ")
            Q_unit=st.selectbox("Q units",["meq/L","meq/mL"],key="cQu")
            Q_params={"Q":(Q_val,Q_unit)}
        else:
            Qm_val=st.number_input("Qm",value=1.5,key="cQm")
            Qm_unit=st.selectbox("Qm units",["meq/g","meq/kg"],key="cQmu")
            RHOP_val=st.number_input("Resin density RHOP",value=39.33,key="cR")
            RHOP_unit=st.selectbox("RHOP units",["lb/ft3","g/ml","kg/m3"],key="cRu")
            Q_params={"Qm":(Qm_val,Qm_unit),"RHOP":(RHOP_val,RHOP_unit)}
        rb_val=st.number_input("Bead radius",value=0.03375,format="%.5f",key="crb")
        rb_unit=st.selectbox("Bead radius units",LENGTH_UNITS,index=0,key="crbu")
    with c2:
        EBED_val=st.number_input("Bed porosity EBED",value=0.350,min_value=0.0,max_value=1.0,key="cE")
        st.number_input("Bead porosity EPOR · unused for HSDM",value=0.0,disabled=True,key="cEp")

    st.markdown("### Column")
    c3,c4=st.columns(2)
    with c3:
        L_val=st.number_input("Bed length",value=14.76,key="cL")
        L_unit=st.selectbox("Length units",LENGTH_UNITS,index=0,key="cLu")
        flow_mode=st.radio("Flow specified as",["Linear","Volumetric"],key="cfm")
    with c4:
        if flow_mode=="Linear":
            v_val=st.number_input("Velocity",value=0.123,key="cv")
            v_unit=st.selectbox("Velocity units",VEL_UNITS,index=0,key="cvu")
            diam_val=st.number_input("Diameter",value=4.0,key="cd")
            diam_unit=st.selectbox("Diameter units",LENGTH_UNITS,index=0,key="cdu")
            flow_params={"v":(v_val,v_unit),"diam":(diam_val,diam_unit)}
        else:
            flrt_val=st.number_input("Flow rate",value=1.546,key="cf")
            flrt_unit=st.selectbox("Flow rate units",FLOW_UNITS,index=0,key="cfu")
            diam_val=st.number_input("Diameter",value=4.0,key="cd2")
            diam_unit=st.selectbox("Diameter units",LENGTH_UNITS,index=0,key="cdu2")
            flow_params={"flrt":(flrt_val,flrt_unit),"diam":(diam_val,diam_unit)}
            v_val=None; v_unit=None

    st.markdown("### Numerics")
    c5,c6,c7=st.columns(3)
    with c5: nr_val=st.slider("Radial collocation points",3,18,7,key="cnr")
    with c6: nz_val=st.slider("Axial collocation points",3,18,13,key="cnz")
    with c7: time_units=st.selectbox("Time units",TIME_UNITS,index=0,key="ctu")

# ============================================================
#  TAB · IONS  (manual EPA-format entry)
# ============================================================
with tab_ions:
    st.markdown("### Ion list")
    st.caption("Every ion present must be listed, including counterions. HSDM always models "
               "competitive exchange. kL, Ds and Dp are set per ion, matching the EPA application.")
    default_ions=pd.DataFrame({
        "name":["CHLORIDE","SULFATE","BICARBONATE","NITRATE"],
        "mw":[35.45,96.06,61.02,62.00],"KxA":[1.0,0.028,0.37,13.0],"valence":[1,2,1,1],
        "kL":[1.0,0.0021,0.0021,0.0021],"kL_units":["cm/s"]*4,
        "Ds":[1.0,2e-7,2e-7,2e-7],"Ds_units":["cm2/s"]*4,
        "Dp":[1.0,2e-6,2e-6,2e-6],"Dp_units":["cm2/s"]*4,"conc_units":["meq"]*4})
    ions_df=st.data_editor(default_ions,num_rows="dynamic",key="ions_ed",use_container_width=True)
    if not any(ions_df["name"].str.upper().isin(["BICARBONATE","ALKALINITY"])):
        st.warning("EPA's model expects BICARBONATE or ALKALINITY present for charge balance.")

    st.markdown("### Influent over time")
    st.caption("Minimum two rows: time zero and end time. Add rows for time-varying influent.")
    ion_names=ions_df["name"].tolist()
    cin_cols=["time"]+ion_names
    if "cin_df" not in st.session_state or list(st.session_state.cin_df.columns)!=cin_cols:
        b=pd.DataFrame({"time":[0,40.5]})
        for n in ion_names: b[n]=[0.0,0.0]
        st.session_state.cin_df=b
    cin_df=st.data_editor(st.session_state.cin_df,num_rows="dynamic",key="cin_ed",use_container_width=True)

    st.markdown("### Measured effluent · optional")
    st.caption("Real column data, if you have it, to overlay against the simulated curve.")
    eff_cols=["hours"]+ion_names
    if "eff_df" not in st.session_state or list(st.session_state.eff_df.columns)!=eff_cols:
        b=pd.DataFrame({"hours":[0]})
        for n in ion_names: b[n]=[None]
        st.session_state.eff_df=b
    eff_df=st.data_editor(st.session_state.eff_df,num_rows="dynamic",key="eff_ed",use_container_width=True)

    st.markdown("### Run")
    max_t=float(cin_df["time"].max()) if len(cin_df) else 48.0
    sim_hours=st.slider("Simulation length",1,max(int(max_t),1),max(int(max_t),1),key="ion_sim")

    def build_input_excel():
        rows=[]
        for name,(val,unit) in Q_params.items(): rows.append({"name":name,"value":val,"units":unit})
        rows.append({"name":"EBED","value":EBED_val,"units":None})
        rows.append({"name":"L","value":L_val,"units":L_unit})
        for name,(val,unit) in flow_params.items(): rows.append({"name":name,"value":val,"units":unit})
        rows.append({"name":"rb","value":rb_val,"units":rb_unit})
        rows.append({"name":"nr","value":nr_val,"units":None})
        rows.append({"name":"nz","value":nz_val,"units":None})
        rows.append({"name":"time","value":1.0,"units":time_units})
        buf=io.BytesIO()
        with pd.ExcelWriter(buf,engine="openpyxl") as w:
            pd.DataFrame(rows).to_excel(w,sheet_name="params",index=False)
            ions_df.rename(columns={"KxA":"Kxc"}).to_excel(w,sheet_name="ions",index=False)
            cin_df.rename(columns={"time":"Time"}).to_excel(w,sheet_name="Cin",index=False)
        buf.seek(0); return buf

    up=st.file_uploader("Or upload a params / ions / Cin workbook",type=["xlsx"],key="ion_up")
    if st.button("Run analysis",type="primary",key="ion_run"):
        try:
            IEX=hsdmix.HSDMIX(up if up is not None else build_input_excel())
            hrs=np.linspace(0,sim_hours,num=sim_hours+1)
            t,u=IEX.solve(t_eval=hrs,const_Cin=True)
            st.session_state["ion_results"]=(t,u,ion_names,L_val,L_unit,v_val,v_unit,time_units)
            st.success("Simulation complete.")
        except Exception as e:
            st.error(f"Simulation stopped: {e}")

    if "ion_results" in st.session_state:
        t,u,names,rL,rLu,rv,rvu,tu=st.session_state["ion_results"]
        st.markdown("### Results")
        dmode=st.radio("Display",["Concentration","C / C₀","Bed volumes"],horizontal=True,key="ion_disp")
        show_in=st.checkbox("Overlay influent",key="ion_si")
        show_eff=st.checkbox("Overlay measured effluent",key="ion_se")

        if dmode=="Bed volumes" and rv is not None:
            vf,_,_=conv_vel(rvu,"cm/s","","" ); lf,_,_=conv_length(rLu,"cm","","")
            sec={"hr":3600,"hour":3600,"day":86400,"min":60,"sec":1}.get(tu,3600)
            xv=(rv*vf*t*sec)/(rL*lf)/1000; xl="bed volumes · ×1000"
        else:
            xv=t; xl="hours" if tu in ("hr","hour") else tu

        fig=go.Figure()
        for i,name in enumerate(names):
            y=u[0,i,-1,:]
            if dmode=="C / C₀" and y[0]!=0: y=y/y[0]
            fig.add_trace(go.Scatter(x=xv,y=y,mode="lines",name=name,
                                     line=dict(width=2.1,color=SERIES[i%len(SERIES)])))
        if show_in:
            for name in ion_names:
                fig.add_trace(go.Scatter(x=cin_df["time"],y=cin_df[name],mode="markers",
                    name=f"{name} in",marker=dict(symbol="x",size=7)))
        if show_eff:
            for name in ion_names:
                if name in eff_df.columns and eff_df[name].notna().any():
                    fig.add_trace(go.Scatter(x=eff_df["hours"],y=eff_df[name],mode="markers",
                        name=f"{name} measured",marker=dict(symbol="diamond",size=7)))
        fig.update_layout(title="Breakthrough",xaxis_title=xl,yaxis_title=dmode,**PLOT_LAYOUT)
        st.plotly_chart(fig,use_container_width=True)

        ex=pd.DataFrame({"Time":t})
        for i,name in enumerate(names): ex[name]=u[0,i,-1,:]
        b=io.BytesIO(); ex.to_excel(b,index=False,engine="openpyxl"); b.seek(0)
        st.download_button("Download results · xlsx",data=b,
                           file_name="ix_results.xlsx",key="ion_dl")

# ============================================================
#  TAB · ALKALINITY  (carbonate equilibrium, EPA R source)
# ============================================================
with tab_alk:
    st.markdown("### Bicarbonate from alkalinity")
    st.caption("The model takes bicarbonate. If you only have alkalinity and pH, convert here. "
               "Carbonate equilibrium constants match EPA's own implementation.")
    a1,a2=st.columns(2)
    with a1:
        alk_value=st.number_input("Alkalinity",value=100.0,key="ak")
        st.selectbox("Units",["mg/L as CaCO3"],key="aku")
    with a2:
        pH_val=st.slider("pH",6.0,11.0,7.0,0.1,key="aph")

    K1=10**-6.352; K2=10**-10.329; KW=10**-14
    h=10**-pH_val; oh=KW/h
    a_1=1/(1+h/K1+K2/h)
    a_2=1/(1+h/K2+h**2/(K1*K2))
    TOT=(alk_value/50000+h-oh)/(a_1+2*a_2)
    HCO3=a_1*TOT*1000

    if HCO3>=0:
        r1,r2,r3=st.columns(3)
        r1.metric("meq/L",f"{HCO3:.4f}")
        r2.metric("mg C/L",f"{HCO3*12:.3f}")
        r3.metric("mg HCO₃⁻/L",f"{HCO3*61:.2f}")
        st.caption("Copy the meq/L figure into the bicarbonate column of your influent table.")
    else:
        st.error("Negative bicarbonate at these inputs. Check the alkalinity and pH pairing.")

# ============================================================
#  TAB · kL ESTIMATOR  (Gnielinski, EPA R source)
# ============================================================
with tab_kl:
    st.markdown("### Film transfer coefficient")
    st.caption("Estimates kL for PFAS compounds using the Gnielinski correlation, matching EPA's "
               "calculator. Uses bead radius, bed porosity and velocity from the Column tab.")
    k1,k2=st.columns(2)
    with k1: temp_val=st.number_input("Temperature",value=23.0,key="kt")
    with k2: st.selectbox("Units",["deg C"],key="ktu")

    default_pfas=pd.DataFrame({
        "name":["GenX","NafionBP2","PFBA","PFBS","PFDA","PFHpA","PFHxA","PFHxS","PFMOAA",
                "PFNA","PFNS","PFO2HxA","PFO3OA","PFO4DA","PFOA","PFOS","PFPeA","PFMOPrA",
                "62FTS","82FTS","PFHpS","PFPrS","PFPeS"],
        "MolarVol cm3/mol":[188.6,252.2446,129.7206,162.0,292.0,212.9018,182.0,217.0,111.1296,
                            265.0,295.76882,140.5926,174.3263,212.3882,237.0,272.0,158.112,
                            139.417,254.8571,308.8713,242.0,137.4121,191.3115]})
    pfas_df=st.data_editor(default_pfas,num_rows="dynamic",key="kl_ed",use_container_width=True)

    if st.button("Estimate kL",key="kl_run"):
        try:
            if flow_mode!="Linear":
                st.error("Needs linear velocity. Switch the Column tab to Linear flow.")
            else:
                vf,_,_=conv_vel(v_unit,"cm/s","","" ); rf,_,_=conv_length(rb_unit,"cm","","")
                vel=v_val*vf; rbc=rb_val*rf
                T=temp_val+273.15
                mu=np.exp(-24.71+(4209/T)+0.04527*T-(3.376e-5*T**2))/100
                t2=T/324.65
                rho=0.98396*(-1.41768+8.97665*t2-12.2755*t2**2+7.45844*t2**3-1.73849*t2**4)
                res=[]
                for _,row in pfas_df.iterrows():
                    mv=float(row["MolarVol cm3/mol"])
                    D=13.26e-5*((mu*100)**-1.14)*(mv**-0.589)
                    dP=2*rbc; uu=vel/EBED_val
                    Re=uu*dP*(rho/mu); Sc=mu/rho/D
                    Sh=(2+0.644*Re**0.5*Sc**(1/3))*(1+1.5*(1-EBED_val))
                    res.append(Sh*D/dP)
                pfas_df["kL cm/s"]=res
                st.success(f"Water at {temp_val:.0f}°C — viscosity {mu:.5f} P, density {rho:.4f} g/cm³")
                st.dataframe(pfas_df,use_container_width=True,hide_index=True)
                st.caption("Copy a kL value into the ion table for the matching species.")
        except Exception as e:
            st.error(f"Estimate stopped: {e}")

st.markdown("""<div style="margin-top:3rem;padding-top:1.2rem;
border-top:1px solid rgba(255,255,255,.07);font-family:'JetBrains Mono',monospace;
font-size:.68rem;color:#5F7A8A;letter-spacing:.04em">
Engine — EPA Homogeneous Surface Diffusion Model, github.com/USEPA/Water_Treatment_Models ·
Screening tool, not a substitute for pilot testing
</div>""",unsafe_allow_html=True)
