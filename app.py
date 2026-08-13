import streamlit as st
import numpy as np, pandas as pd, io, sys
import plotly.graph_objects as go

sys.path.append('Water_Treatment_Models/IonExchangeModel')
from ixpy import hsdmix
from ixpy.paramsheets import conv_length, conv_vel
from core import PFAS_DB, BG_IONS, MCL, CARY, simulate, analyze
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

# ================= SIDEBAR =================
with st.sidebar:
    st.markdown("## Breakthrough")
    st.caption("PFAS ion exchange modelling on the EPA HSDM engine")
    page = st.radio("Section", [
        "Simulator",
        "Bed & flow",
        "Selectivity data",
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

# ================= SIMULATOR =================
if page == "Simulator":
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
                td,BV,curves = simulate(selected, cin,
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
        recs,first,fsp = analyze(curves,td,BV,cin_used,thr)

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

        order=sorted(curves,key=lambda k:PFAS_DB[k]["KxA"])
        xmode=st.radio("Horizontal axis",["Bed volumes","Days"],horizontal=True)
        x = BV/1000 if xmode=="Bed volumes" else td
        xl = "throughput · 1000 bed volumes" if xmode=="Bed volumes" else "days in service"

        fig=go.Figure()
        for i,n in enumerate(order):
            fig.add_trace(go.Scatter(x=x,y=curves[n],mode="lines",
                name=f"{n} C{PFAS_DB[n]['c']}",
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
            st.caption(f"Bed {bedL:,.0f} L at ${st.session_state.cost:.0f}/L, treating "
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
    st.write("These values feed every simulation. Defaults match EPA's published example column.")
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
             "Higher values bind more strongly and exhaust later.")
    rows=[{"Species":k,"Class":d["cls"],"Chain":f"C{d['c']}","MW":f"{d['mw']:.2f}",
           "Selectivity (KxA)":f"{d['KxA']:,.0f}","MCL ng/L":MCL.get(k) or "none",
           "Provenance":d["src"]} for k,d in
          sorted(PFAS_DB.items(),key=lambda x:x[1]["KxA"])]
    st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)

    st.markdown("### Provenance")
    st.write("**EPA measured** — five carboxylates taken directly from EPA's published example "
             "workbook in Water_Treatment_Models, Shiny-IEX/Examples/example_input_medium.xlsx. "
             "Molecular weights from PSDM/PFAS_properties.xlsx.")
    st.write("**Derived** — the three sulfonates are set at 100x the same-chain carboxylate. "
             "ACS ES&T Water (2023), *Strong Base Anion Exchange Selectivity of Nine "
             "Perfluoroalkyl Chemicals Relevant to Drinking Water*, reports sulfonate "
             "selectivity roughly two orders of magnitude above carboxylates at equal chain length.")
    st.write("**Extrapolated** — PFNA from regression on EPA's own carboxylate series "
             "(R² = 0.963, 0.403 log10 units per CF2).")
    st.info("This parameter set reproduces the NEWMOA published breakthrough order exactly: "
            "PFBA < PFPeA < PFHxA < PFHpA < PFOA < PFNA < PFBS < PFHxS < PFOS. That validates "
            "ordering. Absolute magnitudes for the derived sulfonates remain unverified against "
            "column data.")

    ks=[PFAS_DB[k]["KxA"] for k in PFAS_DB]; ns=list(PFAS_DB.keys())
    o=np.argsort(ks)
    fig=go.Figure(go.Bar(x=[ns[i] for i in o],y=[ks[i] for i in o],
        marker_color=[SERIES[i%len(SERIES)] for i in range(len(ns))]))
    fig.update_layout(yaxis_type="log",yaxis_title="selectivity vs chloride (log)",
                      height=380,**PLOT)
    st.plotly_chart(fig,use_container_width=True)

# ================= ALKALINITY =================
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
