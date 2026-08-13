import streamlit as st
import numpy as np, pandas as pd, io, sys
import plotly.graph_objects as go

sys.path.append('Water_Treatment_Models/IonExchangeModel')
from ixpy import hsdmix
from ixpy.paramsheets import conv_length, conv_vel
import copy
from core import (PFAS_DB, BG_IONS, MCL, CARY, simulate, analyze,
                  bed_life, solve_depth, sweep_depth, RESINS,
                  estimate_KxA, KxA_from_bedvolumes,
                  LFER_SLOPE, LFER_INTERCEPT, PFSA_FACTOR)
from style import CSS, PLOT, SERIES

st.set_page_config(page_title="Breakthrough", page_icon="~", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)

LENGTH_U=["cm","mm","in","m","ft"]; VEL_U=["cm/s","m/s","in/s","ft/s"]
FLOW_U=["cm3/s","L/min","gal/min","gpm","ml/min"]; TIME_U=["hr","hour","day","min","sec"]

# ---------- session defaults ----------
D = st.session_state.setdefault
D("Q",1000.0); D("EBED",0.35); D("L",14.76); D("v",0.123); D("rb",0.03375)
D("kL",0.0021); D("nr",7); D("nz",13); D("diam",60.0); D("flow_gpm",50.0)
D("cost",25.0); D("thresh",10)
if "db" not in st.session_state:
    st.session_state.db = copy.deepcopy(PFAS_DB)
if "mcl" not in st.session_state:
    st.session_state.mcl = dict(MCL)
DB = st.session_state.db
MCLS = st.session_state.mcl

# ================= SIDEBAR =================
with st.sidebar:
    st.markdown("## Breakthrough")
    st.caption("PFAS ion exchange modelling on the EPA HSDM engine")
    page = st.radio("Section", [
        "Dashboard",
        "Simulator",
        "Design solver",
        "Bed & flow",
        "Selectivity data",
        "Selectivity calculator",
        "Alkalinity converter",
        "Film transfer estimator",
    ], label_visibility="collapsed")

    st.divider()
    st.markdown("###### Current bed")
    st.caption(
        f"Q {st.session_state.Q:,.0f} meq/L\n\n"
        f"L {st.session_state.L:.2f} cm · v {st.session_state.v:.3f} cm/s\n\n"
        f"porosity {st.session_state.EBED:.2f}")
    bedL = np.pi*(st.session_state.diam/2)**2*st.session_state.L/1000
    ebct = bedL/(st.session_state.flow_gpm*3.785)
    st.caption(f"volume {bedL:,.0f} L · EBCT {ebct:.2f} min")

# ================= DASHBOARD =================
if page == "Dashboard":
    st.title("Overview")
    bedL = np.pi*(st.session_state.diam/2)**2*st.session_state.L/1000
    ebct = bedL/(st.session_state.flow_gpm*3.785)

    if "res" not in st.session_state:
        st.info("No simulation run yet. Open the Simulator, choose your species and influent, "
                "then return here for the summary.")
        st.markdown("### Current bed")
        a,b,c,d = st.columns(4)
        a.metric("Bed volume", f"{bedL:,.0f} L")
        b.metric("EBCT", f"{ebct:.2f} min")
        c.metric("Bed depth", f"{st.session_state.L:.1f} cm")
        d.metric("Flow", f"{st.session_state.flow_gpm:.0f} gpm")
        st.stop()

    td, BV, curves, cin_used = st.session_state.res
    thr = st.session_state.thresh/100
    recs, first, fsp = analyze(curves, td, BV, cin_used, thr)

    st.markdown("### Compliance")
    # MCL status per regulated species
    reg = [n for n in curves if MCL.get(n)]
    cols = st.columns(max(len(reg),1)) if reg else [st]
    for col,n in zip(cols,reg):
        C0 = float(cin_used.iloc[0][n]); m = MCL[n]
        s = curves[n]; mi = np.where(s*C0 >= m)[0]
        if C0 >= m and len(mi)==0:
            col.metric(n, "compliant", f"raw {C0:.1f} > MCL {m:.0f}", delta_color="off")
        elif len(mi):
            col.metric(n, f"{td[mi[0]]:,.0f} d", f"until MCL {m:.0f} ppt", delta_color="inverse")
        else:
            col.metric(n, "holds", f"MCL {m:.0f} ppt", delta_color="normal")

    st.divider()
    st.markdown("### Bed status")
    a,b,c,d = st.columns(4)
    if fsp:
        bv_lim=(st.session_state.v*first*86400)/st.session_state.L
        a.metric("Limiting species", fsp)
        b.metric("Bed life", f"{first:,.0f} d")
        c.metric("Bed volumes", f"{bv_lim:,.0f}")
        charge=bedL*st.session_state.cost
        d.metric("Annual media", f"${charge*(365/first):,.0f}")
    else:
        a.metric("Limiting species", "none")
        b.metric("Bed life", f">{td[-1]:,.0f} d")
        c.metric("Bed volume", f"{bedL:,.0f} L")
        d.metric("EBCT", f"{ebct:.2f} min")

    # compliance timeline
    st.markdown("### Breakthrough timeline")
    st.caption(f"When each species reaches {st.session_state.thresh}% of influent.")
    tl=[]
    for n in sorted(curves,key=lambda k:DB[k]["KxA"]):
        s=curves[n]; i=np.where(s>=thr)[0]
        tl.append((n, td[i[0]] if len(i) else None))
    reached=[(n,d) for n,d in tl if d is not None]
    if reached:
        fig=go.Figure()
        fig.add_trace(go.Bar(
            y=[n for n,_ in reached], x=[d for _,d in reached], orientation='h',
            marker_color=[SERIES[i%len(SERIES)] for i in range(len(reached))],
            text=[f"{d:,.0f} d" for _,d in reached], textposition="outside"))
        fig.update_layout(xaxis_title="days to breakthrough", yaxis_title="",
                          height=60+38*len(reached), showlegend=False, **PLOT)
        st.plotly_chart(fig,use_container_width=True)
    never=[n for n,d in tl if d is None]
    if never:
        st.success(f"No breakthrough within the simulated window: {', '.join(never)}")

# ================= DESIGN SOLVER =================
elif page == "Design solver":
    st.title("Design solver")
    st.write("Works the problem backwards. Instead of asking how long a bed lasts, set the bed "
             "life you need and solve for the depth required to reach it.")

    if "cin" not in st.session_state:
        st.info("Set up species and influent in the Simulator first.")
        st.stop()
    cin = st.session_state.cin
    selected = [c for c in cin.columns if c in PFAS_DB]
    if not selected:
        st.info("No PFAS species in the current influent. Configure them in the Simulator.")
        st.stop()

    st.caption(f"Solving for: {', '.join(selected)}  ·  threshold "
               f"{st.session_state.thresh}% of influent")

    c1,c2 = st.columns(2)
    with c1:
        target = st.number_input("Target bed life · days", value=365.0, min_value=1.0)
        st.caption("365 = annual changeout. 180 = twice yearly.")
    with c2:
        maxL = st.number_input("Maximum vessel depth · cm", value=400.0, min_value=10.0)
        st.caption("Solver will not exceed this.")

    if st.button("Solve for depth", type="primary"):
        with st.spinner("Running iterative solve, takes 30-60 seconds"):
            kw = dict(Q=st.session_state.Q, EBED=st.session_state.EBED,
                      v=st.session_state.v, rb=st.session_state.rb,
                      kL=st.session_state.kL, nr=st.session_state.nr,
                      nz=st.session_state.nz, thresh=st.session_state.thresh/100)
            try:
                L_req, achieved, sp, ok = solve_depth(selected, cin, target, hi=maxL, **kw)
            except Exception as e:
                st.error(f"Solver failed: {e}"); st.stop()

        if L_req is None:
            st.error(f"Cannot reach {target:,.0f} days within {maxL:,.0f} cm. "
                     f"Deepest bed tested gives {achieved:,.0f} days, limited by {sp}. "
                     "Increase maximum depth, or reduce flow velocity in Bed & flow.")
        else:
            bedL_req = np.pi*(st.session_state.diam/2)**2*L_req/1000
            ebct_req = bedL_req/(st.session_state.flow_gpm*3.785)
            a,b,c,d = st.columns(4)
            a.metric("Required depth", f"{L_req:,.1f} cm")
            b.metric("Achieved life", f"{achieved:,.0f} d" if achieved else "no breakthrough")
            c.metric("Resin volume", f"{bedL_req:,.0f} L")
            d.metric("EBCT", f"{ebct_req:.2f} min")
            st.caption(f"Limited by {sp}. Current bed is {st.session_state.L:.1f} cm "
                       f"({L_req/st.session_state.L:.1f}x change required).")
            if not ok:
                st.warning("Solver hit its iteration limit. Treat the depth as approximate.")
            cost_req = bedL_req*st.session_state.cost
            bedL_now = np.pi*(st.session_state.diam/2)**2*st.session_state.L/1000
            cost_now = bedL_now*st.session_state.cost
            if achieved:
                st.info(f"Resin charge \\${cost_req:,.0f} at the solved depth "
                        f"(\\${cost_req*(365/achieved):,.0f} per year) "
                        f"against \\${cost_now:,.0f} for the current bed.")

    st.divider()
    st.markdown("### Depth sweep")
    st.caption("Bed life across a range of depths, so you can see the trade directly.")
    s1,s2,s3 = st.columns(3)
    with s1: d_lo=st.number_input("From · cm",value=10.0,min_value=1.0)
    with s2: d_hi=st.number_input("To · cm",value=200.0,min_value=2.0)
    with s3: d_n=st.slider("Points",3,10,6)

    if st.button("Run sweep"):
        with st.spinner(f"Running {d_n} simulations, allow ~{d_n*6} seconds"):
            kw = dict(Q=st.session_state.Q, EBED=st.session_state.EBED,
                      v=st.session_state.v, rb=st.session_state.rb,
                      kL=st.session_state.kL, nr=st.session_state.nr,
                      nz=st.session_state.nz, thresh=st.session_state.thresh/100)
            try:
                pts = sweep_depth(selected, cin, np.linspace(d_lo,d_hi,d_n), **kw)
            except Exception as e:
                st.error(f"Sweep failed: {e}"); st.stop()
        got=[(L,d) for L,d,_ in pts if d is not None]
        if got:
            fig=go.Figure()
            fig.add_trace(go.Scatter(x=[L for L,_ in got],y=[d for _,d in got],
                mode="lines+markers",line=dict(color="#40E0D0",width=2.4),
                marker=dict(size=8)))
            fig.update_layout(xaxis_title="bed depth · cm",yaxis_title="bed life · days",
                              height=400,**PLOT)
            st.plotly_chart(fig,use_container_width=True)
            tbl=pd.DataFrame([{"Depth cm":f"{L:,.1f}",
                               "Bed life days":f"{d:,.0f}" if d else "no breakthrough",
                               "Resin L":f"{np.pi*(st.session_state.diam/2)**2*L/1000:,.0f}",
                               "Limiting":sp or "-"} for L,d,sp in pts])
            st.dataframe(tbl,use_container_width=True,hide_index=True)
        else:
            st.warning("No breakthrough at any depth tested. Widen the range or extend run time.")

# ================= SIMULATOR =================
elif page == "Simulator":
    st.title("Competitive PFAS breakthrough")
    st.write("Each PFAS binds the resin with different strength, so they exhaust at different "
             "times. Short chains break through first and can be displaced off the resin by "
             "longer chains arriving behind them, driving effluent above influent.")

    c1,c2 = st.columns([3,2])
    with c1:
        st.markdown("### Species present")
        pfca = st.multiselect("Carboxylates (PFCA)",
            ["PFBA","PFPeA","PFHxA","PFHpA","PFOA","PFNA"],
            default=["PFBA","PFPeA","PFHxA","PFHpA","PFOA"])
        pfsa = st.multiselect("Sulfonates (PFSA)",
            ["PFBS","PFHxS","PFOS"], default=["PFBS","PFHxS","PFOS"])
        selected = pfca + pfsa
    with c2:
        st.markdown("### Threshold")
        st.session_state.thresh = st.slider("Breakthrough at % of influent",1,50,
                                             st.session_state.thresh)
        st.caption("10% is the convention in published column studies.")
        if st.button("Load Cary, NC sample", use_container_width=True):
            b={"time":[0,3000]}
            for n,d in BG_IONS.items(): b[n]=[d["default"]]*2
            for n in selected: b[n]=[CARY.get(n,0.0)]*2
            st.session_state.cin=pd.DataFrame(b); st.rerun()

    if not selected:
        st.info("Select at least one species above.")
        st.stop()

    st.markdown("### Influent")
    st.caption("PFAS in ng/L (ppt). Background ions in meq/L. The last row's time sets run length.")
    cols=["time"]+list(BG_IONS.keys())+selected
    if "cin" not in st.session_state or list(st.session_state.cin.columns)!=cols:
        b={"time":[0,3000]}
        for n,d in BG_IONS.items(): b[n]=[d["default"]]*2
        for n in selected: b[n]=[10.0,10.0]
        st.session_state.cin=pd.DataFrame(b)
    cin = st.data_editor(st.session_state.cin, num_rows="dynamic", use_container_width=True)

    if st.button("Run simulation", type="primary"):
        with st.spinner("Solving transport equations"):
            try:
                td,BV,curves = simulate(selected, cin, db=DB,
                    Q=st.session_state.Q, EBED=st.session_state.EBED,
                    L=st.session_state.L, v=st.session_state.v,
                    rb=st.session_state.rb, kL=st.session_state.kL,
                    nr=st.session_state.nr, nz=st.session_state.nz)
                st.session_state.res=(td,BV,curves,cin.copy())
            except Exception as e:
                st.error(f"Solver failed: {e}"); st.stop()

    if "res" in st.session_state:
        td,BV,curves,cin_used = st.session_state.res
        if not curves:
            st.warning("Every selected species has zero influent concentration.")
            st.stop()
        thr=st.session_state.thresh/100
        recs,first,fsp = analyze(curves,td,BV,cin_used,thr,db=DB,mcl=MCLS)

        st.divider()
        if fsp:
            bv_lim=(st.session_state.v*first*86400)/st.session_state.L
            m1,m2,m3,m4=st.columns(4)
            m1.metric("Limiting species",fsp)
            m2.metric("Bed life",f"{first:,.0f} d")
            m3.metric("Bed volumes",f"{bv_lim:,.0f}")
            m4.metric("Changeouts/yr",f"{365/first:.2f}")
            st.caption(f"{fsp} governs changeout — it reaches "
                       f"{st.session_state.thresh}% of influent before any other species.")
        else:
            st.success(f"No species reached {st.session_state.thresh}% within "
                       f"{td[-1]:,.0f} days. Extend the influent time range to find bed life.")

        order=sorted(curves,key=lambda k:DB[k]["KxA"])
        xmode=st.radio("Horizontal axis",["Bed volumes","Days"],horizontal=True)
        x = BV/1000 if xmode=="Bed volumes" else td
        xl = "throughput · 1000 bed volumes" if xmode=="Bed volumes" else "days in service"

        fig=go.Figure()
        for i,n in enumerate(order):
            fig.add_trace(go.Scatter(x=x,y=curves[n],mode="lines",
                name=f"{n} C{DB[n]['c']}",
                line=dict(width=2.2,color=SERIES[i%len(SERIES)])))
        fig.add_hline(y=1.0,line_dash="dot",line_color="rgba(255,255,255,0.3)")
        fig.add_hline(y=thr,line_dash="dash",line_color="#FF6B6B")
        fig.update_layout(xaxis_title=xl,yaxis_title="C / C0",height=460,**PLOT)
        st.plotly_chart(fig,use_container_width=True)

        st.markdown("### Breakthrough by species")
        st.dataframe(pd.DataFrame(recs),use_container_width=True,hide_index=True)

        over=[n for n,s in curves.items() if s.max()>1.02]
        if over:
            st.warning(f"Chromatographic displacement — {', '.join(over)} exceeded influent "
                       "concentration. Stronger-binding species are stripping these off the resin, "
                       "so effluent is briefly worse than raw water for them.")

        if first:
            st.divider()
            st.markdown("### Cost")
            bedL=np.pi*(st.session_state.diam/2)**2*st.session_state.L/1000
            charge=bedL*st.session_state.cost
            annual=charge*(365/first)
            gal=st.session_state.flow_gpm*60*24*365
            k1,k2,k3=st.columns(3)
            k1.metric("Resin charge",f"${charge:,.0f}")
            k2.metric("Annual media",f"${annual:,.0f}")
            k3.metric("Per 1000 gal",f"${1000*annual/gal:.3f}")
            st.caption(f"Bed {bedL:,.0f} L at \\${st.session_state.cost:.0f}/L, treating "
                       f"{gal:,.0f} gal/yr. Media only — excludes vessels, installation, "
                       "labour and spent-resin disposal.")
            bv_lim=(st.session_state.v*first*86400)/st.session_state.L
            if bv_lim<20000:
                st.error("Short bed life. Sulfate and nitrate compete for the same sites — "
                         "check background anion levels.")
            elif bv_lim<50000:
                st.warning("Below the range published PFAS column studies report. Pilot advised.")
            else:
                st.success("Within the 50,000–300,000 bed volume range published studies report.")

        exp=pd.DataFrame({"days":td,"bed_volumes":BV})
        for n,s in curves.items():
            exp[f"{n}_C_C0"]=s; exp[f"{n}_ppt"]=s*float(cin_used.iloc[0][n])
        b=io.BytesIO(); exp.to_excel(b,index=False,engine="openpyxl"); b.seek(0)
        st.download_button("Download results",b,"breakthrough.xlsx",use_container_width=True)

# ================= BED & FLOW =================
elif page == "Bed & flow":
    st.title("Bed and flow")
    st.write("These values feed every simulation. Pick a commercial resin to load its published "
             "specifications, or enter values manually.")

    st.markdown("### Resin selection")
    pick = st.selectbox("Commercial resin", list(RESINS.keys()), key="resin_pick")
    spec = RESINS[pick]
    if spec:
        i1,i2,i3,i4 = st.columns(4)
        i1.metric("Capacity", f"{spec['Q']:,.0f} meq/L")
        i2.metric("Bead diameter", f"{spec['dia_um']} um")
        i3.metric("Matrix", spec["matrix"])
        i4.metric("Functional group", spec["func"])
        st.caption(f"{spec['note']}  Capacity on data sheet: {spec['cap_note']}. "
                   f"Water retention: {spec['wrc']}. Ionic form: {spec['form']}.")
        if st.button("Load these specifications", type="primary"):
            st.session_state.Q=spec["Q"]; st.session_state.rb=spec["rb"]
            st.session_state.EBED=spec["EBED"]
            st.success(f"Loaded {pick}. Values below updated."); st.rerun()
        st.caption("Bed porosity defaults to 0.35 where the vendor does not publish it. "
                   "Values below stay editable after loading.")
    else:
        st.caption("Enter specifications manually below.")

    st.divider()
    c1,c2=st.columns(2)
    with c1:
        st.markdown("### Resin")
        st.session_state.Q=st.number_input("Capacity Q · meq/L",value=st.session_state.Q)
        st.session_state.rb=st.number_input("Bead radius · cm",value=st.session_state.rb,format="%.5f")
        st.session_state.EBED=st.number_input("Bed porosity",value=st.session_state.EBED,
                                               min_value=0.01,max_value=0.99)
        st.session_state.kL=st.number_input("Film transfer kL · cm/s",
                                             value=st.session_state.kL,format="%.5f")
    with c2:
        st.markdown("### Column")
        st.session_state.L=st.number_input("Bed depth · cm",value=st.session_state.L)
        st.session_state.diam=st.number_input("Vessel diameter · cm",value=st.session_state.diam)
        st.session_state.v=st.number_input("Velocity · cm/s",value=st.session_state.v,format="%.4f")
        st.session_state.flow_gpm=st.number_input("Flow rate · gpm",value=st.session_state.flow_gpm)

    st.markdown("### Numerics and cost")
    c3,c4,c5=st.columns(3)
    with c3: st.session_state.nr=st.slider("Radial collocation points",3,18,st.session_state.nr)
    with c4: st.session_state.nz=st.slider("Axial collocation points",3,18,st.session_state.nz)
    with c5: st.session_state.cost=st.number_input("Resin cost · $/L",value=st.session_state.cost)

    bedL=np.pi*(st.session_state.diam/2)**2*st.session_state.L/1000
    ebct=bedL/(st.session_state.flow_gpm*3.785)
    st.divider()
    m1,m2,m3=st.columns(3)
    m1.metric("Bed volume",f"{bedL:,.0f} L")
    m2.metric("EBCT",f"{ebct:.2f} min")
    m3.metric("Loading rate",f"{st.session_state.v*60:.1f} cm/min")
    if ebct<2.0:
        st.info(f"EBCT of {ebct:.2f} min sits below the 2–5 min range typical for PFAS ion "
                "exchange. A deeper bed or wider vessel increases contact time.")

# ================= SELECTIVITY DATA =================
elif page == "Selectivity data":
    st.title("Selectivity data")
    st.write("Selectivity relative to chloride governs the order species break through. "
             "Higher values bind more strongly and exhaust later. Every value here is editable "
             "and feeds straight into the simulator.")

    st.markdown("### Parameters")
    st.caption("Edit molecular weight, selectivity or MCL directly. Changes apply on the next run.")

    edit_df = pd.DataFrame([
        {"Species":k, "Class":d["cls"], "Carbons":d["c"], "MW":d["mw"],
         "Selectivity KxA":d["KxA"],
         "MCL ng/L":(MCLS.get(k) if MCLS.get(k) is not None else np.nan),
         "Provenance":d["src"]}
        for k,d in sorted(DB.items(), key=lambda x:x[1]["KxA"])])

    edited = st.data_editor(edit_df, use_container_width=True, hide_index=True,
        disabled=["Species","Class","Provenance"], key="sel_editor",
        column_config={
          "MW": st.column_config.NumberColumn("MW g/mol", format="%.3f"),
          "Selectivity KxA": st.column_config.NumberColumn("Selectivity KxA", format="%.0f"),
          "MCL ng/L": st.column_config.NumberColumn("MCL ng/L", format="%.1f",
                        help="Leave blank if the species has no regulatory limit"),
          "Carbons": st.column_config.NumberColumn("Chain C", format="%d"),
        })

    c1,c2 = st.columns([1,3])
    with c1:
        if st.button("Apply changes", type="primary", use_container_width=True):
            for _,r in edited.iterrows():
                sp=r["Species"]
                st.session_state.db[sp]["mw"]=float(r["MW"])
                st.session_state.db[sp]["KxA"]=float(r["Selectivity KxA"])
                st.session_state.db[sp]["c"]=int(r["Carbons"])
                v=r["MCL ng/L"]
                st.session_state.mcl[sp]=(None if pd.isna(v) else float(v))
                if abs(float(r["Selectivity KxA"])-PFAS_DB[sp]["KxA"])>1e-6:
                    st.session_state.db[sp]["src"]="User edited"
            st.success("Applied. Re-run the simulator to use these values.")
            st.rerun()
    with c2:
        if st.button("Reset to published values", use_container_width=True):
            st.session_state.db=copy.deepcopy(PFAS_DB)
            st.session_state.mcl=dict(MCL)
            st.success("Reset."); st.rerun()

    st.markdown("### Provenance")
    st.write("**EPA measured** - five carboxylates taken directly from EPA's published example "
             "workbook, Water_Treatment_Models/Shiny-IEX/Examples/example_input_medium.xlsx. "
             "Molecular weights from PSDM/PFAS_properties.xlsx.")
    st.write("**Derived** - the three sulfonates are set at 100x the same-chain carboxylate. "
             "ACS ES&T Water (2023), *Strong Base Anion Exchange Selectivity of Nine "
             "Perfluoroalkyl Chemicals Relevant to Drinking Water*, reports sulfonate selectivity "
             "roughly two orders of magnitude above carboxylates at equal chain length.")
    st.write("**Extrapolated** - PFNA from regression on EPA's own carboxylate series.")
    st.info("This set reproduces the NEWMOA published breakthrough order exactly: PFBA < PFPeA < "
            "PFHxA < PFHpA < PFOA < PFNA < PFBS < PFHxS < PFOS. That validates ordering. "
            "Absolute magnitudes for the derived sulfonates remain unverified against column data.")

    ks=[DB[k]["KxA"] for k in DB]; ns=list(DB.keys())
    o=np.argsort(ks)
    fig=go.Figure(go.Bar(x=[ns[i] for i in o],y=[ks[i] for i in o],
        marker_color=[SERIES[i%len(SERIES)] for i in range(len(ns))]))
    fig.update_layout(yaxis_type="log",yaxis_title="selectivity vs chloride (log scale)",
                      height=380,**PLOT)
    st.plotly_chart(fig,use_container_width=True)

elif page == "Selectivity calculator":
    st.title("Selectivity calculator")
    st.write("Selectivity is not published for every PFAS on every resin. This estimates it three "
             "ways: from chain length, from a measured column result, or from a paired reference "
             "compound. Any result can be written straight into the parameter table.")

    m = st.radio("Method", ["Chain length (LFER)", "From measured bed volumes",
                            "Scale from a reference species"], horizontal=True)
    st.divider()

    # ---------- 1. LFER ----------
    if m == "Chain length (LFER)":
        st.markdown("### Estimate from molecular structure")
        st.write("Each added CF2 group raises binding free energy by a near-constant amount, so "
                 "log selectivity rises linearly with chain length. The relationship below was "
                 "fitted to EPA's own five-carboxylate series.")
        st.latex(r"\log_{10}(K_{x/Cl}) = %.3f \cdot n_C + %.3f" % (LFER_SLOPE, LFER_INTERCEPT))
        st.caption(f"R2 = 0.963 against EPA data. Sulfonates are then multiplied by "
                   f"{PFSA_FACTOR:.0f}x at equal chain length, per ACS ES&T Water (2023).")

        c1,c2,c3 = st.columns(3)
        with c1: nC = st.number_input("Perfluorinated carbons", value=8, min_value=2, max_value=16)
        with c2: head = st.selectbox("Head group", ["PFCA (carboxylate)","PFSA (sulfonate)"])
        with c3: st.metric("Estimated KxA", f"{estimate_KxA(nC,'PFSA' if 'PFSA' in head else 'PFCA'):,.0f}")

        # fit quality against the species we have real EPA values for
        st.markdown("### Fit against measured values")
        rows=[]
        for k,d in DB.items():
            est=estimate_KxA(d["c"], "PFSA" if d["cls"]=="PFSA" else "PFCA")
            rows.append({"Species":k,"Class":d["cls"],"Chain":f"C{d['c']}",
                         "In table":f"{d['KxA']:,.0f}","LFER estimate":f"{est:,.0f}",
                         "Ratio":f"{est/d['KxA']:.2f}x","Provenance":d["src"]})
        st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
        st.caption("Ratio near 1.0 means the correlation reproduces the tabulated value. The LFER "
                   "is a structural estimate, not a substitute for a measured coefficient.")

        cs=np.arange(2,17)
        fig=go.Figure()
        fig.add_trace(go.Scatter(x=cs,y=[estimate_KxA(c) for c in cs],mode="lines",
            name="PFCA (fitted)",line=dict(color="#40E0D0",width=2)))
        fig.add_trace(go.Scatter(x=cs,y=[estimate_KxA(c,"PFSA") for c in cs],mode="lines",
            name="PFSA (fitted)",line=dict(color="#8B6FE8",width=2,dash="dash")))
        for k,d in DB.items():
            if d["src"]=="EPA measured":
                fig.add_trace(go.Scatter(x=[d["c"]],y=[d["KxA"]],mode="markers+text",
                    name=k,text=[k],textposition="top center",showlegend=False,
                    marker=dict(size=10,color="#FFB454")))
        fig.update_layout(yaxis_type="log",xaxis_title="perfluorinated carbons",
                          yaxis_title="selectivity vs chloride",height=420,**PLOT)
        st.plotly_chart(fig,use_container_width=True)
        est_val = estimate_KxA(nC,'PFSA' if 'PFSA' in head else 'PFCA')

    # ---------- 2. from measured bed volumes ----------
    elif m == "From measured bed volumes":
        st.markdown("### Back-calculate from a column result")
        st.write("If you have run a column and know how many bed volumes it treated before "
                 "breakthrough, selectivity can be inferred by comparison against a species whose "
                 "coefficient is already known, under the same water and bed conditions.")
        st.info("Bed life scales close to linearly with selectivity over the practical range, "
                "which is what makes this inversion possible. Verified across a sweep from "
                "KxA 363 to 36,300 in this model.")

        c1,c2 = st.columns(2)
        with c1:
            ref = st.selectbox("Reference species (known KxA)",
                               [k for k,d in DB.items() if d["src"]=="EPA measured"])
            bv_ref = st.number_input("Reference bed volumes at breakthrough", value=10827.0, min_value=1.0)
        with c2:
            bv_obs = st.number_input("Your measured bed volumes", value=50000.0, min_value=1.0)
            st.caption("From your own column test or vendor pilot data.")

        est_val = KxA_from_bedvolumes(bv_obs, bv_ref, DB[ref]["KxA"])
        k1,k2 = st.columns(2)
        k1.metric("Reference KxA", f"{DB[ref]['KxA']:,.0f}")
        k2.metric("Implied KxA", f"{est_val:,.0f}" if est_val else "-")
        st.caption(f"Your column lasted {bv_obs/bv_ref:.2f}x as long as {ref} would under the same "
                   "conditions, implying proportionally higher selectivity.")

    # ---------- 3. scale from reference ----------
    else:
        st.markdown("### Scale from a reference species")
        st.write("Useful when a vendor reports performance relative to a known compound, or when "
                 "adapting a coefficient measured on one resin to another.")
        c1,c2 = st.columns(2)
        with c1:
            ref = st.selectbox("Reference species", list(DB.keys()))
            st.metric("Reference KxA", f"{DB[ref]['KxA']:,.0f}")
        with c2:
            factor = st.number_input("Multiplier", value=1.0, min_value=0.0001, format="%.4f")
            st.caption("e.g. 100 for a sulfonate against its equal-chain carboxylate.")
        est_val = DB[ref]["KxA"]*factor
        st.metric("Resulting KxA", f"{est_val:,.0f}")

    # ---------- write back ----------
    st.divider()
    st.markdown("### Write to parameter table")
    w1,w2 = st.columns([2,1])
    with w1:
        target = st.selectbox("Assign this value to", list(DB.keys()), key="calc_target")
    with w2:
        st.metric("Value to write", f"{est_val:,.0f}" if est_val else "-")
    if st.button("Write value", type="primary"):
        if est_val:
            st.session_state.db[target]["KxA"]=float(est_val)
            st.session_state.db[target]["src"]="Calculated"
            st.success(f"{target} selectivity set to {est_val:,.0f}. Re-run the simulator to apply.")
        else:
            st.error("No value to write.")

elif page == "Alkalinity converter":
    st.title("Alkalinity to bicarbonate")
    st.write("The model takes bicarbonate in meq/L. Convert from an alkalinity and pH pair here. "
             "Carbonate equilibrium constants match EPA's implementation.")
    c1,c2=st.columns(2)
    with c1: alk=st.number_input("Alkalinity · mg/L as CaCO3",value=100.0)
    with c2: pH=st.slider("pH",6.0,11.0,7.0,0.1)
    K1=10**-6.352; K2=10**-10.329; KW=10**-14
    h=10**-pH; oh=KW/h
    a1=1/(1+h/K1+K2/h); a2=1/(1+h/K2+h**2/(K1*K2))
    hco3=a1*((alk/50000+h-oh)/(a1+2*a2))*1000
    if hco3>=0:
        m1,m2,m3=st.columns(3)
        m1.metric("meq/L",f"{hco3:.4f}")
        m2.metric("mg C/L",f"{hco3*12:.3f}")
        m3.metric("mg HCO3/L",f"{hco3*61:.2f}")
        st.caption("Enter the meq/L figure in the bicarbonate column of the influent table.")
    else:
        st.error("Negative bicarbonate at this alkalinity and pH pairing. Check both values.")

# ================= kL ESTIMATOR =================
else:
    st.title("Film transfer estimator")
    st.write("Estimates the film transfer coefficient using the Gnielinski correlation, matching "
             "EPA's calculator. Uses bead radius, porosity and velocity from Bed & flow.")
    T_c=st.number_input("Temperature · deg C",value=23.0)
    base=pd.DataFrame({
      "name":["GenX","PFBA","PFBS","PFDA","PFHpA","PFHxA","PFHxS","PFNA","PFOA","PFOS","PFPeA"],
      "MolarVol":[188.6,129.7206,162.0,292.0,212.9018,182.0,217.0,265.0,237.0,272.0,158.112]})
    tbl=st.data_editor(base,num_rows="dynamic",use_container_width=True)
    if st.button("Estimate",type="primary"):
        T=T_c+273.15
        mu=np.exp(-24.71+(4209/T)+0.04527*T-(3.376e-5*T**2))/100
        t2=T/324.65
        rho=0.98396*(-1.41768+8.97665*t2-12.2755*t2**2+7.45844*t2**3-1.73849*t2**4)
        out=[]
        for _,r in tbl.iterrows():
            D=13.26e-5*((mu*100)**-1.14)*(float(r["MolarVol"])**-0.589)
            dP=2*st.session_state.rb; u=st.session_state.v/st.session_state.EBED
            Re=u*dP*(rho/mu); Sc=mu/rho/D
            Sh=(2+0.644*Re**0.5*Sc**(1/3))*(1+1.5*(1-st.session_state.EBED))
            out.append(Sh*D/dP)
        tbl["kL cm/s"]=out
        st.caption(f"Water at {T_c:.0f} deg C — viscosity {mu:.5f} P, density {rho:.4f} g/cm3")
        st.dataframe(tbl,use_container_width=True,hide_index=True)
