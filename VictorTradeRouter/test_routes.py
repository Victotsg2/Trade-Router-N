from routing import generate_route, generate_world_route


def check_world(start_region, start_port, destination_region, destination_port, minimum_teleports=1):
    result = generate_world_route(start_region, start_port, destination_region, destination_port)
    assert result.collision_free
    assert result.clearance_respected
    assert result.transition_locations_match
    assert result.teleport_count >= minimum_teleports
    assert result.legs[0].region_id == start_region
    assert result.legs[-1].region_id == destination_region
    print(
        f"PASS {' -> '.join(result.region_sequence)} | "
        f"{result.teleport_count} TP | {result.total_distance_px:.1f}px | "
        f"{result.sequences_evaluated} sequences compared"
    )


# Preserve the approved local Belle Isles test.
local = generate_route("BEL", "BEL-P04", "BEL-TP-STP")
assert local.collision_free and local.clearance_respected
print(f"PASS Belle Isles local: Petit Anvers -> Saint-Pierre TP | {local.route_length_px:.1f}px")

# Required cross-region coverage.
check_world("BEL", "BEL-P04", "KIN", "KIN-P01")
check_world("VYS", "VYS-P01", "STP", "STP-P01")
check_world("SPO", "SPO-P01", "LEB", "LEB-P02")
check_world("SSA", "SSA-P01", "ILB", "ILB-P01")
check_world("NCA", "NCA-P01", "ESO", "ESO-P01")

# A longer journey requiring at least three transitions.
check_world("SSA", "SSA-P01", "VYS", "VYS-P01", minimum_teleports=3)
