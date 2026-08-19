from __future__ import annotations

import unittest

import numpy as np

from routing import (
    NARROW_PASSAGE_CLEARANCE_PX,
    OPEN_WATER_CLEARANCE_PX,
    PORT_APPROACH_CLEARANCE_PX,
    TP_APPROACH_CLEARANCE_PX,
    _astar,
    generate_route,
)


class AdaptiveClearanceTests(unittest.TestCase):
    def test_clearance_policy_matches_approved_values(self):
        self.assertEqual(OPEN_WATER_CLEARANCE_PX, 14.0)
        self.assertEqual(NARROW_PASSAGE_CLEARANCE_PX, 10.0)
        self.assertEqual(PORT_APPROACH_CLEARANCE_PX, 5.0)
        self.assertEqual(TP_APPROACH_CLEARANCE_PX, 8.0)

    def test_astar_prefers_open_water_but_accepts_a_narrow_passage(self):
        mask = np.ones((35, 80), dtype=bool)
        clearance = np.full(mask.shape, OPEN_WATER_CLEARANCE_PX)
        clearance[17, 2:78] = NARROW_PASSAGE_CLEARANCE_PX
        preferred = _astar(mask, (2, 17), (77, 17), clearance)
        self.assertTrue(any(y != 17 for _, y in preferred[1:-1]))

        channel = np.zeros((35, 80), dtype=bool)
        channel[17, 2:78] = True
        channel_clearance = np.full(channel.shape, NARROW_PASSAGE_CLEARANCE_PX)
        necessary = _astar(channel, (2, 17), (77, 17), channel_clearance)
        self.assertTrue(all(y == 17 for _, y in necessary))

    def test_vysarian_interior_passage_is_used_without_touching_obstacles(self):
        route = generate_route("VYS", "VYS-TP01", "VYS-P01")
        self.assertTrue(route.collision_free)
        self.assertTrue(route.clearance_respected)
        self.assertEqual(route.required_clearance_px, NARROW_PASSAGE_CLEARANCE_PX)
        self.assertGreaterEqual(route.core_minimum_clearance_px + 1e-6, NARROW_PASSAGE_CLEARANCE_PX)
        self.assertLess(route.route_length_px, 800.0)
        self.assertGreater(min(y for _, y in route.route_pixels), 350)


if __name__ == "__main__":
    unittest.main(verbosity=2)
