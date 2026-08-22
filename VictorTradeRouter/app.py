from __future__ import annotations

import base64
import io
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from PIL import Image

from diplomacy import NATIONS, diplomacy_warnings, load_ownership, load_settings, region_controls, save_ownership, save_settings
from economy import calculate_trade, load_economy, save_economy, validate_economy
from interface_v4 import run_interface
from recommendations import generate_trade_recommendations
from routing import RouteDiagnosticError, generate_world_route_candidates, load_regions, ports as geometry_ports, regional_to_world, render_unified_route, world_alignment, world_navigation_samples
from wind import WIND_DISCLAIMER, choose_wind_route, hud_arrow_to_world_wind, load_handoff, wind_toward_at_elapsed


ROOT = Path(__file__).parent
st.set_page_config(
    page_title="Victor's Trade Router",
    page_icon="⚓",
    layout="wide",
)


def apply_windward_theme() -> None:
    hero_file = ROOT / "assets" / "winward_project_header.png"
    hero = base64.b64encode(hero_file.read_bytes()).decode("ascii")
    st.markdown(f"""
<style>
@font-face {{ font-family: WindwardFallback; src: local('Georgia'); }}
:root {{ --navy:#081a29; --navy2:#102d42; --sea:#385f78; --gold:#c9a84d; --pale:#e8edf0; }}
.stApp {{
  --windward-background:var(--st-background-color,var(--background-color,#e7edef));
  --windward-surface:var(--st-secondary-background-color,var(--secondary-background-color,#f7f9f9));
  --windward-text:var(--st-text-color,var(--text-color,#132332));
  --windward-border:var(--st-border-color,var(--border-color,#8fa3ad));
  background-color:var(--windward-background) !important;
  background-image:
    linear-gradient(rgba(56,95,120,.08), rgba(8,26,41,.04)),
    radial-gradient(circle at 50% 0%, rgba(143,177,196,.16) 0%, transparent 58%);
  color:var(--windward-text);
}}
html, body, [class*="css"], [data-testid="stAppViewContainer"] {{ font-family:"Trebuchet MS","Segoe UI",sans-serif; }}
.stApp [data-testid="stAppViewContainer"], .stApp [data-testid="stMain"] {{
  background-color:transparent;
  color:var(--windward-text);
}}
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6,
.stApp [data-testid="stMarkdownContainer"] p,
.stApp [data-testid="stMarkdownContainer"] li,
.stApp [data-testid="stCaptionContainer"] p,
.stApp [data-testid="stWidgetLabel"] p,
.stApp [data-testid="stMetricLabel"],
.stApp [data-testid="stMetricValue"],
.stApp [data-testid="stExpander"] summary,
.stApp [data-testid="stExpander"] summary p,
.stApp button[data-baseweb="tab"] p {{
  color:var(--windward-text) !important;
}}
h1, h2, h3, h4, .windward-title, button, [data-testid="stExpander"] summary {{
  font-family:WindwardFallback, Georgia, "Times New Roman", serif !important;
  letter-spacing:.035em;
}}
.block-container {{ max-width:1260px; padding-top:1.4rem; padding-bottom:2.5rem; }}
.windward-hero {{
  width:100%; max-width:none; height:clamp(205px,20vw,250px); min-height:0;
  border:3px solid #172b39; border-radius:3px;
  background-image:linear-gradient(90deg,rgba(5,24,38,.18),rgba(5,24,38,.05)),url("data:image/png;base64,{hero}");
  background-size:cover;
  background-repeat:no-repeat;
  background-position:center 54%;
  background-color:#17344d;
  box-shadow:0 8px 22px rgba(5,22,34,.28), inset 0 0 0 1px rgba(230,238,240,.35);
  display:flex; flex-direction:column; justify-content:flex-end; padding:18px 24px; margin:0 auto 16px auto;
}}
.windward-title {{ color:#f4f6f4; font-size:2.05rem; font-weight:800; text-shadow:0 3px 2px #132431,0 0 8px #09151c; }}
div.stButton > button {{
  color:#f2f3ef; background:linear-gradient(#173d56,#0b2436); border:1px solid #c9a84d;
  border-radius:2px; box-shadow:inset 0 0 0 1px rgba(255,255,255,.08); font-weight:700;
}}
div.stButton > button p, div.stButton > button span {{ color:#f2f3ef !important; }}
div.stButton > button:hover {{ color:#fff4c9; border-color:#f0cf70; background:linear-gradient(#20516f,#103149); }}
div.stButton > button:hover p, div.stButton > button:hover span {{ color:#fff4c9 !important; }}
div[data-testid="stMetric"] {{ color:var(--windward-text); background:var(--windward-surface); border:1px solid var(--windward-border); border-top:3px solid #c0a04c; padding:10px 14px; }}
div[data-testid="stMetric"] [data-testid="stMetricLabel"], div[data-testid="stMetric"] [data-testid="stMetricValue"] {{ color:var(--windward-text) !important; }}
div[data-testid="stExpander"] {{ color:var(--windward-text); background:var(--windward-surface); border:1px solid var(--windward-border); border-radius:2px; }}
[data-testid="stPlotlyChart"] {{ border:1px solid var(--windward-border); background:var(--windward-surface); }}
.windward-note {{ color:var(--windward-text); opacity:.82; font-size:.87rem; }}
.windward-rank {{ color:#c5a34a; font-family:Georgia,serif; font-weight:700; }}
.windward-nav-spacer {{ height:18px; }}
.windward-warning {{
  margin-top:1rem; padding:12px 15px; color:#fff1c9; background:#713431;
  border:1px solid #d9a84f; border-left:6px solid #f0c65b;
  box-shadow:0 3px 10px rgba(43,19,17,.18); font-weight:700;
}}
header[data-testid="stHeader"] {{ background:transparent; }}
</style>
<div class="windward-hero">
  <div class="windward-title">VICTOR'S TRADE ROUTER</div>
</div>
""", unsafe_allow_html=True)


def clean_region_name(name: str) -> str:
    return "Îles de Louis" if "les de Louis" in name else name


def editable_records(value) -> list[dict]:
    if isinstance(value, pd.DataFrame):
        return json.loads(value.to_json(orient="records"))
    return list(value)


def zoomable_route(png: bytes, key: str) -> None:
    image = Image.open(io.BytesIO(png)).convert("RGB")
    figure = px.imshow(image)
    figure.update_layout(margin=dict(l=0, r=0, t=0, b=0), dragmode="pan", height=max(520, min(920, int(image.height * 0.78))))
    figure.update_xaxes(visible=False, constrain="domain")
    figure.update_yaxes(visible=False, scaleanchor="x")
    st.plotly_chart(figure, width="stretch", key=key, config={"scrollZoom": True, "displaylogo": False, "modeBarButtonsToRemove": ["select2d", "lasso2d"]})


def persist_section(section: str, rows: list[dict], key_fields: tuple[str, ...]) -> None:
    current = st.session_state.economy_data[section]
    updates = {tuple(row[field] for field in key_fields): row for row in rows}
    st.session_state.economy_data[section] = [updates.get(tuple(row[field] for field in key_fields), row) for row in current]
    save_economy(st.session_state.economy_data)


def world_map_figure(
    economy: dict,
    *,
    current_position_mode: bool = False,
    selected_origin: str | None = None,
    selected_destination: str | None = None,
) -> go.Figure:
    settings = world_alignment()
    image = Image.open(ROOT / settings["world_map"]).convert("RGB")
    figure = px.imshow(image)
    if current_position_mode:
        samples = world_navigation_samples(24)
        figure.add_trace(go.Scattergl(
            x=[row[0] for row in samples], y=[row[1] for row in samples], mode="markers",
            marker=dict(size=8, opacity=0.015, color="#00f0ff"),
            customdata=[[row[2], row[3], row[4]] for row in samples],
            hovertemplate="Navigable water in %{customdata[0]}<extra></extra>", name="Navigable water",
        ))
    else:
        geometry_by_id = {(region["region_id"], port["port_id"]): port for region in load_regions() for port in geometry_ports(region["region_id"])}
        rows = []
        for port in economy["ports"]:
            geometry = geometry_by_id.get((port["region_id"], port.get("geometry_port_id")))
            if not geometry:
                continue
            wx, wy = regional_to_world(port["region_id"], (int(geometry["pixel_x"]), int(geometry["pixel_y"])))
            rows.append((wx, wy, port["display_name"], port["region"]))
        ordinary = [row for row in rows if row[2] not in {selected_origin, selected_destination}]
        figure.add_trace(go.Scattergl(
            x=[row[0] for row in ordinary], y=[row[1] for row in ordinary], mode="markers",
            marker=dict(size=13, color="#ffe657", line=dict(width=2, color="#081923")),
            customdata=[[row[2], row[3]] for row in ordinary],
            hovertemplate="%{customdata[0]} · %{customdata[1]}<extra></extra>", name="Trade ports",
        ))
        for name, color, symbol, label_text in (
            (selected_origin, "#3ee585", "circle", "ORIGIN"),
            (selected_destination, "#ff6262", "diamond", "DESTINATION"),
        ):
            selected = next((row for row in rows if row[2] == name), None)
            if selected:
                figure.add_trace(go.Scattergl(
                    x=[selected[0]], y=[selected[1]], mode="markers+text",
                    marker=dict(size=19, color=color, symbol=symbol, line=dict(width=3, color="#081923")),
                    text=[label_text], textposition="top center", textfont=dict(size=12, color="white"),
                    customdata=[[selected[2], selected[3]]],
                    hovertemplate="%{customdata[0]} · %{customdata[1]}<extra></extra>", name=label_text,
                ))
    figure.update_layout(margin=dict(l=0, r=0, t=0, b=0), dragmode="pan", clickmode="event+select", showlegend=False, height=690)
    figure.update_xaxes(visible=False, constrain="domain")
    figure.update_yaxes(visible=False, scaleanchor="x")
    return figure


def selected_customdata(event) -> list | None:
    if event is None:
        return None
    selection = getattr(event, "selection", None)
    if selection is None and isinstance(event, dict):
        selection = event.get("selection")
    points = getattr(selection, "points", None)
    if points is None and isinstance(selection, dict):
        points = selection.get("points")
    if not points:
        return None
    point = points[-1]
    return point.get("customdata") if isinstance(point, dict) else getattr(point, "customdata", None)


def map_port_picker(economy: dict) -> tuple[str, str]:
    if "map_pick_stage" not in st.session_state:
        st.session_state.map_pick_stage = "origin"
    stage = st.session_state.map_pick_stage
    if stage == "origin":
        st.markdown(
            "<div style='padding:14px 18px;border:2px solid #3ee585;border-radius:10px;background:#12392b;"
            "font-size:18px;color:#f2fff7'><b>STEP 1 OF 2 — SELECT ORIGIN</b><br><span style='font-size:14px;color:#d8f7e4'>Click the port where the cargo is purchased.</span></div>",
            unsafe_allow_html=True,
        )
    elif stage == "destination":
        st.markdown(
            "<div style='padding:14px 18px;border:2px solid #ff6262;border-radius:10px;background:#3d2025;"
            "font-size:18px;color:#fff3f3'><b>STEP 2 OF 2 — SELECT DESTINATION</b><br><span style='font-size:14px;color:#ffd8d8'>Now click the port where the cargo will be sold.</span></div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div style='padding:14px 18px;border:2px solid #75b9ff;border-radius:10px;background:#172f46;"
            "font-size:18px;color:#f2f8ff'><b>SELECTION READY</b><br><span style='font-size:14px;color:#d8eaff'>Generate the route below, or choose which endpoint you want to change.</span></div>",
            unsafe_allow_html=True,
        )
    selected_columns = st.columns(2)
    selected_columns[0].success(f"Origin: {st.session_state.selected_origin}")
    selected_columns[1].error(f"Destination: {st.session_state.selected_destination}")
    controls = st.columns(3)
    if controls[0].button("Change Origin", key="map_origin_next", width="stretch"):
        st.session_state.map_pick_stage = "origin"
        st.rerun()
    if controls[1].button("Change Destination", key="map_destination_next", width="stretch"):
        st.session_state.map_pick_stage = "destination"
        st.rerun()
    if controls[2].button("Reset Selection", key="map_clear", width="stretch"):
        st.session_state.selected_origin = "Petit Anvers"
        st.session_state.selected_destination = "Port Royal"
        st.session_state.map_pick_stage = "origin"
        st.session_state.map_nonce += 1
        st.rerun()
    event = st.plotly_chart(
        world_map_figure(
            economy,
            selected_origin=st.session_state.selected_origin,
            selected_destination=st.session_state.selected_destination,
        ),
        width="stretch",
        key=f"port_pick_map_{st.session_state.map_nonce}",
        on_select="rerun",
        selection_mode="points",
        config={"scrollZoom": True, "displaylogo": False},
    )
    custom = selected_customdata(event)
    if custom:
        name = str(custom[0])
        if st.session_state.map_pick_stage == "origin":
            st.session_state.selected_origin = name
            st.session_state.map_pick_stage = "destination"
        elif name != st.session_state.selected_origin:
            st.session_state.selected_destination = name
            st.session_state.map_pick_stage = "complete"
        st.session_state.map_nonce += 1
        st.rerun()
    return st.session_state.selected_origin, st.session_state.selected_destination


def dropdown_port_picker(economy: dict) -> tuple[str, str]:
    region_names = sorted({row["region"] for row in economy["ports"]})
    port_by_name = {row["display_name"]: row for row in economy["ports"]}
    start_current = port_by_name[st.session_state.selected_origin]
    destination_current = port_by_name[st.session_state.selected_destination]
    left, right = st.columns(2)
    with left:
        start_region = st.selectbox("Starting Region", region_names, index=region_names.index(start_current["region"]), key="v2_start_region")
        start_options = [row["display_name"] for row in economy["ports"] if row["region"] == start_region]
        start_index = start_options.index(start_current["display_name"]) if start_current["display_name"] in start_options else 0
        origin = st.selectbox("Trade Origin Port", start_options, index=start_index, key="v2_start_port")
    with right:
        destination_region = st.selectbox("Destination Region", region_names, index=region_names.index(destination_current["region"]), key="v2_destination_region")
        destination_options = [row["display_name"] for row in economy["ports"] if row["region"] == destination_region]
        destination_index = destination_options.index(destination_current["display_name"]) if destination_current["display_name"] in destination_options else 0
        destination = st.selectbox("Destination Port", destination_options, index=destination_index, key="v2_destination_port")
    st.session_state.selected_origin = origin
    st.session_state.selected_destination = destination
    return origin, destination


def current_position_picker() -> dict | None:
    st.caption("Click the ship's actual location on navigable water. The closest sampled water point is used; cargo still comes from the selected trade origin.")
    event = st.plotly_chart(world_map_figure(st.session_state.economy_data, current_position_mode=True), width="stretch", key=f"current_position_map_{st.session_state.position_nonce}", on_select="rerun", selection_mode="points", config={"scrollZoom": True, "displaylogo": False})
    custom = selected_customdata(event)
    if custom:
        st.session_state.current_position = {"region_id": str(custom[0]), "point": (int(custom[1]), int(custom[2]))}
        st.session_state.position_nonce += 1
        st.rerun()
    position = st.session_state.get("current_position")
    if position:
        region = next(row["region_name"] for row in load_regions() if row["region_id"] == position["region_id"])
        st.caption(f"Selected current position: {clean_region_name(region)} water at regional point {position['point'][0]}, {position['point'][1]}")
    return position


def wind_compass(ship_bearing: float, hud_arrow: float, height: int = 355) -> go.Figure:
    labels = [
        ("N", (0 - ship_bearing) % 360),
        ("NE", (45 - ship_bearing) % 360),
        ("E", (90 - ship_bearing) % 360),
        ("SE", (135 - ship_bearing) % 360),
        ("S", (180 - ship_bearing) % 360),
        ("SW", (225 - ship_bearing) % 360),
        ("W", (270 - ship_bearing) % 360),
        ("NW", (315 - ship_bearing) % 360),
    ]
    figure = go.Figure()
    octagon_theta = [22.5 + 45 * index for index in range(8)] + [22.5]
    figure.add_trace(go.Scatterpolar(theta=octagon_theta, r=[1.12] * 9, mode="lines", line=dict(color="#8d9294", width=4), fill="toself", fillcolor="#2a2424", hoverinfo="skip"))
    ring = list(range(0, 361, 5))
    figure.add_trace(go.Scatterpolar(theta=ring, r=[0.70] * len(ring), mode="lines", line=dict(color="#8c8987", width=2), hoverinfo="skip"))
    figure.add_trace(go.Scatterpolar(
        theta=[row[1] for row in labels], r=[0.94] * 8, mode="text", text=[row[0] for row in labels],
        textfont=dict(size=22, color="#f3f3ef", family="Georgia, serif"), hoverinfo="skip",
    ))
    figure.add_trace(go.Scatterpolar(
        theta=[(hud_arrow + 180) % 360, hud_arrow], r=[0.42, 0.68], mode="lines+markers",
        line=dict(color="rgba(175,174,174,0.72)", width=12),
        marker=dict(size=[3, 19], color=["rgba(175,174,174,0.30)", "#b7b5b4"], symbol=["circle", "triangle-up"]),
        hoverinfo="skip",
    ))
    figure.update_layout(
        polar=dict(
            radialaxis=dict(visible=False, range=[0, 1.18]),
            angularaxis=dict(visible=False, rotation=90, direction="clockwise"),
            bgcolor="#2a2424",
        ),
        showlegend=False,
        margin=dict(l=10, r=10, t=10, b=10),
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return figure


def recommendation_figure(rows: list[dict]) -> go.Figure:
    rows = list(reversed(rows))
    figure = go.Figure(go.Bar(
        x=[row["trade_score"] for row in rows],
        y=[row["destination"] for row in rows],
        orientation="h",
        marker=dict(
            color=[row["wind_color"] for row in rows],
            line=dict(color="#d8c27a", width=1.2),
        ),
        text=[
            f"£{row['total_profit_gbp']:,}  ·  {row['time_estimate']}  ·  {row['wind_rating']}"
            for row in rows
        ],
        textposition="inside",
        insidetextanchor="start",
        textfont=dict(color="#f7f3e8", size=13, family="Georgia, serif"),
        customdata=[[
            row["destination"], row["destination_region"], row["cargo"], row["total_profit_gbp"],
            row["profit_per_unit_gbp"], row["time_estimate"], row["wind_rating"],
            row["modeled_departure_speed_knots"], row["relative_wind_deviation_deg"],
            row["distance_source"], row["cargo_distance_m"], row["general_bearing_deg"],
        ] for row in rows],
        hovertemplate=(
            "<b>%{customdata[0]}</b> · %{customdata[1]}<br>"
            "Cargo: %{customdata[2]}<br>"
            "Total profit: £%{customdata[3]:,}<br>"
            "Profit per unit: £%{customdata[4]:,}<br>"
            "Estimated voyage: %{customdata[5]}<br>"
            "Departure wind: %{customdata[6]} (%{customdata[7]} kt model)<br>"
            "Wind deviation: %{customdata[8]}°<br>"
            "Distance basis: %{customdata[9]}<br>"
            "General bearing: %{customdata[11]}°<extra>Select Route</extra>"
        ),
    ))
    figure.update_layout(
        height=max(500, 39 * len(rows) + 80),
        margin=dict(l=12, r=12, t=20, b=18),
        paper_bgcolor="#0c2537",
        plot_bgcolor="#0c2537",
        clickmode="event+select",
        showlegend=False,
        font=dict(family="Georgia, serif", color="#e7ecec"),
        xaxis=dict(visible=False, range=[0, 106]),
        yaxis=dict(tickfont=dict(size=13, color="#e7ecec"), automargin=True),
        bargap=0.24,
    )
    return figure


def load_home_recommendation(origin: str, destination: str, ship: str, wind_toward: float) -> None:
    for key in (
        "v2_start_region", "v2_start_port", "v2_destination_region", "v2_destination_port",
        "port_selection_mode", "navigation_start_mode", "wind_entry_mode", "absolute_wind",
        "v2_ship", "v2_tax_mode", "v2_result", "current_position",
    ):
        st.session_state.pop(key, None)
    st.session_state.selected_origin = origin
    st.session_state.selected_destination = destination
    st.session_state.v2_ship = ship
    st.session_state.v2_tax_mode = "Default"
    st.session_state.navigation_start_mode = "Origin Port"
    st.session_state.wind_entry_mode = "Enter world direction"
    st.session_state.absolute_wind = int(round(wind_toward)) % 360
    st.session_state.map_pick_stage = "complete"
    st.session_state.active_page = "ROUTE PLANNER"


def render_home(economy: dict) -> None:
    st.markdown("## TRADE INFO")
    st.markdown("<div class='windward-note'>Choose your departure conditions. Hover over a route for its details; select it to prepare the full route.</div>", unsafe_allow_html=True)
    route_ports = [row["display_name"] for row in economy["ports"] if row.get("route_eligible")]
    settings_col, compass_col = st.columns([1.7, 1.0], vertical_alignment="center")
    with settings_col:
        controls = st.columns([1.45, 1.0])
        origin = controls[0].selectbox("Port of origin", route_ports, key="home_origin")
        ship = controls[1].selectbox("Ship", [row["ship"] for row in economy["ships"]], key="home_ship")
        wind_toward = st.slider("Wind heading at departure", 0, 359, 180, 1, key="home_wind")
    with compass_col:
        st.plotly_chart(
            wind_compass(0.0, float(wind_toward), height=270),
            width="stretch",
            key="home_wind_compass",
            config={"displayModeBar": False},
        )
    rows = generate_trade_recommendations(economy, origin, ship, float(wind_toward), limit=18)
    if not rows:
        st.warning("No profitable coordinate-backed voyages have enough data for this departure port.")
        return
    st.markdown("### RECOMMENDED ROUTES")
    event = st.plotly_chart(
        recommendation_figure(rows),
        width="stretch",
        key="home_recommendation_chart",
        on_select="rerun",
        selection_mode="points",
        config={"displayModeBar": False},
    )
    custom = selected_customdata(event)
    if custom:
        load_home_recommendation(origin, str(custom[0]), ship, float(wind_toward))
        st.rerun()


def render_trade_summary(payload: dict) -> None:
    trade = payload["trade"]
    st.markdown(f"## {payload['origin']} → {payload['destination']}")
    summary = st.columns(4)
    summary[0].metric("Cargo", trade["cargo"])
    summary[1].metric("Units", trade["total_units"])
    summary[2].metric("Profit / unit", "Unavailable" if trade["profit_per_unit_gbp"] is None else f"£{trade['profit_per_unit_gbp']:,}")
    summary[3].metric("Total expected profit", "Unavailable" if trade["total_profit_gbp"] is None else f"£{trade['total_profit_gbp']:,}")


def clear_sail_instruction(row: dict) -> dict:
    timing = "At the orange arrow"
    if row.get("expected_elapsed_minutes") is not None:
        timing = f"About {row['expected_elapsed_minutes']:.0f} min after departure"
    wind = "Not time-calibrated"
    if row.get("expected_wind_toward_deg") is not None:
        wind = f"{row['expected_wind_toward_deg']:.0f}° toward"
    return {
        "When": timing,
        "Region": row["region_id"],
        "Wind then": wind,
        "What to do": row["instruction"],
    }


if "economy_data" not in st.session_state:
    st.session_state.economy_data = load_economy()
if "ownership_data" not in st.session_state:
    st.session_state.ownership_data = load_ownership()
if "v2_settings" not in st.session_state:
    st.session_state.v2_settings = load_settings()
if "selected_origin" not in st.session_state:
    st.session_state.selected_origin = "Petit Anvers"
if "selected_destination" not in st.session_state:
    st.session_state.selected_destination = "Port Royal"
if "map_nonce" not in st.session_state:
    st.session_state.map_nonce = 0
if "position_nonce" not in st.session_state:
    st.session_state.position_nonce = 0

economy = st.session_state.economy_data
ownership = st.session_state.ownership_data
settings = st.session_state.v2_settings
port_by_name = {row["display_name"]: row for row in economy["ports"]}

apply_windward_theme()
run_interface(
    economy,
    ownership,
    settings,
    render_home=render_home,
    map_port_picker=map_port_picker,
    dropdown_port_picker=dropdown_port_picker,
    current_position_picker=current_position_picker,
    wind_compass=wind_compass,
    zoomable_route=zoomable_route,
    render_trade_summary=render_trade_summary,
    clear_sail_instruction=clear_sail_instruction,
)
st.stop()

st.title("⚓ Naval Trade Route Tester v3")
st.caption("One trade-and-route workflow using the locked 17-region geometry, connected harbor-water endpoints, wind-aware candidate comparison, and safe TP transitions")
route_tab, data_tab, status_tab = st.tabs(["Generate Trade Route", "Data & Debug", "Data Status"])

with route_tab:
    selection_mode = st.radio("Select ports using", ["Dropdowns", "Map"], horizontal=True, key="port_selection_mode")
    origin, destination = map_port_picker(economy) if selection_mode == "Map" else dropdown_port_picker(economy)
    st.caption(f"Trade: {origin} → {destination}")
    navigation_mode = st.radio("Navigation Start", ["Origin Port", "Current Position"], horizontal=True, key="navigation_start_mode")
    current_position = current_position_picker() if navigation_mode == "Current Position" else None

    ship_col, tax_col = st.columns(2)
    with ship_col:
        ship = st.selectbox("Ship", [row["ship"] for row in economy["ships"]], key="v2_ship")
    with tax_col:
        tax_mode = st.selectbox("Tax", ["Default", "Manual"], key="v2_tax_mode")
    origin_defaults = port_by_name[origin]
    destination_defaults = port_by_name[destination]
    if tax_mode == "Manual":
        tax_left, tax_right = st.columns(2)
        export_tax = tax_left.number_input("Origin Export Tax %", 0.0, 100.0, float(origin_defaults["export_tax_percent"]), 0.5, key=f"manual_export_{origin}")
        import_tax = tax_right.number_input("Destination Import Tax %", 0.0, 100.0, float(destination_defaults["import_tax_percent"]), 0.5, key=f"manual_import_{destination}")
    else:
        export_tax = None
        import_tax = None
        st.caption(f"Default taxes: {origin_defaults['export_tax_percent']:g}% export · {destination_defaults['import_tax_percent']:g}% import")

    st.markdown("#### Wind at departure")
    wind_entry = st.radio("Wind entry", ["Match game HUD", "Enter world direction"], horizontal=True, key="wind_entry_mode")
    compass_col, wind_col = st.columns([1, 1])
    with wind_col:
        if wind_entry == "Match game HUD":
            ship_bearing = st.number_input("In-game Bearing", 0.0, 359.9, 0.0, 1.0, key="ship_bearing")
            hud_arrow = st.slider("Rotate the wind arrow to match the HUD", 0, 359, 180, 1, key="hud_arrow")
            wind_toward = hud_arrow_to_world_wind(ship_bearing, hud_arrow, arrow_represents_toward=bool(settings.get("wind_arrow_represents_toward", True)))
        else:
            ship_bearing = 0.0
            hud_arrow = st.slider("Wind direction (world compass)", 0, 359, 180, 1, key="absolute_wind")
            wind_toward = float(hud_arrow)
        st.metric("Global wind direction", f"{wind_toward:.0f}° toward")
        st.caption("0° North · 90° East · 180° South · 270° West")
    with compass_col:
        st.plotly_chart(wind_compass(ship_bearing, hud_arrow), width="stretch", config={"displayModeBar": False})

    with st.expander("Enemy warnings"):
        player_nation = st.selectbox("Player Nation", ["Not set"] + NATIONS, key="player_nation")
        enemy_nations = st.multiselect("Nations currently treated as enemies", [nation for nation in NATIONS if nation != player_nation], key="enemy_nations")
        if len(ownership.get("ports", {})) == 0:
            st.caption("Port ownership is not populated yet. Add it in Data & Debug to enable these warnings.")

    if st.button("GENERATE TRADE ROUTE", type="primary", width="stretch", key="generate_trade_route"):
        st.session_state.pop("route_debug", None)
        if origin == destination:
            st.error("Origin and destination must be different ports.")
        elif navigation_mode == "Current Position" and not current_position:
            st.error("Click the current ship position on the map first.")
        else:
            try:
                trade = calculate_trade(economy, origin, destination, ship, export_tax, import_tax)
                route_start = port_by_name[origin]
                route_end = port_by_name[destination]
                plan = None
                route_png = None
                enemy_alerts = []
                if route_start["route_eligible"] and route_end["route_eligible"]:
                    kwargs = {}
                    if current_position:
                        kwargs = {"navigation_start_region_id": current_position["region_id"], "navigation_start_point": tuple(current_position["point"]), "navigation_start_name": "Current ship position"}
                    with st.spinner("Victorsg_Khrushchev, is Checking the Winds"):
                        candidates = generate_world_route_candidates(route_start["region_id"], route_start["geometry_port_id"], route_end["region_id"], route_end["geometry_port_id"], max_candidates=12, **kwargs)
                        plan = choose_wind_route(candidates, ship, wind_toward, pixels_per_nautical_mile=settings.get("pixels_per_nautical_mile"))
                        route_png = render_unified_route(plan.route)
                        trade["generated_route_distance_px"] = plan.route.total_distance_px
                        enemy_alerts = diplomacy_warnings(economy, ownership, origin, destination, plan.route.region_sequence, enemy_nations)
                st.session_state.v2_result = {"trade": trade, "plan": plan, "route_png": route_png, "enemy_warnings": enemy_alerts, "origin": origin, "destination": destination}
                st.session_state.route_debug = {
                    "status": "SUCCESS",
                    "origin": origin,
                    "destination": destination,
                    "route_choice": None if plan is None else plan.route_choice,
                    "wind_strategy": None if plan is None else plan.strategy,
                    "anchor_resolutions": [] if plan is None else plan.route.anchor_resolutions,
                    "diagnostics": [] if plan is None else plan.route.diagnostics,
                    "candidate_summaries": [] if plan is None else plan.candidate_summaries,
                }
            except RouteDiagnosticError as exc:
                st.session_state.pop("v2_result", None)
                st.session_state.route_debug = {
                    "status": "ERROR",
                    "code": exc.code,
                    "message": exc.player_message,
                    "details": exc.details,
                    "origin": origin,
                    "destination": destination,
                }
                st.error(exc.player_message)
                st.caption("The detailed failure code and attempted alternatives are available in Data & Debug → Route Diagnostics.")
            except ValueError as exc:
                st.session_state.pop("v2_result", None)
                st.session_state.route_debug = {"status": "ERROR", "code": "INPUT_OR_MODEL_ERROR", "message": str(exc), "origin": origin, "destination": destination}
                st.error(str(exc))

    if "v2_result" in st.session_state:
        payload = st.session_state.v2_result
        trade = payload["trade"]
        plan = payload["plan"]
        st.subheader(f"{payload['origin']} → {payload['destination']}")
        cargo_col, ship_col, units_col = st.columns(3)
        cargo_col.metric("Cargo", trade["cargo"])
        ship_col.metric("Ship", trade["ship"])
        units_col.metric("Cargo units", trade["total_units"], f"{trade['ship_hold_units']} hold + 1 carried")
        if trade["gross_sell_value_per_unit_gbp"] is None:
            st.warning("No recorded Cargo Distance or game Value exists for this pair, so no sale or profit figure was invented.")
        else:
            first = st.columns(4)
            first[0].metric("Purchase / unit", f"£{trade['purchase_total_per_unit_gbp']:,}")
            first[1].metric("Expected sale / unit", f"£{trade['net_sale_per_unit_gbp']:,}")
            first[2].metric("Profit / unit", f"£{trade['profit_per_unit_gbp']:,}")
            first[3].metric("Total expected profit", f"£{trade['total_profit_gbp']:,}")
            st.caption(f"Applied taxes: {trade['origin_export_tax_percent']:g}% origin export · {trade['destination_import_tax_percent']:g}% destination import")
        if plan is None:
            st.warning("Deadman's Murcia is active for trade economics, but its route endpoint remains disabled until its exact navigable-water anchor is confirmed.")
        else:
            zoomable_route(payload["route_png"], "v2_route_zoom")
            filename = f"{payload['origin']}_to_{payload['destination']}_trade_route.png".replace(" ", "_")
            st.download_button("Download route image", payload["route_png"], filename, "image/png", width="stretch")
            route_metrics = st.columns(4)
            route_metrics[0].metric("Route distance", f"{plan.route.total_distance_px:,.1f} px")
            route_metrics[1].metric("ETA", "Scale needed" if plan.eta_minutes is None else f"{plan.eta_minutes / 60:.2f} h")
            route_metrics[2].metric("TP transitions", plan.route.teleport_count)
            route_metrics[3].metric("Tack points", len(plan.tack_points))
            st.caption("Regions: " + " → ".join(plan.route.region_sequence))
            adjusted_anchors = [
                row for row in plan.route.anchor_resolutions
                if row.get("port_semantic_point") != row.get("port_navigation_anchor")
            ]
            for anchor in adjusted_anchors:
                st.info(
                    f"{anchor['display_name']} uses nearby connected harbor water at "
                    f"({anchor['port_navigation_anchor'][0]}, {anchor['port_navigation_anchor'][1]}) for routing; "
                    "its visible port marker is unchanged."
                )
            if plan.eta_minutes is None:
                st.caption("Precise knot-based ETA and time-driven wind rotation remain disabled until one verified map-distance scale is entered in Data & Debug.")
            else:
                wind_end = wind_toward_at_elapsed(plan.wind_at_departure_deg, plan.eta_minutes)
                st.caption(f"Wind: {plan.wind_at_departure_deg:.0f}° toward at departure → approximately {wind_end:.0f}° toward at arrival")
            for warning in plan.warnings + payload["enemy_warnings"]:
                st.warning(warning)
            if plan.sail_instructions:
                st.markdown("#### Sail instructions")
                st.dataframe([{
                    "Tack": row["step"],
                    "Region": row["region_id"],
                    "Planned time": "—" if row.get("expected_elapsed_minutes") is None else f"{row['expected_elapsed_minutes']:.1f} min",
                    "Expected wind": "—" if row.get("expected_wind_toward_deg") is None else f"{row['expected_wind_toward_deg']:.0f}° toward",
                    "Instruction": row["instruction"],
                } for row in plan.sail_instructions], hide_index=True, width="stretch")
            with st.expander("Route validation details"):
                st.dataframe([{"Region": leg.region_name, "Distance px": round(leg.route_length_px, 1), "Minimum clearance px": round(leg.minimum_clearance_px, 1), "Required core clearance px": round(leg.required_clearance_px, 1), "Collision-free": leg.collision_free} for leg in plan.route.legs], hide_index=True, width="stretch")
        with st.expander("Trade calculation details"):
            st.json(trade)
    st.caption(WIND_DISCLAIMER)

with data_tab:
    st.subheader("Search and edit data")
    st.warning("Saving changes updates only the trade/diplomacy/settings layer. Stage 1 maps, masks, TP data, transforms, and routing geometry are not edited.")
    port_data_tab, cargo_data_tab, sale_data_tab, ship_data_tab, ownership_tab, settings_tab, diagnostics_tab, raw_tab = st.tabs(["Port Taxes", "Cargo Purchases", "Destination Values", "Ships", "Ownership", "Model Settings", "Route Diagnostics", "V2 Handoff"])
    with port_data_tab:
        search = st.text_input("Search port or region", key="port_search").strip().lower()
        subset = [row for row in economy["ports"] if not search or search in f"{row['display_name']} {row['region']}".lower()]
        edited = st.data_editor(subset, hide_index=True, width="stretch", disabled=["economy_port_id", "display_name", "region", "region_id", "geometry_port_id", "route_eligible", "geometry_status", "location_note", "tax_status", "tax_editable_default"], column_config={"import_tax_percent": st.column_config.NumberColumn("Import %", min_value=0.0, max_value=100.0), "export_tax_percent": st.column_config.NumberColumn("Export %", min_value=0.0, max_value=100.0)}, key="port_editor")
        if st.button("Save Port Tax Edits", key="save_ports"):
            persist_section("ports", editable_records(edited), ("economy_port_id",))
            st.success("Port tax defaults saved.")
    with cargo_data_tab:
        search = st.text_input("Search origin or cargo", key="cargo_search").strip().lower()
        subset = [row for row in economy["cargo_purchase_data"] if not search or search in f"{row['origin_port']} {row['cargo']} {row['region']}".lower()]
        edited = st.data_editor(subset, hide_index=True, width="stretch", disabled=["region", "origin_port"], column_config={"base_price_status": st.column_config.SelectboxColumn(options=["CONFIRMED", "ESTIMATED"]), "weight_status": st.column_config.SelectboxColumn(options=["CONFIRMED", "ESTIMATED"]), "base_price_gbp": st.column_config.NumberColumn("Base £", min_value=0.0), "weight_tons": st.column_config.NumberColumn("Weight t", min_value=0.1)}, key="cargo_editor")
        if st.button("Save Cargo Edits", key="save_cargo"):
            persist_section("cargo_purchase_data", editable_records(edited), ("origin_port",))
            st.success("Cargo data saved without changing confirmation status.")
    with sale_data_tab:
        origins = ["All"] + sorted({row["origin_port"] for row in economy["destination_sales"]})
        origin_filter = st.selectbox("Origin filter", origins, key="sale_origin_filter")
        search = st.text_input("Search origin, destination, or cargo", key="sale_search").strip().lower()
        subset = [row for row in economy["destination_sales"] if (origin_filter == "All" or row["origin_port"] == origin_filter) and (not search or search in f"{row['origin_port']} {row['destination_port']} {row['cargo']}".lower())]
        if len(subset) > 500:
            st.info(f"{len(subset):,} rows match. The editor shows the first 500; narrow the filter to edit another row.")
            subset = subset[:500]
        edited = st.data_editor(subset, hide_index=True, width="stretch", disabled=["origin_port", "cargo", "destination_port", "source", "supporting_frame_count", "distinct_ocr_tuples_seen"], column_config={"cargo_distance_m": st.column_config.NumberColumn("Cargo Distance m", min_value=0.0), "displayed_sell_value_gbp": st.column_config.NumberColumn("Game Value £", min_value=0), "distance_status": st.column_config.SelectboxColumn(options=["CONFIRMED_FROM_VIDEO", "CONFIRMED_FROM_SCREENSHOT", "CONFIRMED_RECORDED_RECIPROCAL_AUDIT", "CONFIRMED_FROM_GRIFFARDS_DESTINATION_LIST", "ESTIMATED", "NEEDS_REVIEW"]), "value_status": st.column_config.SelectboxColumn(options=["CONFIRMED_FROM_VIDEO", "CONFIRMED_FROM_SCREENSHOT", "DERIVED", "ESTIMATED", "NEEDS_REVIEW"])}, key="sale_editor")
        if st.button("Save Destination Edits", key="save_sales"):
            persist_section("destination_sales", editable_records(edited), ("origin_port", "destination_port"))
            st.success("Destination values and distances saved.")
    with ship_data_tab:
        edited = st.data_editor(economy["ships"], hide_index=True, width="stretch", disabled=["ship"], key="ship_editor")
        st.caption("The 9.0 kt normalized directional model is separate from listed/raw speed metadata.")
        if st.button("Save Ship Edits", key="save_ships"):
            persist_section("ships", editable_records(edited), ("ship",))
            st.success("Ship data saved.")
    with ownership_tab:
        ownership_rows = [{"Port": row["display_name"], "Region": row["region"], "Nation": ownership.get("ports", {}).get(row["display_name"], "Unknown")} for row in economy["ports"]]
        edited = st.data_editor(ownership_rows, hide_index=True, width="stretch", disabled=["Port", "Region"], column_config={"Nation": st.column_config.SelectboxColumn(options=["Unknown"] + NATIONS)}, key="ownership_editor")
        if st.button("Save Port Ownership", key="save_ownership"):
            records = editable_records(edited)
            ownership["ports"] = {row["Port"]: row["Nation"] for row in records if row["Nation"] != "Unknown"}
            ownership["source_status"] = "USER_REVIEWED_IN_APP"
            save_ownership(ownership)
            st.session_state.ownership_data = ownership
            st.success("Per-port ownership saved.")
        st.dataframe([{"Region": region, "Control": control} for region, control in sorted(region_controls(economy, ownership).items())], hide_index=True, width="stretch")
    with settings_tab:
        st.caption("A verified map scale is required before pixels can become nautical miles and a knot-based ETA. No default scale is guessed.")
        current_scale = settings.get("pixels_per_nautical_mile")
        scale_text = st.text_input("Verified pixels per nautical mile (leave blank if unknown)", "" if current_scale is None else str(current_scale), key="scale_text")
        arrow_toward = st.checkbox("HUD arrow represents the direction wind pushes toward", value=bool(settings.get("wind_arrow_represents_toward", True)), key="arrow_convention")
        if st.button("Save Model Settings", key="save_model_settings"):
            settings["pixels_per_nautical_mile"] = None if not scale_text.strip() else float(scale_text)
            settings["map_scale_status"] = "UNCALIBRATED" if settings["pixels_per_nautical_mile"] is None else "USER_CALIBRATED"
            settings["wind_arrow_represents_toward"] = arrow_toward
            save_settings(settings)
            st.session_state.v2_settings = settings
            st.success("Model settings saved.")
    with diagnostics_tab:
        st.caption("The latest route's endpoint snaps, candidate strategies, and any detailed failure information appear here. This does not alter Stage 1 geometry.")
        route_debug = st.session_state.get("route_debug")
        if route_debug is None:
            st.info("Generate a route to populate diagnostics.")
        else:
            st.json(route_debug)
            st.download_button(
                "Download Latest Route Diagnostics",
                json.dumps(route_debug, ensure_ascii=False, indent=2),
                "latest_route_diagnostics.json",
                "application/json",
                width="stretch",
            )
    with raw_tab:
        handoff = load_handoff()
        st.json(handoff)
        st.download_button("Download v2 handoff JSON", json.dumps(handoff, ensure_ascii=False, indent=2), "naval_route_trade_wind_handoff_v2.json", "application/json", width="stretch")
    st.download_button("Download Current Economy JSON", json.dumps(economy, ensure_ascii=False, indent=2), "economy_data.json", "application/json", width="stretch")

with status_tab:
    st.subheader("Imported data and remaining calibration")
    validation = validate_economy(economy)
    purchase_count = len(economy["cargo_purchase_data"])
    confirmed_purchase = sum(row["base_price_status"] == "CONFIRMED" for row in economy["cargo_purchase_data"])
    metrics = st.columns(5)
    metrics[0].metric("Current ports", len(economy["ports"]))
    metrics[1].metric("Routable anchors", sum(bool(row["route_eligible"]) for row in economy["ports"]))
    metrics[2].metric("Purchase rows", purchase_count)
    metrics[3].metric("Confirmed purchases", confirmed_purchase)
    metrics[4].metric("Destination rows", f"{len(economy['destination_sales']):,}")
    st.dataframe(validation, hide_index=True, width="stretch")
    st.markdown(f"""
**Still requiring calibration or user data**

- Deadman's Murcia remains economic-only until its exact East Somerset navigable-water anchor is supplied.
- Been's exact wind-angle curve remains partial/heuristic.
- Pembroke remains a Been-based proxy with better frontal-wind tolerance; its fixed spanker is never presented as movable.
- Numeric turning effects for spanker/mast asymmetry remain unmeasured; sail instructions are tactical guidance.
- Port ownership is populated for {len(ownership.get('ports', {}))} of 58 ports because the referenced ownership image was not included in the v2 ZIP.
- Map/path scale is {'not calibrated, so precise knot-based ETA is withheld' if settings.get('pixels_per_nautical_mile') is None else 'user-calibrated; ETA is approximate because variable wind strength is excluded'}.
""")
    st.caption("Cargo Distance remains game-economy data and is never substituted for generated sailing-route distance.")
