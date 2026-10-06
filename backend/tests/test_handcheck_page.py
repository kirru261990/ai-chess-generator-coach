import importlib.util
import json
import re
from pathlib import Path

SET = Path(__file__).resolve().parents[2] / "evals" / "sets" / "real_play_v1"
TOOL = Path(__file__).resolve().parents[2] / "evals" / "tools" / "make_handcheck_page.py"


def page():
    return (SET / "handcheck_owner.html").read_text()


def test_the_owner_page_shows_the_same_30_items_as_the_sheet_and_never_a_label():
    ids = re.findall(r"^## (rp1-\d+)", (SET / "handcheck_owner.md").read_text(), re.MULTILINE)
    text = page()
    assert len(ids) == 30 and all(f'id="{i}"' in text for i in ids)
    assert text.count("<svg") == 30
    for leak in ("not_applicable", "uncertain", "constructed", "adversarial", "real_blunder", "real_safe",
                 "real_taken", "material_label", '"label"'):
        assert leak not in text


def test_each_item_asks_at_most_two_plain_questions():
    text = page()
    assert text.count('<div class="q" data-qid="A">') == 30
    assert text.count('<div class="q" data-qid="B">') == 19  # only the missed_free items have a second question
    assert "can't tell" in text.lower() or "can&#x27;t tell" in text.lower()


def test_plain_move_wording_needs_no_notation():
    spec = importlib.util.spec_from_file_location("mk", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    import chess

    board = chess.Board("4k3/8/8/3n4/8/8/8/3RK3 w - - 0 1")
    assert mod.plain_move(board, chess.Move.from_uci("d1d5")) == "White's rook takes the knight on d5."
    assert mod.plain_move(board, chess.Move.from_uci("e1f1")) == "White's king moves to f1."
    rows = [json.loads(line) for line in (SET / "positions.jsonl").read_text().splitlines()]
    assert rows  # the page is built from the same file


def test_every_owner_item_can_be_checked_with_the_simple_questions():
    # The owner page omits the mate/forced-win question, so no owner item may depend on it, and the
    # answers must map to the item's material_label (see LABEL_RULE.md section 9).
    ids = re.findall(r"^## (rp1-\d+)", (SET / "handcheck_owner.md").read_text(), re.M)
    rows = {r["id"]: r for r in map(json.loads, (SET / "positions.jsonl").read_text().splitlines())}
    for i in ids:
        r = rows[i]
        assert r["material_label"] in {"taken", "missed", "not_applicable"}, (i, r["material_label"])
        assert r["category"] != "adversarial"
