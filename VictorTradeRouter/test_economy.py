from __future__ import annotations

from collections import Counter

from economy import calculate_trade, load_economy, validate_economy


data = load_economy()
findings = validate_economy(data)
assert not [row for row in findings if row["severity"] == "ERROR"], findings
assert len(data["ports"]) == 58
assert len(data["cargo_purchase_data"]) == 58
assert len(data["ships"]) == 3
assert Counter(row["base_price_status"] for row in data["cargo_purchase_data"]) == {
    "CONFIRMED": 20,
    "ESTIMATED": 38,
}
deadman = next(row for row in data["ports"] if row["display_name"] == "Deadman's Murcia")
assert deadman["region_id"] == "ESO"
assert not deadman["route_eligible"]
assert deadman["geometry_port_id"] is None

observed = next(
    row
    for row in data["destination_sales"]
    if row["value_status"] == "CONFIRMED_FROM_VIDEO"
)
result = calculate_trade(data, observed["origin_port"], observed["destination_port"], "Pembroke")
assert result["gross_sell_value_per_unit_gbp"] == observed["displayed_sell_value_gbp"]
assert result["gross_sell_value_status"] == "CONFIRMED_FROM_VIDEO"
assert result["cargo_distance_m"] == observed["cargo_distance_m"]
assert result["total_units"] == result["ship_hold_units"] + 1
assert result["generated_route_distance_px"] is None

derived = next((row for row in data["destination_sales"] if row["value_status"] == "DERIVED"), None)
assert derived is not None
derived_result = calculate_trade(data, derived["origin_port"], derived["destination_port"], "Hoy")
assert derived_result["gross_sell_value_status"] == "DERIVED"

print(
    f"PASS economy: {len(data['ports'])} ports, {len(data['destination_sales'])} destination rows, "
    "statuses preserved, taxes separate, +1 cargo rule applied"
)
