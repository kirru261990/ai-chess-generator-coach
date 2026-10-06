import importlib.util
from pathlib import Path

TOOL = Path(__file__).resolve().parents[2] / "evals" / "tools" / "compare_handcheck.py"


def mod():
    spec = importlib.util.spec_from_file_location("compare_handcheck", TOOL)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_parse_reads_the_pages_copy_format_including_dashes():
    out = mod().parse("rp1-201: A yes, B no\nrp1-156: A no\nrp1-154: A no, B -\nnot a line\n")
    assert out == {"rp1-201": {"A": "yes", "B": "no"}, "rp1-156": {"A": "no"}, "rp1-154": {"A": "no", "B": "-"}}


def test_answers_map_to_labels_as_the_rule_says():
    implied = mod().implied
    assert implied("missed_free", {"A": "no"}) == "not_applicable"
    assert implied("missed_free", {"A": "no", "B": "-"}) == "not_applicable"
    assert implied("missed_free", {"A": "yes", "B": "yes"}) == "taken"
    assert implied("missed_free", {"A": "yes", "B": "no"}) == "missed"
    assert implied("hanging_own", {"A": "yes"}) == "missed"
    assert implied("hanging_own", {"A": "no"}) == "taken"


def test_cant_tell_is_not_decided_and_not_counted_as_agreement():
    m = mod()
    assert m.implied("missed_free", {"A": "can't tell"}) is None
    assert m.implied("missed_free", {"A": "yes"}) is None  # B missing
    rows = {"x": {"detector": "hanging_own", "category": "real_safe", "material_label": "taken"}}
    assert m.compare({"x": {"A": "can't tell"}}, rows)[0]["agree"] is None


def test_the_recorded_owner_result_is_reproducible_from_the_saved_answers():
    m = mod()
    import json

    rows = {r["id"]: r for r in map(json.loads, (TOOL.parents[1] / "sets" / "real_play_v1" / "positions.jsonl").read_text().splitlines())}
    results = m.compare(m.parse((TOOL.parents[1] / "sets" / "real_play_v1" / "handchecks" / "owner_answers.txt").read_text()), rows)
    assert len(results) == 30 and sum(r["agree"] for r in results) == 25
    assert {r["category"] for r in results if not r["agree"]} == {"constructed_miss"}
