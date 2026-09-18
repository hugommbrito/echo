import pytest

from apps.leveling.probes import plan_slots, probe_count, probe_positions


@pytest.mark.parametrize(
    "n, count",
    [(0, 0), (1, 0), (2, 0), (3, 1), (4, 1), (5, 1), (7, 1), (8, 2), (10, 2), (12, 2), (13, 3)],
)
def test_probe_count(n, count):
    assert probe_count(n) == count


def test_probe_positions_are_spread_and_unique():
    positions = probe_positions(10, 2)
    assert positions == [2, 7]
    assert probe_positions(5, 1) == [2]
    assert probe_positions(3, 1) == [1]


def test_plan_slots_round_robin_and_probes(global_categories):
    cats = [
        global_categories["job-interview"],
        global_categories["shopping"],
        global_categories["travel"],
    ]
    slots = plan_slots(10, cats, "B1")
    assert [s.number for s in slots] == list(range(1, 11))
    assert [s.category.slug for s in slots[:4]] == [
        "job-interview",
        "shopping",
        "travel",
        "job-interview",
    ]
    probes = [(s.number, s.level, s.probe) for s in slots if s.probe != "none"]
    assert probes == [(3, "B2", "above"), (8, "A2", "below")]
    assert all(s.level == "B1" for s in slots if s.probe == "none")


def test_plan_slots_at_scale_edges(global_categories):
    cats = [global_categories["travel"]]
    top = plan_slots(5, cats, "C2")
    assert [(s.level, s.probe) for s in top if s.probe != "none"] == [("C1", "below")]
    bottom = plan_slots(5, cats, "A1")
    assert [(s.level, s.probe) for s in bottom if s.probe != "none"] == [("A2", "above")]


def test_no_probes_for_small_batches(global_categories):
    slots = plan_slots(2, [global_categories["travel"]], "B1")
    assert all(s.probe == "none" and s.level == "B1" for s in slots)
    assert plan_slots(0, [global_categories["travel"]], "B1") == []
