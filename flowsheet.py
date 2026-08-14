"""Flowsheet canvas: drag-and-drop treatment train builder."""
import streamlit as st
import numpy as np, pandas as pd, io
import plotly.graph_objects as go
from streamlit_flow import streamlit_flow
from streamlit_flow.elements import StreamlitFlowNode, StreamlitFlowEdge
from streamlit_flow.state import StreamlitFlowState
from streamlit_flow.layouts import ManualLayout
from core import PFAS_DB, BG_IONS, MCL, CARY, RESINS, simulate, analyze, mass_captured
from style import PLOT, SERIES

NODE_STYLE = {
    "source": {"background": "rgba(255,180,84,.18)", "border": "1px solid rgba(255,180,84,.55)",
               "color": "#FFD98A", "borderRadius": "12px", "width": 165, "fontSize": "13px"},
    "ix":     {"background": "rgba(64,224,208,.16)", "border": "1px solid rgba(64,224,208,.5)",
               "color": "#A8F5EC", "borderRadius": "12px", "width": 165, "fontSize": "13px"},
    "gac":    {"background": "rgba(139,111,232,.15)", "border": "1px dashed rgba(139,111,232,.55)",
               "color": "#C9B8FF", "borderRadius": "12px", "width": 165, "fontSize": "13px"},
    "out":    {"background": "rgba(255,255,255,.07)", "border": "1px solid rgba(255,255,255,.28)",
               "color": "#E8F4F8", "borderRadius": "12px", "width": 165, "fontSize": "13px"},
}

def _default_cfg(kind):
    if kind == "source":
        c = {"label": "Raw water", "flow_gpm": 50.0}
        for n, d in BG_IONS.items(): c[n] = d["default"]
        for k in PFAS_DB: c[k] = CARY.get(k, 0.0)
        return c
    if kind == "ix":
        return {"label": "IX vessel", "resin": "Custom / manual entry", "Q": 1000.0,
                "L": 14.76, "diam": 60.0, "v": 0.123, "EBED": 0.35, "rb": 0.03375,
                "kL": 0.0021, "cost": 25.0, "leadlag": False}
    if kind == "gac":
        return {"label": "GAC contactor"}
    return {"label": "Treated water", "thresh": 10}


def _mk_node(nid, kind, pos):
    ntype = "input" if kind == "source" else ("output" if kind == "out" else "default")
    return StreamlitFlowNode(nid, pos, {"content": f"**{_default_cfg(kind)['label']}**"},
                             node_type=ntype, source_position="right",
                             target_position="left", style=NODE_STYLE[kind], draggable=True)


def render():
    st.title("Flowsheet")
    st.write("Build a treatment train by dropping units on the canvas and connecting them. "
             "Right click the canvas to add a unit. Drag from a node's right edge to another "
             "node's left edge to connect. Run several trains from one source to compare "
             "configurations against identical water.")

    # ---------- state ----------
    if "fs_state" not in st.session_state:
        st.session_state.fs_state = StreamlitFlowState(
            [_mk_node("source_1", "source", (60, 130)),
             _mk_node("ix_1", "ix", (330, 130)),
             _mk_node("out_1", "out", (600, 130))],
            [StreamlitFlowEdge("source_1-ix_1", "source_1", "ix_1", animated=True),
             StreamlitFlowEdge("ix_1-out_1", "ix_1", "out_1", animated=True)])
    if "fs_cfg" not in st.session_state:
        st.session_state.fs_cfg = {"source_1": _default_cfg("source"),
                                   "ix_1": _default_cfg("ix"),
                                   "out_1": _default_cfg("out")}

    # ---------- add units ----------
    a1, a2, a3, a4 = st.columns(4)
    def _add(kind, label):
        n = len([k for k in st.session_state.fs_cfg if k.startswith(kind)]) + 1
        nid = f"{kind}_{n}"
        while nid in st.session_state.fs_cfg:
            n += 1; nid = f"{kind}_{n}"
        y = 130 + 150 * (len(st.session_state.fs_state.nodes) % 4)
        x = {"source": 60, "ix": 330, "gac": 330, "out": 600}[kind]
        st.session_state.fs_state.nodes.append(_mk_node(nid, kind, (x, y)))
        st.session_state.fs_cfg[nid] = _default_cfg(kind)
        st.rerun()
    with a1:
        if st.button("Add source", use_container_width=True): _add("source", "Raw water")
    with a2:
        if st.button("Add IX vessel", use_container_width=True): _add("ix", "IX vessel")
    with a3:
        if st.button("Add GAC", use_container_width=True): _add("gac", "GAC contactor")
    with a4:
        if st.button("Add output", use_container_width=True): _add("out", "Treated water")

    # ---------- canvas ----------
    # Isolated in a fragment. Without this the component fires a rerun on every
    # interaction that restarts the whole script and kills any in-flight solve.
    @st.fragment
    def _canvas():
        st.session_state.fs_state = streamlit_flow(
            "flowsheet_canvas", st.session_state.fs_state,
            layout=ManualLayout(), fit_view=True, height=430,
            enable_node_menu=True, enable_edge_menu=True, enable_pane_menu=True,
            get_node_on_click=True, allow_new_edges=True, animate_new_edges=True,
            min_zoom=0.4, hide_watermark=True)
        _s = st.session_state.fs_state.selected_id
        if _s:
            st.session_state.fs_sel = _s
    _canvas()

    # prune configs for deleted nodes
    live = {n.id for n in st.session_state.fs_state.nodes}
    for k in [k for k in st.session_state.fs_cfg if k not in live]:
        del st.session_state.fs_cfg[k]

    sel_id = st.session_state.get("fs_sel")
    if sel_id not in st.session_state.fs_cfg:
        sel_id = None
    st.divider()

    # ---------- inspector ----------
    if sel_id and sel_id in st.session_state.fs_cfg:
        cfg = st.session_state.fs_cfg[sel_id]
        kind = sel_id.split("_")[0]
        st.markdown(f"### {cfg['label']}")

        if kind == "source":
            cfg["label"] = st.text_input("Name", cfg["label"], key=f"nm_{sel_id}")
            cfg["flow_gpm"] = st.number_input("Flow rate, gpm", value=float(cfg["flow_gpm"]),
                                              key=f"fl_{sel_id}")
            st.markdown("###### PFAS present, ng/L (ppt)")
            st.caption("Set a species to zero to exclude it from this water.")
            g = st.columns(3)
            for i, k in enumerate(PFAS_DB):
                with g[i % 3]:
                    cfg[k] = st.number_input(f"{k}  C{PFAS_DB[k]['c']}", value=float(cfg.get(k, 0.0)),
                                             min_value=0.0, key=f"p_{sel_id}_{k}")
            st.markdown("###### Background anions, meq/L")
            b = st.columns(4)
            for i, k in enumerate(BG_IONS):
                with b[i % 4]:
                    cfg[k] = st.number_input(k.title(), value=float(cfg.get(k, 0.0)),
                                             key=f"b_{sel_id}_{k}")
            if st.button("Load Cary, NC sample", key=f"cary_{sel_id}"):
                for k in PFAS_DB: cfg[k] = CARY.get(k, 0.0)
                st.rerun()

        elif kind == "ix":
            cfg["label"] = st.text_input("Name", cfg["label"], key=f"nm_{sel_id}")
            pick = st.selectbox("Commercial resin", list(RESINS.keys()),
                                index=list(RESINS.keys()).index(cfg.get("resin", "Custom / manual entry")),
                                key=f"rs_{sel_id}")
            cfg["resin"] = pick
            spec = RESINS[pick]
            if spec:
                st.caption(f"{spec['matrix']} matrix, {spec['func']}, "
                           f"{spec['dia_um']} um bead, capacity {spec['cap_note']}.")
                if st.button("Load these specifications", key=f"ld_{sel_id}"):
                    cfg["Q"] = spec["Q"]; cfg["rb"] = spec["rb"]; cfg["EBED"] = spec["EBED"]
                    st.rerun()
            c1, c2, c3 = st.columns(3)
            with c1:
                cfg["Q"] = st.number_input("Capacity Q, meq/L", value=float(cfg["Q"]), key=f"q_{sel_id}")
                cfg["EBED"] = st.number_input("Bed porosity", value=float(cfg["EBED"]),
                                              min_value=0.01, max_value=0.99, key=f"e_{sel_id}")
            with c2:
                cfg["L"] = st.number_input("Bed depth, cm", value=float(cfg["L"]), key=f"l_{sel_id}")
                cfg["diam"] = st.number_input("Diameter, cm", value=float(cfg["diam"]), key=f"d_{sel_id}")
            with c3:
                cfg["v"] = st.number_input("Velocity, cm/s", value=float(cfg["v"]),
                                           format="%.4f", key=f"v_{sel_id}")
                cfg["cost"] = st.number_input("Resin cost, $/L", value=float(cfg["cost"]), key=f"c_{sel_id}")
            cfg["leadlag"] = st.checkbox(
                "Lead-lag configuration (two vessels in series)", value=cfg.get("leadlag", False),
                key=f"ll_{sel_id}",
                help="Standard practice. The lag vessel polishes the lead's effluent so the "
                     "lead can run to exhaustion before changeout.")
            bedL = np.pi * (cfg["diam"] / 2) ** 2 * cfg["L"] / 1000
            st.caption(f"Bed volume {bedL:,.0f} L"
                       + (" per vessel, two vessels" if cfg["leadlag"] else ""))

        elif kind == "gac":
            cfg["label"] = st.text_input("Name", cfg["label"], key=f"nm_{sel_id}")
            st.warning("**Not yet parameterised for PFAS.** A GAC contactor is simulated by the "
                       "EPA Pore Surface Diffusion Model, which requires Freundlich isotherm "
                       "constants K and 1/n for each compound on the specific carbon product. "
                       "EPA's published PSDM examples cover trichloroethylene, "
                       "tetrachloroethylene and toluene, not PFAS. Rather than invent those "
                       "constants, this unit is inert: it passes water through unchanged and is "
                       "excluded from results. Supply measured isotherm data and it can be "
                       "activated.")

        else:
            cfg["label"] = st.text_input("Name", cfg["label"], key=f"nm_{sel_id}")
            cfg["thresh"] = st.slider("Breakthrough threshold, % of influent", 1, 50,
                                      int(cfg.get("thresh", 10)), key=f"t_{sel_id}")
    else:
        st.info("Click a unit on the canvas to configure it.")

    # ---------- trace and run ----------
    st.divider()
    edges = [(e.source, e.target) for e in st.session_state.fs_state.edges]
    trains = []
    for sid in [n for n in st.session_state.fs_cfg if n.startswith("source")]:
        stack = [(sid, [sid])]
        while stack:
            cur, path = stack.pop()
            nxt = [t for s, t in edges if s == cur]
            if not nxt and cur.startswith("out"):
                trains.append(path)
            for t in nxt:
                if t not in path:
                    stack.append((t, path + [t]))
    valid = [p for p in trains if p[-1].startswith("out")
             and any(x.startswith("ix") for x in p)]

    if not valid:
        st.warning("No complete train yet. Connect a source through at least one IX vessel to "
                   "an output.")
        return

    st.markdown(f"### {len(valid)} train{'s' if len(valid) > 1 else ''} ready")
    for p in valid:
        st.caption("  →  ".join(st.session_state.fs_cfg[n]["label"] for n in p))

    if st.button("Run flowsheet", type="primary"):
        st.session_state.fs_results = _solve(valid)

    results = st.session_state.get("fs_results") or []
    if not results:
        return
    _render_results(results)


@st.cache_data(show_spinner=False, max_entries=24)
def _solve_one(payload_json):
    """Cached single-train solve. Caching is what makes this survive the reruns
    the canvas component fires, which would otherwise interrupt a long solve."""
    import json as _json
    d = _json.loads(payload_json)
    src, ix, thr, db, mcl = d["src"], d["ix"], d["thr"], d["db"], d["mcl"]
    species = [k for k in PFAS_DB if src.get(k, 0) > 0]
    if not species:
        return None
    row = {"time": [0, 3000]}
    for k, dd in BG_IONS.items(): row[k] = [src.get(k, dd["default"])] * 2
    for k in species: row[k] = [src[k]] * 2
    cin = pd.DataFrame(row)
    depth = ix["L"] * (2 if ix.get("leadlag") else 1)
    td, BV, curves = simulate(species, cin, Q=ix["Q"], EBED=ix["EBED"], L=depth,
                              v=ix["v"], rb=ix["rb"], kL=ix["kL"], db=db)
    recs, first, fsp = analyze(curves, td, BV, cin, thr, db=db, mcl=mcl)
    mass = mass_captured(curves, td, cin, src["flow_gpm"], db=db)
    return {"depth": depth, "td": td, "BV": BV, "curves": curves, "recs": recs,
            "first": first, "fsp": fsp, "mass": mass, "thr": thr}


def _solve(valid):
    import json as _json
    results = []
    prog = st.progress(0.0, text="Solving")
    for i, path in enumerate(valid):
        src = st.session_state.fs_cfg[path[0]]
        ix = st.session_state.fs_cfg[next(x for x in path if x.startswith("ix"))]
        out = st.session_state.fs_cfg[path[-1]]
        prog.progress(i / len(valid), text=f"Solving {src['label']} to {out['label']}")
        payload = _json.dumps({"src": src, "ix": ix, "thr": out.get("thresh", 10) / 100,
                               "db": st.session_state.db, "mcl": st.session_state.mcl},
                              sort_keys=True, default=str)
        try:
            r = _solve_one(payload)
            if r is None:
                st.error(f"{src['label']} has no PFAS above zero."); continue
            r.update({"path": path, "src": src, "ix": ix})
            results.append(r)
        except Exception as e:
            st.error(f"Train failed: {e}")
    prog.empty()
    return results


def _render_results(results):
    # ---------- comparison ----------
    if len(results) > 1:
        st.markdown("### Train comparison")
        comp = []
        for r in results:
            bedL = np.pi * (r["ix"]["diam"] / 2) ** 2 * r["depth"] / 1000
            charge = bedL * r["ix"]["cost"]
            comp.append({
                "Train": " to ".join(st.session_state.fs_cfg[n]["label"] for n in r["path"]),
                "Resin": r["ix"]["resin"].split(" (")[0],
                "Config": "lead-lag" if r["ix"].get("leadlag") else "single",
                "Limiting": r["fsp"] or "none",
                "Bed life, d": f"{r['first']:,.0f}" if r["first"] else "not reached",
                "Resin charge": f"${charge:,.0f}",
                "Annual media": f"${charge*(365/r['first']):,.0f}" if r["first"] else "-",
            })
        st.dataframe(pd.DataFrame(comp), use_container_width=True, hide_index=True)

    # ---------- per train ----------
    for r in results:
        st.divider()
        st.markdown("### " + " to ".join(
            st.session_state.fs_cfg[n]["label"] for n in r["path"]))
        bedL = np.pi * (r["ix"]["diam"] / 2) ** 2 * r["depth"] / 1000
        ebct = bedL / (r["src"]["flow_gpm"] * 3.785)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Limiting species", r["fsp"] or "none")
        m2.metric("Bed life", f"{r['first']:,.0f} d" if r["first"] else ">3000 d")
        m3.metric("EBCT", f"{ebct:.2f} min")
        m4.metric("Mass captured", f"{sum(r['mass'].values()):.2f} g")

        fig = go.Figure()
        for i, n in enumerate(sorted(r["curves"], key=lambda k: PFAS_DB[k]["KxA"])):
            fig.add_trace(go.Scatter(x=r["BV"] / 1000, y=r["curves"][n], mode="lines",
                                     name=f"{n} C{PFAS_DB[n]['c']}",
                                     line=dict(width=2.1, color=SERIES[i % len(SERIES)])))
        fig.add_hline(y=1.0, line_dash="dot", line_color="rgba(255,255,255,.3)")
        fig.add_hline(y=r["thr"], line_dash="dash", line_color="#FF6B6B")
        fig.update_layout(xaxis_title="throughput, 1000 bed volumes",
                          yaxis_title="C / C0", height=400, **PLOT)
        st.plotly_chart(fig, use_container_width=True)

        with st.expander("Species detail and mass balance"):
            df = pd.DataFrame(r["recs"])
            df["Mass captured, g"] = [f"{r['mass'].get(x, 0):.3f}" for x in df["Species"]]
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.caption("Mass captured is the integral of influent minus effluent over the run. "
                       "It sets the contaminant load that leaves the site on the spent resin, "
                       "which governs disposal handling and cost.")
