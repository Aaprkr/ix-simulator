import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import io
import sys

sys.path.append('Water_Treatment_Models/IonExchangeModel')
from ixpy import hsdmix
from ixpy.paramsheets import conv_length, conv_vel

st.set_page_config(page_title="Ion Exchange Breakthrough Simulator", layout="wide")
st.title("Ion Exchange Breakthrough Simulator")
st.caption("Built on the EPA's HSDM (Homogeneous Surface Diffusion Model). Rebuilt to match the EPA's official Shiny app inputs, using the EPA's own unit conversion code internally.")

LENGTH_UNITS = ["cm", "mm", "in", "m", "ft"]
VEL_UNITS = ["cm/s", "m/s", "in/s", "ft/s"]
FLOW_UNITS = ["cm3/s", "L/min", "gal/min", "gpm", "ml/min"]
CONC_UNITS = ["meq", "mg", "ug", "ng", "mgN", "mgC", "eq", "g"]
TIME_UNITS = ["hr", "hour", "day", "min", "sec"]

st.header("Model Selection")
model_type = st.selectbox("Model Type", ["Gel-Type (HSDM)", "Macroporous (PSDM) - not yet enabled"])
if "PSDM" in model_type:
    st.warning("PSDM support is not yet implemented in this app. Defaulting to HSDM.")

st.header("Load Existing File (Optional)")
uploaded_file = st.file_uploader("Upload a pre-built .xlsx file matching the params/ions/Cin schema", type=["xlsx"])
if uploaded_file is not None:
    st.info("Uploaded file will be used directly when you click Run Simulation, bypassing the form below.")

tab1, tab2, tab3, tab4 = st.tabs(["Column Parameters", "Ions", "Alkalinity", "kL Guesser"])

with tab1:
    st.subheader("Resin Characteristics")
    c1, c2 = st.columns(2)
    with c1:
        q_mode = st.radio("Resin Capacity Basis", ["Direct (Q)", "From Qm + Density (RHOP)"])
        if q_mode == "Direct (Q)":
            Q_val = st.number_input("Resin Capacity, Q", value=1400.0)
            Q_unit = st.selectbox("Resin Capacity Units", ["meq/L", "meq/mL"])
            Q_params = {"Q": (Q_val, Q_unit)}
        else:
            Qm_val = st.number_input("Qm (capacity by mass)", value=1.5)
            Qm_unit = st.selectbox("Qm Units", ["meq/g", "meq/kg"])
            RHOP_val = st.number_input("Resin Density, RHOP", value=39.33)
            RHOP_unit = st.selectbox("RHOP Units", ["lb/ft3", "g/ml", "kg/m3"])
            Q_params = {"Qm": (Qm_val, Qm_unit), "RHOP": (RHOP_val, RHOP_unit)}

        rb_val = st.number_input("Bead Radius", value=0.03375, format="%.5f")
        rb_unit = st.selectbox("Bead Radius Units", LENGTH_UNITS, index=0)

    with c2:
        EBED_val = st.number_input("Bed Porosity (EBED, 0-1)", value=0.350, min_value=0.0, max_value=1.0)
        st.number_input("Bead Porosity (EPOR) - not used for HSDM", value=0.0, disabled=True)

    st.subheader("Column Specifications")
    c3, c4 = st.columns(2)
    with c3:
        L_val = st.number_input("Length", value=14.76)
        L_unit = st.selectbox("Length Units", LENGTH_UNITS, index=0)
        flow_mode = st.radio("Flow Specified As", ["Linear", "Volumetric"])

    with c4:
        if flow_mode == "Linear":
            v_val = st.number_input("Velocity", value=0.123)
            v_unit = st.selectbox("Velocity Units", VEL_UNITS, index=0)
            diam_val = st.number_input("Diameter", value=4.0)
            diam_unit = st.selectbox("Diameter Units", LENGTH_UNITS, index=0)
            flow_params = {"v": (v_val, v_unit), "diam": (diam_val, diam_unit)}
        else:
            flrt_val = st.number_input("Flow Rate", value=1.546)
            flrt_unit = st.selectbox("Flow Rate Units", FLOW_UNITS, index=0)
            diam_val = st.number_input("Diameter", value=4.0)
            diam_unit = st.selectbox("Diameter Units", LENGTH_UNITS, index=0)
            flow_params = {"flrt": (flrt_val, flrt_unit), "diam": (diam_val, diam_unit)}

    st.subheader("Numerics & Time")
    c5, c6, c7 = st.columns(3)
    with c5:
        nr_val = st.slider("Radial Collocation Points (nr)", 3, 18, 7)
    with c6:
        nz_val = st.slider("Axial Collocation Points (nz)", 3, 18, 13)
    with c7:
        time_units = st.selectbox("Time Units", TIME_UNITS, index=0)

with tab2:
    st.subheader("Ion List")
    st.caption("Every ion in the system must be listed, including counterions like chloride, sulfate, bicarbonate, and nitrate, not just your target contaminant. HSDM always models competitive exchange. kL, Ds, and Dp can be set per ion here, matching the EPA app's approach, rather than a single global value.")

    default_ions = pd.DataFrame({
        "name": ["CHLORIDE", "SULFATE", "BICARBONATE", "NITRATE"],
        "mw": [35.45, 96.06, 61.02, 62.00],
        "KxA": [1.0, 0.028, 0.37, 13.0],
        "valence": [1, 2, 1, 1],
        "kL": [1.0, 0.0021, 0.0021, 0.0021],
        "kL_units": ["cm/s", "cm/s", "cm/s", "cm/s"],
        "Ds": [1.0, 2e-7, 2e-7, 2e-7],
        "Ds_units": ["cm2/s", "cm2/s", "cm2/s", "cm2/s"],
        "Dp": [1.0, 2e-6, 2e-6, 2e-6],
        "Dp_units": ["cm2/s", "cm2/s", "cm2/s", "cm2/s"],
        "conc_units": ["meq", "meq", "meq", "meq"],
    })

    ions_df = st.data_editor(default_ions, num_rows="dynamic", key="ions_editor", use_container_width=True)

    if not any(ions_df["name"].str.upper().isin(["BICARBONATE", "ALKALINITY"])):
        st.warning("The EPA model expects BICARBONATE or ALKALINITY to be included for proper charge balance.")

    st.subheader("Influent Concentration Points")
    st.caption("Minimum 2 rows required: time 0, and simulation end time. Add more rows for variable (time-varying) influent concentrations.")

    ion_names = ions_df["name"].tolist()
    cin_cols = ["time"] + ion_names
    if "cin_df" not in st.session_state or list(st.session_state.cin_df.columns) != cin_cols:
        base = pd.DataFrame({"time": [0, 40.5]})
        for name in ion_names:
            base[name] = [0.0, 0.0]
        st.session_state.cin_df = base

    cin_df = st.data_editor(st.session_state.cin_df, num_rows="dynamic", key="cin_editor", use_container_width=True)

    st.subheader("Effluent Concentration Points (Optional)")
    st.caption("Real measured data, if you have it, for comparing against the simulated curve.")
    eff_cols = ["hours"] + ion_names
    if "eff_df" not in st.session_state or list(st.session_state.eff_df.columns) != eff_cols:
        base_eff = pd.DataFrame({"hours": [0]})
        for name in ion_names:
            base_eff[name] = [None]
        st.session_state.eff_df = base_eff
    eff_df = st.data_editor(st.session_state.eff_df, num_rows="dynamic", key="eff_editor", use_container_width=True)

with tab3:
    st.subheader("Bicarbonate Concentration of Alkalinity")
    st.caption("Bicarbonate is the common chemical used to measure alkalinity in this model, however, you may only have a pH reading. Use this calculator to convert.")

    ac1, ac2 = st.columns(2)
    with ac1:
        alk_value = st.number_input("Alkalinity Value", value=100.0)
        alk_units = st.selectbox("Concentration Units", ["mg/L CaCO3"])
    with ac2:
        pH_val = st.slider("pH", 6.0, 11.0, 7.0, 0.1)

    K1 = 10 ** -6.352
    K2 = 10 ** -10.329
    KW = 10 ** -14
    h_plus = 10 ** -pH_val
    oh_minus = KW / h_plus
    alpha_1 = 1 / (1 + h_plus / K1 + K2 / h_plus)
    alpha_2 = 1 / (1 + h_plus / K2 + h_plus ** 2 / (K1 * K2))
    TOTCO3_M = (alk_value / 50000 + h_plus - oh_minus) / (alpha_1 + 2 * alpha_2)
    TOTCO3_mM = 1000 * TOTCO3_M
    HCO3_mM_L = alpha_1 * TOTCO3_mM

    if HCO3_mM_L >= 0:
        bicarb_meq_L = HCO3_mM_L
        bicarb_mg_C_L = bicarb_meq_L * 12
        bicarb_mg_HCO3_L = bicarb_meq_L * 61
        r1, r2, r3 = st.columns(3)
        r1.metric("Bicarbonate (meq/L)", f"{bicarb_meq_L:.6f}")
        r2.metric("Bicarbonate (mg C/L)", f"{bicarb_mg_C_L:.5f}")
        r3.metric("Bicarbonate (mg HCO3-/L)", f"{bicarb_mg_HCO3_L:.4f}")
    else:
        st.error("INVALID: negative bicarbonate concentration at these inputs.")

with tab4:
    st.subheader("Film Transfer Coefficient (kL) Guesser")
    st.caption("Estimates kL for common PFAS compounds using the Gnielinski equation, matching the EPA's own calculator. Uses the Bead Radius, Bed Porosity, and Velocity already entered in Column Parameters.")

    kc1, kc2 = st.columns(2)
    with kc1:
        temp_val = st.number_input("Temperature", value=23.0)
    with kc2:
        temp_unit = st.selectbox("Temperature Units", ["deg C"])

    default_pfas = pd.DataFrame({
        "name": ["GenX", "NafionBP2", "PFBA", "PFBS", "PFDA", "PFHpA", "PFHxA", "PFHxS",
                 "PFMOAA", "PFNA", "PFNS", "PFO2HxA", "PFO3OA", "PFO4DA", "PFOA", "PFOS",
                 "PFPeA", "PFMOPrA", "62FTS", "82FTS", "PFHpS", "PFPrS", "PFPeS"],
        "MolarVol (cm^3/mol)": [188.6000, 252.2446, 129.7206, 162.000, 292.0000, 212.9018,
                                 182.0000, 217.00000, 111.1296, 265.000, 295.76882, 140.5926,
                                 174.3263, 212.3882, 237.000, 272.0000, 158.112, 139.417,
                                 254.8571, 308.8713, 242.00, 137.4121, 191.3115],
    })
    pfas_df = st.data_editor(default_pfas, num_rows="dynamic", key="pfas_editor", use_container_width=True)

    if st.button("Estimate Values"):
        try:
            if flow_mode != "Linear":
                st.error("kL Guesser requires linear velocity. Switch Flow Specified As to Linear in Column Parameters.")
            else:
                v_cm_s_factor, _, _ = conv_vel(v_unit, "cm/s", "", "")
                velocity_cm_s = v_val * v_cm_s_factor
                rb_cm_factor, _, _ = conv_length(rb_unit, "cm", "", "")
                rb_cm = rb_val * rb_cm_factor

                t1 = temp_val + 273.15
                viscosity = np.exp(-24.71 + (4209 / t1) + 0.04527 * t1 - (3.376e-5 * t1 ** 2)) / 100
                t2 = (temp_val + 273.15) / 324.65
                density = 0.98396 * (-1.41768 + 8.97665 * t2 - 12.2755 * t2 ** 2 + 7.45844 * t2 ** 3 - 1.73849 * t2 ** 4)

                results = []
                for _, row in pfas_df.iterrows():
                    molar_vol = row["MolarVol (cm^3/mol)"]
                    mu1 = viscosity * 100
                    diffusion_coeff = 13.26e-5 * (mu1 ** -1.14) * (float(molar_vol) ** -0.589)

                    rho_L = density
                    mu2 = viscosity
                    dP = 2 * rb_cm
                    u = velocity_cm_s / EBED_val
                    Re = u * dP * (rho_L / mu2)
                    Sc = mu2 / rho_L / diffusion_coeff
                    Sh = (2 + 0.644 * Re ** 0.5 * Sc ** (1 / 3)) * (1 + 1.5 * (1 - EBED_val))
                    kL_est = Sh * diffusion_coeff / dP
                    results.append(kL_est)

                pfas_df["kL Estimate (cm/s)"] = results
                st.success("Estimates calculated.")
                st.dataframe(pfas_df, use_container_width=True)
        except Exception as e:
            st.error(f"Estimation failed: {e}")

def build_input_excel():
    params_rows = []
    for name, (val, unit) in Q_params.items():
        params_rows.append({"name": name, "value": val, "units": unit})
    params_rows.append({"name": "EBED", "value": EBED_val, "units": None})
    params_rows.append({"name": "L", "value": L_val, "units": L_unit})
    for name, (val, unit) in flow_params.items():
        params_rows.append({"name": name, "value": val, "units": unit})
    params_rows.append({"name": "rb", "value": rb_val, "units": rb_unit})
    params_rows.append({"name": "nr", "value": nr_val, "units": None})
    params_rows.append({"name": "nz", "value": nz_val, "units": None})
    params_rows.append({"name": "time", "value": 1.0, "units": time_units})
    params_df = pd.DataFrame(params_rows)

    ions_export = ions_df.rename(columns={"KxA": "Kxc"})
    cin_export = cin_df.rename(columns={"time": "Time"})

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        params_df.to_excel(writer, sheet_name="params", index=False)
        ions_export.to_excel(writer, sheet_name="ions", index=False)
        cin_export.to_excel(writer, sheet_name="Cin", index=False)
    buffer.seek(0)
    return buffer

st.header("Run Simulation")

max_time = float(cin_df["time"].max()) if len(cin_df) else 48.0
sim_hours = st.slider("Simulation length to display (hours)", 1, max(int(max_time), 1), max(int(max_time), 1))

if st.button("Run Analysis", type="primary"):
    try:
        excel_buffer = uploaded_file if uploaded_file is not None else build_input_excel()
        IEX = hsdmix.HSDMIX(excel_buffer)
        hours = np.linspace(0, sim_hours, num=sim_hours + 1)
        t, u = IEX.solve(t_eval=hours, const_Cin=True)
        st.session_state["results"] = (t, u, ion_names, L_val, L_unit,
                                        v_val if flow_mode == "Linear" else None,
                                        v_unit if flow_mode == "Linear" else None)
        st.success("Simulation complete.")
    except Exception as e:
        st.error(f"Simulation failed: {e}")

if "results" in st.session_state:
    st.header("Results")
    t, u, names, res_L, res_L_unit, res_v, res_v_unit = st.session_state["results"]

    display_mode = st.radio("Display as:", ["Concentration", "C / C0", "Bed Volumes (x1000)"], horizontal=True)
    show_influent = st.checkbox("Show influent (Cin) data overlay")
    show_effluent = st.checkbox("Show effluent (measured) data overlay")

    if display_mode == "Bed Volumes (x1000)" and res_v is not None:
        v_factor, _, _ = conv_vel(res_v_unit, "cm/s", "", "")
        l_factor, _, _ = conv_length(res_L_unit, "cm", "", "")
        v_cm_s = res_v * v_factor
        L_cm = res_L * l_factor
        t_sec_factor = {"hr": 3600, "hour": 3600, "day": 86400, "min": 60, "sec": 1}.get(time_units, 3600)
        x_vals = (v_cm_s * t * t_sec_factor) / L_cm / 1000
        x_label = "Bed Volumes (x1000)"
    else:
        x_vals = t
        x_label = "Hours" if time_units in ("hr", "hour") else time_units.capitalize()

    fig = go.Figure()
    for i, name in enumerate(names):
        y = u[0, i, -1, :]
        if display_mode == "C / C0" and y[0] != 0:
            y = y / y[0]
        fig.add_trace(go.Scatter(x=x_vals, y=y, mode="lines", name=name))

    if show_influent:
        for name in ion_names:
            fig.add_trace(go.Scatter(
                x=cin_df["time"], y=cin_df[name],
                mode="markers", name=f"{name} (influent)", marker=dict(symbol="x")
            ))

    if show_effluent:
        for name in ion_names:
            if name in eff_df.columns and eff_df[name].notna().any():
                fig.add_trace(go.Scatter(
                    x=eff_df["hours"], y=eff_df[name],
                    mode="markers", name=f"{name} (measured)", marker=dict(symbol="diamond")
                ))

    fig.update_layout(title="IX Breakthrough Curve", xaxis_title=x_label,
                       yaxis_title=display_mode, legend_title="Click legend to toggle")
    st.plotly_chart(fig, use_container_width=True)

    export_df = pd.DataFrame({"Time": t})
    for i, name in enumerate(names):
        export_df[name] = u[0, i, -1, :]
    export_buffer = io.BytesIO()
    export_df.to_excel(export_buffer, index=False, engine="openpyxl")
    export_buffer.seek(0)
    st.download_button("Download Results (Excel)", data=export_buffer,
                        file_name="ix_simulation_results.xlsx")
