import streamlit as st
import numpy as np
import plotly.graph_objects as go
import sys
sys.path.append('Water_Treatment_Models/IonExchangeModel')
from ixpy import hsdmix
st.set_page_config(page_title="IX Breakthrough Simulator", layout="centered")
st.title("Ion Exchange Breakthrough Simulator")
st.write("Based on the EPA's HSDM ion exchange model.")

hours_max = st.slider("Simulation length (hours)", 12, 96, 48)
run = st.button("Run Simulation")

if run:
    hours = np.linspace(0, hours_max, num=hours_max+1)
    IEX = hsdmix.HSDMIX('Water_Treatment_Models/IonExchangeModel/test/data/reg_test_input.xlsx')
    t, u = IEX.solve(t_eval=hours, const_Cin=True)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=t, y=u[0,0,-1,:], mode='lines', name='Effluent Concentration'))
    fig.update_layout(title='IX Breakthrough Curve', xaxis_title='Hours', yaxis_title='Concentration')
    st.plotly_chart(fig)
