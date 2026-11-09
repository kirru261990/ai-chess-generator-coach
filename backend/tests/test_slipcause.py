"""Slip cause (ADR 0021): which detector, if any, confirms why a first slip lost. Detectors are injected; they have their own tests."""

import json
from types import SimpleNamespace as NS

import chess
import pytest

from app.learner import drillbank, slipcause

START = chess.Board().fen()
DRILL = {"id": "d1", "fen": START, "ply": 8, "played": "a2a3", "accepted": ["e2e4"]}


def det(outcome, version="1"):
    return lambda board, move, ply, analyser: NS(outcome=outcome, reason="r", evidence={})


def table(hang="no_mistake", threat="met", free="not_available", versions=("4", "4", "3")):
    return (("hanging_own", versions[0], det(hang), "mistake"), ("threat", versions[1], det(threat), "missed"),
            ("missed_free", versions[2], det(free), "missed"))


def test_the_first_confirming_detector_in_priority_order_gives_the_cause():
    assert slipcause.label(DRILL, None, table(hang="mistake", threat="missed", free="missed"))["cause"] == "hanging_own"
    assert slipcause.label(DRILL, None, table(threat="missed", free="missed"))["cause"] == "threat"
    got = slipcause.label(DRILL, None, table(free="missed"))
    assert got["cause"] == "missed_free" and got["detector"] == "missed_free" and got["version"] == "3"


def test_uncertain_or_silent_detectors_give_other_never_a_guess():
    got = slipcause.label(DRILL, None, table(hang="uncertain", threat="uncertain", free="uncertain"))
    assert got == {"cause": "other", "detector": None, "version": slipcause.SET_VERSION}
    assert slipcause.label(DRILL, None, table())["cause"] == "other"


@pytest.fixture
def causes(tmp_path, monkeypatch):
    monkeypatch.setattr(drillbank.config, "DATA_DIR", tmp_path)
    drillbank.bank_dir().mkdir(parents=True)


def test_labels_are_saved_by_drill_id_and_an_older_detector_version_is_not_served(causes):
    slipcause.save({"d1": {"cause": "hanging_own", "detector": "hanging_own", "version": "4"},
                    "d2": {"cause": "threat", "detector": "threat", "version": "3"}})  # threat is at v4 now
    got = slipcause.load()
    assert got["d1"]["cause"] == "hanging_own" and "d2" not in got


def test_each_cause_has_a_plain_sentence_and_a_habit_and_other_gives_no_reason():
    for c in ("hanging_own", "threat", "missed_free"):
        s = slipcause.explain_cause(c)
        assert s["sentence"] and s["habit"]
    other = slipcause.explain_cause("other")
    assert other["habit"] is None and "no reason" in other["sentence"]
    assert json.dumps(slipcause.explain_cause("nonsense")) == json.dumps(other)


def test_an_other_label_from_an_older_detector_set_is_not_served_either(causes):
    slipcause.save({"d1": {"cause": "other", "detector": None, "version": slipcause.SET_VERSION},
                    "d2": {"cause": "other", "detector": None, "version": "hanging_own@3+threat@4+missed_free@3"}})
    assert set(slipcause.load()) == {"d1"}  # d2 was judged "other" by a detector set that no longer exists, so it is relabelled
