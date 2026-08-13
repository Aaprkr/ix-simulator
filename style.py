CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

.stApp {
    background: linear-gradient(180deg, #0A1F2E 0%, #061520 50%, #030B12 100%);
    background-attachment: fixed;
}
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.block-container { padding-top: 2rem; max-width: 1400px; }

h1 { font-weight: 300 !important; letter-spacing: -0.02em; color: #E8F4F8 !important; }
h2 { font-weight: 400 !important; color: #E8F4F8 !important; font-size: 1.3rem !important; }
h3 { font-weight: 500 !important; color: #9DB8C8 !important; font-size: 0.8rem !important;
     text-transform: uppercase; letter-spacing: 0.1em; }
p, li, label { color: #9DB8C8; }

section[data-testid="stSidebar"] {
    background: rgba(255,255,255,0.03);
    border-right: 1px solid rgba(255,255,255,0.08);
}
section[data-testid="stSidebar"] * { color: #C5DCE8; }

div[data-testid="stMetric"] {
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: 14px;
    padding: 1rem;
}
div[data-testid="stMetricValue"] {
    font-family: 'JetBrains Mono', monospace !important;
    color: #40E0D0 !important;
    font-weight: 400 !important;
}
div[data-testid="stMetricLabel"] p {
    color: #7A94A6 !important; font-size: 0.7rem !important;
    text-transform: uppercase; letter-spacing: 0.1em;
}

.stButton > button {
    background: rgba(255,255,255,0.07);
    border: 1px solid rgba(255,255,255,0.15);
    border-radius: 10px;
    color: #E8F4F8;
    font-weight: 400;
}
.stButton > button:hover {
    border-color: rgba(64,224,208,0.5);
    background: rgba(64,224,208,0.10);
    color: #40E0D0;
}
.stButton > button[kind="primary"] {
    background: rgba(64,224,208,0.18);
    border: 1px solid rgba(64,224,208,0.45);
    color: #A8F5EC;
}

.stNumberInput input, .stTextInput input {
    background: rgba(255,255,255,0.05) !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    color: #E8F4F8 !important;
    font-family: 'JetBrains Mono', monospace !important;
    border-radius: 8px !important;
}
div[data-baseweb="select"] > div {
    background: rgba(255,255,255,0.05) !important;
    border-color: rgba(255,255,255,0.12) !important;
}

div[data-testid="stDataFrame"], div[data-testid="stDataEditor"] {
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: 12px;
}
div[data-testid="stExpander"] {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.10) !important;
    border-radius: 12px !important;
}
div[data-testid="stAlert"] { border-radius: 10px; }
#MainMenu, footer { visibility: hidden; }
header[data-testid="stHeader"] { background: transparent !important; height: 0 !important; }
div[data-testid="stToolbar"] { display: none !important; }
div[data-testid="stDecoration"] { display: none !important; }
</style>
"""

PLOT = dict(
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(255,255,255,0.02)',
    font=dict(family='JetBrains Mono, monospace', color='#9DB8C8', size=11),
    xaxis=dict(gridcolor='rgba(255,255,255,0.06)', linecolor='rgba(255,255,255,0.15)'),
    yaxis=dict(gridcolor='rgba(255,255,255,0.06)', linecolor='rgba(255,255,255,0.15)'),
    legend=dict(bgcolor='rgba(6,21,32,0.7)', bordercolor='rgba(255,255,255,0.1)', borderwidth=1),
    margin=dict(l=60, r=30, t=50, b=50),
    hovermode='x unified',
)
SERIES = ['#FFB454','#FFD98A','#7BE8B4','#40E0D0','#39B8E5','#5B8DEF','#8B6FE8','#C77DFF','#FF6B9D']
