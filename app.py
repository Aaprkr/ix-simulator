import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import io
import sys

sys.path.append('Water_Treatment_Models/IonExchangeModel')
from ixpy import hsdmix

st.set_page_config(page_title="IX Breakthrough Simulator", layout="wide")
st.title("Ion Exchange Breakthrough Simulator")
st.caption("Built on the EPA's HSDM (Homogeneous Surface Diffusion Model)")

st.header("1. Column & Resin Parameters")

col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("Resin Capacity")
    q_mode = st.radio("How do you know resin capacity?",
                       ["Direct (Q, meq/L)", "From Qm + Density"])
    if q_mode == "Direct (Q, meq/L)":
        Q_val = st.number_input("Q (meq/L)", value=1000.0)
        Q_params = {"Q": (Q_val, "meq/L")}
    else:
        Qm_val = st.number_input("Qm (meq/g)", value=1.5)
        RHOP_val = st.number_input("Resin Density, RHOP (lb/ft3)", value=39.33)
        Q_params = {"Qm": (Qm_val, "meq/g"), "RHOP": (RHOP_val, "lb/ft3")}

    EBED_val = st.number_input("Bed Porosity (EBED, 0-1)", value=0.38, min_value=0.0, max_value=1.0)
    rb_val = st.number_input("Bead Radius, rb (cm)", value=0.0345, format="%.4f")

with col2:
    st.subheader("Column Size & Flow")
    L_val = st.number_input("Length, L (in)", value=34.0)
    flow_mode = st.radio("Flow specified as:", ["Linear velocity (v)", "Flow rate + diameter"])
    if flow_mode == "Linear velocity (v)":
        v_val = st.number_input("Velocity, v (cm/s)", value=1.0)
        diam_val = st.number_input("Diameter, diam (in)", value=10.2)
        flow_params = {"v": (v_val, "cm/s"), "diam": (diam_val, "in")}
    else:
        flrt_val = st.number_input("Flow Rate, flrt (gpm)", value=5.0)
        diam_val = st.number_input("Diameter, diam (in)", value=10.2)
        flow_params = {"flrt": (flrt_val, "gpm"), "diam": (diam_val, "in")}

with col3:
    st.subheader("Mass Transfer & Numerics")
    kL_val = st.number_input("Film Transfer Coeff, kL (cm/s)", value=0.0022, format="%.5f")
    Ds_val = st.number_input("Surface Diffusion Coeff, Ds (cm2/s)", value=5.0e-8, format="%.2e")
    nr_val = st.number_input("Radial Collocation Points (nr)", value=7, min_value=3, max_value=20)
    nz_val = st.number_input("Axial Collocation Points (nz)", value=13, min_value=5, max_value=40)
    time_units = st.selectbox("Time Units", ["hr", "day"])

st.header("2. Ions")
st.caption("Every ion in the system must be listed, including counterions like chloride, sulfate, bicarbonate, and nitrate, not just your target contaminant. HSDM always models competitive exchange.")

default_ions = pd.DataFrame({
    "name": ["CHLORIDE", "SULFATE", "BICARBONATE", "NITRATE"],
    "mw": [35.45, 96.06, 61.02, 62.00],
    "Kxc": [1.0, 0.1, 0.6, 5.0],
    "valence": [1, 2, 1, 1],
    "units": ["meq", "meq", "meq", "meq"],
})

ions_df = st.data_editor(default_ions, num_rows="dynamic", key="ions_editor")

if not any(ions_df["name"].str.upper().isin(["BICARBONATE", "ALKALINITY"])):
    st.warning("The EPA model expects BICARBONATE or ALKALINITY to be included for proper charge balance. Results may still run but could be less accurate without it.")

st.header("3. Influent Concentration Over Time")
st.caption("Minimum 2 rows required: time 0, and simulation end time. Add more rows for variable (time-varying) influent concentrations.")

ion_names = ions_df["name"].tolist()

cin_cols = ["Time"] + ion_names
if "cin_df" not in st.session_state or list(st.session_state.cin_df.columns) != cin_cols:
    base = pd.DataFrame({"Time": [0, 50]})
    for name in ion_names:
        base[name] = [0.0, 0.0]
    st.session_state.cin_df = base

cin_df = st.data_editor(st.session_state.cin_df, num_rows="dynamic", key="cin_editor")

def build_input_excel():
    params_rows = []
    for name, (val, unit) in Q_params.items():
        params_rows.append({"name": name, "value": val, "units": unit})
    params_rows.append({"name": "EBED", "value": EBED_val, "units": None})
    params_rows.append({"name": "L", "value": L_val, "units": "in"})
    for name, (val, unit) in flow_params.items():
        params_rows.append({"name": name, "value": val, "units": unit})
    params_rows.append({"name": "rb", "value": rb_val, "units": "cm"})
    params_rows.append({"name": "kL", "value": kL_val, "units": "cm/s"})
    params_rows.append({"name": "Ds", "value": Ds_val, "units": "cm2/s"})
    params_rows.append({"name": "nr", "value": nr_val, "units": None})
    params_rows.append({"name": "nz", "value": nz_val, "units": None})
    params_rows.append({"name": "time", "value": 1.0, "units": time_units})

    params_df = pd.DataFrame(params_rows)

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        params_df.to_excel(writer, sheet_name="params", index=False)
        ions_df.to_excel(writer, sheet_name="ions", index=False)
        cin_df.to_excel(writer, sheet_name="Cin", index=False)
    buffer.seek(0)
    return buffer

st.header("4. Run Simulation")

sim_hours = st.slider("Simulation length to display (hours)", 1, int(cin_df["Time"].max()) or 48,
                       int(cin_df["Time"].max()) or 48)

if st.button("Run Simulation", type="primary"):
    try:
        excel_buffer = build_input_excel()
        IEX = hsdmix.HSDMIX(excel_buffer)
        hours = np.linspace(0, sim_hours, num=sim_hours + 1)
        t, u = IEX.solve(t_eval=hours, const_Cin=True)
        st.session_state["results"] = (t, u, ion_names)
        st.success("Simulation complete.")
    except Exception as e:
        st.error(f"Simulation failed: {e}")

if "results" in st.session_state:
    st.header("5. Results")
    t, u, names = st.session_state["results"]

    display_mode = st.radio("Display as:", ["Concentration", "C / C0", "Bed Volumes (x1000)"], horizontal=True)
    show_influent = st.checkbox("Show influent (Cin) data overlay")

    fig = go.Figure()
    for i, name in enumerate(names):
        y = u[0, i, -1, :]
        if display_mode == "C / C0" and y[0] != 0:
            y = y / y[0]
        fig.add_trace(go.Scatter(x=t, y=y, mode="lines", name=name))

    if show_influent:
        for name in ion_names:
            fig.add_trace(go.Scatter(
                x=cin_df["Time"], y=cin_df[name],
                mode="markers", name=f"{name} (influent)",
                marker=dict(symbol="x")
            ))

    xaxis_label = "Hours" if time_units == "hr" else "Days"
    if display_mode == "Bed Volumes (x1000)":
        xaxis_label = "Bed Volumes (x1000)"

    fig.update_layout(title="IX Breakthrough Curve", xaxis_title=xaxis_label,
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
