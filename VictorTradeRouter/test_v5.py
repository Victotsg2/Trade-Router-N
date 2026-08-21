from __future__ import annotations

import unittest
from pathlib import Path
import tomllib

from routing import generate_world_route_candidates
from wind import WIND_DISCLAIMER, choose_wind_route


class VictorTradeRouterV5Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).parent
        cls.app_source = (cls.root / "app.py").read_text(encoding="utf-8")
        cls.interface_source = (cls.root / "interface_v4.py").read_text(encoding="utf-8")
        cls.wind_source = (cls.root / "wind.py").read_text(encoding="utf-8")

    def test_branding_and_home_labels(self):
        self.assertIn("Victor's Trade Router", self.app_source)
        self.assertIn("VICTOR'S TRADE ROUTER", self.app_source)
        self.assertIn("max-width:none; height:clamp(205px,20vw,250px)", self.app_source)
        self.assertIn('st.markdown("## TRADE INFO")', self.app_source)
        self.assertIn('st.markdown("### RECOMMENDED ROUTES")', self.app_source)
        self.assertIn("<extra>Select Route</extra>", self.app_source)
        self.assertNotIn("Routes · Cargo · Wind", self.app_source)

    def test_removed_home_explanations_are_absent(self):
        self.assertNotIn("Rank combines expected total profit", self.app_source)
        self.assertNotIn("Wind pushes toward {wind_toward}", self.app_source)
        self.assertNotIn('st.metric("Wind pushes toward"', self.interface_source)
        self.assertNotIn("N 0° · E 90° · S 180° · W 270°", self.interface_source)

    def test_home_uses_octagonal_compass(self):
        self.assertIn('key="home_wind_compass"', self.app_source)
        self.assertIn('(315 - ship_bearing) % 360', self.app_source)
        self.assertIn('("NE", (45 - ship_bearing) % 360)', self.app_source)
        self.assertIn('("SE", (135 - ship_bearing) % 360)', self.app_source)

    def test_navigation_is_centered_below_header(self):
        self.assertNotIn("with st.sidebar:", self.interface_source)
        self.assertIn("home_col, planner_col", self.interface_source)
        self.assertIn("windward-nav-spacer", self.app_source)

    def test_unavailable_time_box_and_caption_are_removed(self):
        self.assertIn("if plan.eta_minutes is None:", self.interface_source)
        self.assertIn('route_metrics = st.columns(3)', self.interface_source)
        self.assertNotIn("Estimate unavailable", self.interface_source)
        self.assertNotIn("Time remains an estimate category", self.interface_source)

    def test_shorter_notice_is_prominent(self):
        self.assertNotIn("Wind estimates account for global wind direction", WIND_DISCLAIMER)
        self.assertIn("Regional wind speed variations", WIND_DISCLAIMER)
        self.assertIn("windward-warning", self.interface_source)

    def test_unfavorable_wind_warning_removed_but_tacking_preserved(self):
        self.assertNotIn("Unfavorable wind materially slows part of this route.", self.wind_source)
        candidates = generate_world_route_candidates(
            "BEL", "BEL-P04", "BEL", "BEL-P02", max_candidates=4
        )
        plan = choose_wind_route(
            candidates, "Hoy", 135, pixels_per_nautical_mile=100
        )
        self.assertGreater(len(plan.tack_points), 0)
        self.assertTrue(plan.sail_instructions)

    def test_short_path_wind_data_is_present_and_loadable(self):
        short_handoff = self.root / "data" / "wind_v2.json"
        self.assertTrue(short_handoff.is_file())
        self.assertIn('HANDOFF = DATA_DIR / "wind_v2.json"', self.wind_source)

    def test_light_and_dark_themes_have_readable_contrast(self):
        config_path = self.root / ".streamlit" / "config.toml"
        config = tomllib.loads(config_path.read_text(encoding="utf-8"))

        def luminance(hex_color: str) -> float:
            channels = [int(hex_color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
            linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in channels]
            return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

        def contrast(first: str, second: str) -> float:
            bright, dark = sorted((luminance(first), luminance(second)), reverse=True)
            return (bright + 0.05) / (dark + 0.05)

        for mode in ("light", "dark"):
            theme = config["theme"][mode]
            self.assertGreaterEqual(contrast(theme["textColor"], theme["backgroundColor"]), 7.0)
            self.assertGreaterEqual(contrast(theme["textColor"], theme["secondaryBackgroundColor"]), 7.0)
        self.assertIn("background-color:var(--background-color)", self.app_source)
        self.assertIn("background:var(--secondary-background-color)", self.app_source)
        self.assertIn("color:var(--text-color)", self.app_source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
