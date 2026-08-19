from __future__ import annotations

import io
import unittest
from pathlib import Path

from PIL import Image

from economy import calculate_trade, load_economy
from recommendations import generate_trade_recommendations
from routing import generate_world_route_candidates, render_unified_route, world_alignment
from wind import choose_wind_route, sail_instruction


class NavalTradeV4Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.economy = load_economy()
        cls.local_candidates = generate_world_route_candidates(
            "BEL", "BEL-P04", "BEL", "BEL-P02", max_candidates=4
        )

    def test_home_recommendations_rank_profitable_voyages(self):
        rows = generate_trade_recommendations(
            self.economy, "Petit Anvers", "Pembroke", 180, limit=18
        )
        self.assertEqual(len(rows), 18)
        self.assertEqual([row["rank"] for row in rows], list(range(1, 19)))
        self.assertTrue(all(row["total_profit_gbp"] > 0 for row in rows))
        self.assertTrue(all(rows[i]["raw_rank_score"] >= rows[i + 1]["raw_rank_score"] for i in range(len(rows) - 1)))
        self.assertTrue(all(row["time_estimate"] in {"Short", "Moderate", "Long", "Very long"} for row in rows))
        self.assertTrue(all(row["wind_rating"] in {"Favorable", "Manageable", "Demanding", "Difficult"} for row in rows))

    def test_recommendation_profit_matches_economy_calculation(self):
        row = generate_trade_recommendations(
            self.economy, "Petit Anvers", "Pembroke", 180, limit=1
        )[0]
        trade = calculate_trade(self.economy, "Petit Anvers", row["destination"], "Pembroke")
        self.assertEqual(row["total_profit_gbp"], trade["total_profit_gbp"])

    def test_recommendations_respond_to_departure_wind(self):
        north = generate_trade_recommendations(self.economy, "Louisbourg", "Hoy", 0, limit=58)
        east = generate_trade_recommendations(self.economy, "Louisbourg", "Hoy", 90, limit=58)
        north_by_port = {row["destination"]: row for row in north}
        east_by_port = {row["destination"]: row for row in east}
        shared = set(north_by_port) & set(east_by_port)
        self.assertTrue(any(
            north_by_port[name]["wind_rating"] != east_by_port[name]["wind_rating"]
            or north_by_port[name]["trade_score"] != east_by_port[name]["trade_score"]
            for name in shared
        ))

    def test_route_image_is_map_only_without_report_header(self):
        plan = choose_wind_route(
            self.local_candidates, "Hoy", 0, pixels_per_nautical_mile=100
        )
        image = Image.open(io.BytesIO(render_unified_route(plan.route)))
        world = Image.open(Path(__file__).parent / world_alignment()["world_map"])
        self.assertEqual(image.size, world.size)

    def test_tack_symbol_is_directional_orange_arrow(self):
        plan = choose_wind_route(
            self.local_candidates, "Hoy", 135, pixels_per_nautical_mile=100
        )
        self.assertGreater(len(plan.tack_points), 0)
        image = Image.open(io.BytesIO(render_unified_route(plan.route))).convert("RGB")
        tack = plan.tack_points[0]
        first, second = world_alignment()["regions"][tack["region_id"]]
        x, y = tack["point"]
        wx = int(round(first[0] * x + first[1] * y + first[2]))
        wy = int(round(second[0] * x + second[1] * y + second[2]))
        colors = {
            image.getpixel((px, py))
            for py in range(max(0, wy - 22), min(image.height, wy + 23))
            for px in range(max(0, wx - 22), min(image.width, wx + 23))
        }
        self.assertIn((255, 151, 42), colors)

    def test_common_tack_warning_is_removed(self):
        plan = choose_wind_route(
            self.local_candidates, "Hoy", 0, pixels_per_nautical_mile=100
        )
        self.assertNotIn(
            "Unfavorable wind makes one or more tactical tacks worthwhile.",
            plan.warnings,
        )

    def test_sail_orders_name_the_route_and_action(self):
        self.assertIn("next cyan route segment", sail_instruction("Hoy", True, 1.0))
        self.assertIn("Shiver the topsail", sail_instruction("Been", True, 1.0))
        self.assertIn("Fore/Main/Mizzen", sail_instruction("Pembroke", True, 1.0))

    def test_ui_contains_home_transfer_collapse_and_bottom_data_center(self):
        app_source = Path(__file__).with_name("app.py").read_text(encoding="utf-8")
        interface_source = Path(__file__).with_name("interface_v4.py").read_text(encoding="utf-8")
        self.assertIn("generate_trade_recommendations", app_source)
        self.assertIn('st.session_state.active_page = "ROUTE PLANNER"', app_source)
        self.assertIn('expanded=payload is None', interface_source)
        self.assertIn('st.expander("DATA, DEBUG & STATUS"', interface_source)
        self.assertIn('"Overview", "Port Taxes", "Cargo", "Destination Values"', interface_source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
