from __future__ import annotations

import json
from typing import Callable

import pandas as pd
import streamlit as st

from diplomacy import NATIONS, diplomacy_warnings, region_controls, save_ownership, save_settings
from economy import calculate_trade, save_economy, validate_economy
from routing import RouteDiagnosticError, generate_world_route_candidates, render_unified_route
from wind import WIND_DISCLAIMER, choose_wind_route, hud_arrow_to_world_wind, load_handoff, wind_after_setup, wind_toward_at_elapsed


ROUTE_LOADING_MESSAGE = "Victorsg_Khrushchev is Checking the Winds"
ROUTE_COMPLETE_MESSAGE = "The Wind is Ward"


def _editable_records(value) -> list[dict]:
    if isinstance(value, pd.DataFrame):
        return json.loads(value.to_json(orient="records"))
    return list(value)


def _persist_section(economy: dict, section: str, rows: list[dict], key_fields: tuple[str, ...]) -> None:
    current = economy[section]
    updates = {tuple(row[field] for field in key_fields): row for row in rows}
    economy[section] = [updates.get(tuple(row[field] for field in key_fields), row) for row in current]
    save_economy(economy)


def _nav() -> str:
    if "active_page" not in st.session_state:
        st.session_state.active_page = "HOME"
    st.markdown("<div class='windward-nav-spacer'></div>", unsafe_allow_html=True)
    _, home_col, planner_col, _ = st.columns([2.25, 1.0, 1.35, 2.25])
    if home_col.button("HOME", width="stretch", type="primary" if st.session_state.active_page == "HOME" else "secondary"):
        st.session_state.active_page = "HOME"
        st.rerun()
    if planner_col.button("ROUTE PLANNER", width="stretch", type="primary" if st.session_state.active_page == "ROUTE PLANNER" else "secondary"):
        st.session_state.active_page = "ROUTE PLANNER"
        st.rerun()
    return st.session_state.active_page


def _generate_route(
    economy: dict,
    ownership: dict,
    settings: dict,
    port_by_name: dict,
    origin: str,
    destination: str,
    ship: str,
    export_tax: float | None,
    import_tax: float | None,
    navigation_mode: str,
    current_position: dict | None,
    wind_toward: float,
    enemy_nations: list[str],
) -> None:
    st.session_state.pop("route_debug", None)
    st.session_state.pop("route_generation_complete", None)
    if origin == destination:
        st.error("Origin and destination must be different ports.")
        return
    if navigation_mode == "Current Position" and not current_position:
        st.error("Select the ship's current water position first.")
        return
    try:
        trade = calculate_trade(economy, origin, destination, ship, export_tax, import_tax)
        route_start = port_by_name[origin]
        route_end = port_by_name[destination]
        plan = None
        route_png = None
        enemy_alerts: list[str] = []
        if route_start["route_eligible"] and route_end["route_eligible"]:
            kwargs = {}
            if current_position:
                kwargs = {
                    "navigation_start_region_id": current_position["region_id"],
                    "navigation_start_point": tuple(current_position["point"]),
                    "navigation_start_name": "Current ship position",
                }
            with st.spinner(ROUTE_LOADING_MESSAGE):
                candidates = generate_world_route_candidates(
                    route_start["region_id"], route_start["geometry_port_id"],
                    route_end["region_id"], route_end["geometry_port_id"],
                    max_candidates=12, **kwargs,
                )
                plan = choose_wind_route(
                    candidates, ship, wind_toward,
                    pixels_per_nautical_mile=settings.get("pixels_per_nautical_mile"),
                )
                route_png = render_unified_route(plan.route)
                trade["generated_route_distance_px"] = plan.route.total_distance_px
                enemy_alerts = diplomacy_warnings(
                    economy, ownership, origin, destination,
                    plan.route.region_sequence, enemy_nations,
                )
        st.session_state.v2_result = {
            "trade": trade, "plan": plan, "route_png": route_png,
            "enemy_warnings": enemy_alerts, "origin": origin, "destination": destination,
        }
        st.session_state.route_debug = {
            "status": "SUCCESS", "origin": origin, "destination": destination,
            "route_choice": None if plan is None else plan.route_choice,
            "wind_strategy": None if plan is None else plan.strategy,
            "anchor_resolutions": [] if plan is None else plan.route.anchor_resolutions,
            "diagnostics": [] if plan is None else plan.route.diagnostics,
            "candidate_summaries": [] if plan is None else plan.candidate_summaries,
        }
        st.session_state.route_generation_complete = True
        st.rerun()
    except RouteDiagnosticError as exc:
        st.session_state.pop("v2_result", None)
        st.session_state.route_debug = {
            "status": "ERROR", "code": exc.code, "message": exc.player_message,
            "details": exc.details, "origin": origin, "destination": destination,
        }
        st.error(exc.player_message)
        st.caption("Technical details are available at the bottom of the page under Data, Debug & Status.")
    except ValueError as exc:
        st.session_state.pop("v2_result", None)
        st.session_state.route_debug = {
            "status": "ERROR", "code": "INPUT_OR_MODEL_ERROR",
            "message": str(exc), "origin": origin, "destination": destination,
        }
        st.error(str(exc))


def _result_view(
    payload: dict,
    *,
    zoomable_route: Callable,
    render_trade_summary: Callable,
    clear_sail_instruction: Callable,
) -> None:
    trade = payload["trade"]
    plan = payload["plan"]
    render_trade_summary(payload)
    if trade["gross_sell_value_per_unit_gbp"] is None:
        st.warning("No recorded Cargo Distance or game Value exists for this voyage, so no sale or profit figure was invented.")
    else:
        st.caption(
            f"Buy £{trade['purchase_total_per_unit_gbp']:,} / unit · "
            f"Sell £{trade['net_sale_per_unit_gbp']:,} / unit · "
            f"Taxes {trade['origin_export_tax_percent']:g}% export and {trade['destination_import_tax_percent']:g}% import"
        )
    if plan is None:
        st.warning("This port is available for trade records but does not yet have a confirmed route anchor.")
        return
    zoomable_route(payload["route_png"], "v4_route_zoom")
    filename = f"{payload['origin']}_to_{payload['destination']}_trade_route.png".replace(" ", "_")
    st.download_button("SAVE ROUTE MAP", payload["route_png"], filename, "image/png", width="stretch")
    with st.expander("VOYAGE DETAILS", expanded=False):
        if plan.eta_minutes is None:
            route_metrics = st.columns(3)
            route_metrics[0].metric("Route distance", f"{plan.route.total_distance_px:,.1f} px")
            route_metrics[1].metric("Teleports", plan.route.teleport_count)
            route_metrics[2].metric("Tacks", len(plan.tack_points))
        else:
            route_metrics = st.columns(4)
            route_metrics[0].metric("Route distance", f"{plan.route.total_distance_px:,.1f} px")
            route_metrics[1].metric("Time", f"~{plan.eta_minutes / 60:.2f} h")
            route_metrics[2].metric("Teleports", plan.route.teleport_count)
            route_metrics[3].metric("Tacks", len(plan.tack_points))
        st.caption("Regions: " + " → ".join(plan.route.region_sequence))
        if plan.eta_minutes is not None:
            wind_end = wind_toward_at_elapsed(plan.wind_at_departure_deg, plan.eta_minutes)
            st.caption(
                f"Wind: {plan.wind_when_charted_deg:.0f}° while charting → "
                f"{plan.wind_at_departure_deg:.0f}° once underway → "
                f"about {wind_end:.0f}° at arrival"
            )
        for warning in plan.warnings + payload["enemy_warnings"]:
            st.warning(warning)
        if plan.sail_instructions:
            st.markdown("### TACK ORDERS")
            st.caption("Each orange arrow on the map points along the new heading.")
            st.dataframe(
                [clear_sail_instruction(row) for row in plan.sail_instructions],
                hide_index=True, width="stretch",
            )
        adjusted = [
            row for row in plan.route.anchor_resolutions
            if row.get("port_semantic_point") != row.get("port_navigation_anchor")
        ]
        if adjusted:
            st.caption("Nearby harbor water was used where a visible port marker was not connected to open water.")


def _route_planner(
    economy: dict,
    ownership: dict,
    settings: dict,
    *,
    map_port_picker: Callable,
    dropdown_port_picker: Callable,
    current_position_picker: Callable,
    wind_compass: Callable,
    zoomable_route: Callable,
    render_trade_summary: Callable,
    clear_sail_instruction: Callable,
) -> None:
    port_by_name = {row["display_name"]: row for row in economy["ports"]}
    payload = st.session_state.get("v2_result")
    with st.expander("CHANGE VOYAGE SETTINGS", expanded=payload is None):
        selection_mode = st.radio("Select ports using", ["Dropdowns", "Map"], horizontal=True, key="port_selection_mode")
        origin, destination = map_port_picker(economy) if selection_mode == "Map" else dropdown_port_picker(economy)
        st.caption(f"{origin} → {destination}")
        navigation_mode = st.radio("Navigation start", ["Origin Port", "Current Position"], horizontal=True, key="navigation_start_mode")
        current_position = current_position_picker() if navigation_mode == "Current Position" else None
        ship_col, tax_col = st.columns(2)
        ship = ship_col.selectbox("Ship", [row["ship"] for row in economy["ships"]], key="v2_ship")
        tax_mode = tax_col.selectbox("Tax", ["Default", "Manual"], key="v2_tax_mode")
        origin_defaults = port_by_name[origin]
        destination_defaults = port_by_name[destination]
        if tax_mode == "Manual":
            tax_left, tax_right = st.columns(2)
            export_tax = tax_left.number_input("Origin export tax %", 0.0, 100.0, float(origin_defaults["export_tax_percent"]), 0.5, key=f"manual_export_{origin}")
            import_tax = tax_right.number_input("Destination import tax %", 0.0, 100.0, float(destination_defaults["import_tax_percent"]), 0.5, key=f"manual_import_{destination}")
        else:
            export_tax = None
            import_tax = None
            st.caption(f"Default taxes: {origin_defaults['export_tax_percent']:g}% export · {destination_defaults['import_tax_percent']:g}% import")
        st.markdown("### DEPARTURE WIND")
        wind_entry = st.radio("Wind entry", ["Match game HUD", "Enter world direction"], horizontal=True, key="wind_entry_mode")
        compass_col, wind_col = st.columns([1, 1])
        with wind_col:
            if wind_entry == "Match game HUD":
                ship_bearing = st.number_input("In-game bearing", 0.0, 359.9, 0.0, 1.0, key="ship_bearing")
                if "hud_arrow" not in st.session_state:
                    st.session_state.hud_arrow = 180
                hud_arrow = st.slider("Rotate arrow to match HUD", 0, 359, step=1, key="hud_arrow")
                wind_toward = hud_arrow_to_world_wind(ship_bearing, hud_arrow, arrow_represents_toward=bool(settings.get("wind_arrow_represents_toward", True)))
            else:
                ship_bearing = 0.0
                if "absolute_wind" not in st.session_state:
                    st.session_state.absolute_wind = 180
                hud_arrow = st.slider("Current wind direction", 0, 359, step=1, key="absolute_wind")
                wind_toward = float(hud_arrow)
            st.caption(f"Expected wind once underway: {wind_after_setup(wind_toward):.0f}°")
        with compass_col:
            st.plotly_chart(wind_compass(ship_bearing, hud_arrow), width="stretch", config={"displayModeBar": False})
        with st.expander("Enemy waters", expanded=False):
            player_nation = st.selectbox("Player nation", ["Not set"] + NATIONS, key="player_nation")
            enemy_nations = st.multiselect("Enemy nations", [nation for nation in NATIONS if nation != player_nation], key="enemy_nations")
        if st.button("CHART THIS VOYAGE", type="primary", width="stretch", key="generate_trade_route"):
            _generate_route(
                economy, ownership, settings, port_by_name, origin, destination, ship,
                export_tax, import_tax, navigation_mode, current_position, wind_toward, enemy_nations,
            )
    if st.session_state.pop("route_generation_complete", False):
        st.success(ROUTE_COMPLETE_MESSAGE)
    if payload is not None:
        _result_view(
            payload,
            zoomable_route=zoomable_route,
            render_trade_summary=render_trade_summary,
            clear_sail_instruction=clear_sail_instruction,
        )
    st.markdown(f"<div class='windward-warning'>{WIND_DISCLAIMER}</div>", unsafe_allow_html=True)


def _data_center(economy: dict, ownership: dict, settings: dict) -> None:
    st.caption("Changes here affect data and settings only. Locked maps, masks, teleports, transforms, and geometry are not edited.")
    overview_tab, port_tab, cargo_tab, sale_tab, ship_tab, ownership_tab, settings_tab, diagnostics_tab, raw_tab = st.tabs([
        "Overview", "Port Taxes", "Cargo", "Destination Values", "Ships",
        "Ownership", "Settings", "Route Diagnostics", "Source Data",
    ])
    with overview_tab:
        validation = validate_economy(economy)
        purchase_count = len(economy["cargo_purchase_data"])
        confirmed_purchase = sum(row["base_price_status"] == "CONFIRMED" for row in economy["cargo_purchase_data"])
        ownership_count = len(ownership.get("ports") or {})
        metrics = st.columns(5)
        metrics[0].metric("Ports", len(economy["ports"]))
        metrics[1].metric("Routable", sum(bool(row["route_eligible"]) for row in economy["ports"]))
        metrics[2].metric("Cargo rows", purchase_count)
        metrics[3].metric("Confirmed", confirmed_purchase)
        metrics[4].metric("Sale rows", f"{len(economy['destination_sales']):,}")
        st.dataframe(validation, hide_index=True, width="stretch")
        st.markdown(f"""
**Remaining calibration**

- Deadman's Murcia still needs its exact East Somerset water anchor.
- Been and Pembroke wind curves remain partial/proxy models.
- Numeric sail-turn timing remains unmeasured.
- Port ownership is populated for {ownership_count} of 58 ports.
- Map scale is {'not calibrated' if settings.get('pixels_per_nautical_mile') is None else 'user calibrated'}.
""")
    with port_tab:
        search = st.text_input("Search port or region", key="port_search").strip().lower()
        subset = [row for row in economy["ports"] if not search or search in f"{row['display_name']} {row['region']}".lower()]
        edited = st.data_editor(subset, hide_index=True, width="stretch", disabled=["economy_port_id", "display_name", "region", "region_id", "geometry_port_id", "route_eligible", "geometry_status", "location_note", "tax_status", "tax_editable_default"], column_config={"import_tax_percent": st.column_config.NumberColumn("Import %", min_value=0.0, max_value=100.0), "export_tax_percent": st.column_config.NumberColumn("Export %", min_value=0.0, max_value=100.0)}, key="port_editor")
        if st.button("Save port taxes", key="save_ports"):
            _persist_section(economy, "ports", _editable_records(edited), ("economy_port_id",))
            st.success("Port taxes saved.")
    with cargo_tab:
        search = st.text_input("Search origin or cargo", key="cargo_search").strip().lower()
        subset = [row for row in economy["cargo_purchase_data"] if not search or search in f"{row['origin_port']} {row['cargo']} {row['region']}".lower()]
        edited = st.data_editor(subset, hide_index=True, width="stretch", disabled=["region", "origin_port"], column_config={"base_price_status": st.column_config.SelectboxColumn(options=["CONFIRMED", "ESTIMATED"]), "weight_status": st.column_config.SelectboxColumn(options=["CONFIRMED", "ESTIMATED"]), "base_price_gbp": st.column_config.NumberColumn("Base £", min_value=0.0), "weight_tons": st.column_config.NumberColumn("Weight t", min_value=0.1)}, key="cargo_editor")
        if st.button("Save cargo", key="save_cargo"):
            _persist_section(economy, "cargo_purchase_data", _editable_records(edited), ("origin_port",))
            st.success("Cargo data saved with its confirmation status.")
    with sale_tab:
        origins = ["All"] + sorted({row["origin_port"] for row in economy["destination_sales"]})
        origin_filter = st.selectbox("Origin filter", origins, key="sale_origin_filter")
        search = st.text_input("Search origin, destination, or cargo", key="sale_search").strip().lower()
        subset = [row for row in economy["destination_sales"] if (origin_filter == "All" or row["origin_port"] == origin_filter) and (not search or search in f"{row['origin_port']} {row['destination_port']} {row['cargo']}".lower())]
        if len(subset) > 500:
            st.info(f"{len(subset):,} rows match. The first 500 are shown.")
            subset = subset[:500]
        edited = st.data_editor(subset, hide_index=True, width="stretch", disabled=["origin_port", "cargo", "destination_port", "source", "supporting_frame_count", "distinct_ocr_tuples_seen"], column_config={"cargo_distance_m": st.column_config.NumberColumn("Cargo Distance m", min_value=0.0), "displayed_sell_value_gbp": st.column_config.NumberColumn("Game Value £", min_value=0), "distance_status": st.column_config.SelectboxColumn(options=["CONFIRMED_FROM_VIDEO", "CONFIRMED_FROM_SCREENSHOT", "CONFIRMED_RECORDED_RECIPROCAL_AUDIT", "CONFIRMED_FROM_GRIFFARDS_DESTINATION_LIST", "ESTIMATED", "NEEDS_REVIEW"]), "value_status": st.column_config.SelectboxColumn(options=["CONFIRMED_FROM_VIDEO", "CONFIRMED_FROM_SCREENSHOT", "DERIVED", "ESTIMATED", "NEEDS_REVIEW"])}, key="sale_editor")
        if st.button("Save destination values", key="save_sales"):
            _persist_section(economy, "destination_sales", _editable_records(edited), ("origin_port", "destination_port"))
            st.success("Destination values saved.")
    with ship_tab:
        edited = st.data_editor(economy["ships"], hide_index=True, width="stretch", disabled=["ship"], key="ship_editor")
        if st.button("Save ships", key="save_ships"):
            _persist_section(economy, "ships", _editable_records(edited), ("ship",))
            st.success("Ship data saved.")
    with ownership_tab:
        ownership_rows = [{"Port": row["display_name"], "Region": row["region"], "Nation": ownership.get("ports", {}).get(row["display_name"], "Unknown")} for row in economy["ports"]]
        edited = st.data_editor(ownership_rows, hide_index=True, width="stretch", disabled=["Port", "Region"], column_config={"Nation": st.column_config.SelectboxColumn(options=["Unknown"] + NATIONS)}, key="ownership_editor")
        if st.button("Save ownership", key="save_ownership"):
            records = _editable_records(edited)
            ownership["ports"] = {row["Port"]: row["Nation"] for row in records if row["Nation"] != "Unknown"}
            ownership["source_status"] = "USER_REVIEWED_IN_APP"
            save_ownership(ownership)
            st.session_state.ownership_data = ownership
            st.success("Ownership saved.")
        st.dataframe([{"Region": region, "Control": control} for region, control in sorted(region_controls(economy, ownership).items())], hide_index=True, width="stretch")
    with settings_tab:
        current_scale = settings.get("pixels_per_nautical_mile")
        scale_text = st.text_input("Verified pixels per nautical mile", "" if current_scale is None else str(current_scale), key="scale_text")
        arrow_toward = st.checkbox("HUD arrow shows where wind pushes toward", value=bool(settings.get("wind_arrow_represents_toward", True)), key="arrow_convention")
        if st.button("Save settings", key="save_model_settings"):
            settings["pixels_per_nautical_mile"] = None if not scale_text.strip() else float(scale_text)
            settings["map_scale_status"] = "UNCALIBRATED" if settings["pixels_per_nautical_mile"] is None else "USER_CALIBRATED"
            settings["wind_arrow_represents_toward"] = arrow_toward
            save_settings(settings)
            st.session_state.v2_settings = settings
            st.success("Settings saved.")
    with diagnostics_tab:
        route_debug = st.session_state.get("route_debug")
        if route_debug is None:
            st.info("Chart a route to populate diagnostics.")
        else:
            st.json(route_debug)
            st.download_button("Download diagnostics", json.dumps(route_debug, ensure_ascii=False, indent=2), "latest_route_diagnostics.json", "application/json", width="stretch")
    with raw_tab:
        handoff = load_handoff()
        st.json(handoff)
        st.download_button("Download v2 handoff", json.dumps(handoff, ensure_ascii=False, indent=2), "naval_route_trade_wind_handoff_v2.json", "application/json", width="stretch")
        st.download_button("Download economy data", json.dumps(economy, ensure_ascii=False, indent=2), "economy_data.json", "application/json", width="stretch")


def run_interface(
    economy: dict,
    ownership: dict,
    settings: dict,
    *,
    render_home: Callable,
    map_port_picker: Callable,
    dropdown_port_picker: Callable,
    current_position_picker: Callable,
    wind_compass: Callable,
    zoomable_route: Callable,
    render_trade_summary: Callable,
    clear_sail_instruction: Callable,
) -> None:
    page = _nav()
    if page == "HOME":
        render_home(economy)
    else:
        _route_planner(
            economy, ownership, settings,
            map_port_picker=map_port_picker,
            dropdown_port_picker=dropdown_port_picker,
            current_position_picker=current_position_picker,
            wind_compass=wind_compass,
            zoomable_route=zoomable_route,
            render_trade_summary=render_trade_summary,
            clear_sail_instruction=clear_sail_instruction,
        )
    st.divider()
    with st.expander("DATA, DEBUG & STATUS", expanded=False):
        _data_center(economy, ownership, settings)
