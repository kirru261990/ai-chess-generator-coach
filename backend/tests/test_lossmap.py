"""Loss map: each synced game sorted into ahead / level / behind after Black's 5th move, with the results from each zone."""

from app.learner import lossmap


def game(gid, color="white", result="win"):
    return {"source_id": gid, "user_color": color, "user_result": result}


def analysis(gid, cp=None, mate=None, plies=38):
    """Depth-10 pass of one game. `cp` is from White's side, as the pass stores it."""
    positions = [{"ply": i, "cp": 0, "mate": None} for i in range(plies)]
    if plies > lossmap.ZONE_PLY:
        positions[lossmap.ZONE_PLY] = {"ply": lossmap.ZONE_PLY, "cp": cp, "mate": mate}
    return {"source_id": gid, "positions": positions}


def build(rows):
    games = [game(g, c, r) for g, c, r, _ in rows]
    analyses = [analysis(g, cp) for g, _, _, cp in rows]
    return lossmap.compute(games, analyses)


def zone(result, name):
    return next(z for z in result["zones"] if z["zone"] == name)


def test_a_lead_of_half_a_pawn_or_more_for_the_player_is_ahead_and_the_same_deficit_is_behind():
    assert lossmap.zone_of(60, None, "white") == "ahead"
    assert lossmap.zone_of(50, None, "white") == "ahead"
    assert lossmap.zone_of(49, None, "white") == "level"
    assert lossmap.zone_of(-50, None, "white") == "behind"


def test_the_score_is_from_the_players_side_so_black_flips_it():
    assert lossmap.zone_of(80, None, "black") == "behind"
    assert lossmap.zone_of(-80, None, "black") == "ahead"


def test_a_forced_mate_counts_as_ahead_or_behind():
    assert lossmap.zone_of(None, 3, "white") == "ahead"
    assert lossmap.zone_of(None, -2, "white") == "behind"
    assert lossmap.zone_of(None, 2, "black") == "behind"


def test_results_group_into_win_draw_and_loss():
    assert [
        lossmap.outcome(r)
        for r in (
            "win",
            "checkmated",
            "resigned",
            "timeout",
            "abandoned",
            "agreed",
            "stalemate",
            "repetition",
        )
    ] == ["win", "loss", "loss", "loss", "loss", "draw", "draw", "draw"]


def test_an_unknown_result_is_not_counted_rather_than_guessed():
    assert lossmap.outcome("something_new") is None


def test_counts_per_zone_carry_their_denominators():
    got = build(
        [
            ("a", "white", "win", 100),
            ("b", "white", "win", 100),
            ("c", "white", "resigned", 100),
            ("d", "white", "win", 0),
            ("e", "white", "resigned", 0),
            ("f", "white", "resigned", -100),
        ]
    )
    ahead = zone(got, "ahead")
    assert (ahead["games"], ahead["wins"], ahead["losses"]) == (3, 2, 1)
    assert zone(got, "level")["games"] == 2 and zone(got, "behind")["games"] == 1
    assert got["losses"] == 3 and got["sorted"] == 6


def test_the_share_of_losses_in_each_zone_uses_all_losses_as_the_denominator():
    got = build(
        [
            ("a", "white", "resigned", 100),
            ("b", "white", "resigned", 0),
            ("c", "white", "resigned", 0),
            ("d", "white", "resigned", -100),
        ]
    )
    assert zone(got, "level")["loss_share"] == {"of": 4, "n": 2}
    assert zone(got, "ahead")["loss_share"] == {"of": 4, "n": 1}


def test_a_game_shorter_than_the_checkpoint_is_left_out_and_counted():
    games = [game("a"), game("b")]
    got = lossmap.compute(games, [analysis("a", 100), analysis("b", plies=6)])
    assert got["sorted"] == 1 and got["left_out"]["too_short"] == 1


def test_a_game_with_no_analysis_is_left_out_and_counted():
    got = lossmap.compute([game("a"), game("b")], [analysis("a", 100)])
    assert got["left_out"]["not_analysed"] == 1 and got["sorted"] == 1


def test_a_game_whose_checkpoint_score_is_missing_is_left_out_not_sorted_as_level():
    got = lossmap.compute([game("a")], [analysis("a", cp=None, mate=None)])
    assert got["sorted"] == 0 and got["left_out"]["no_score"] == 1


def test_an_unknown_result_is_left_out_and_counted():
    got = lossmap.compute([game("a", result="weird")], [analysis("a", 100)])
    assert got["sorted"] == 0 and got["left_out"]["unknown_result"] == 1


def test_a_zone_with_too_few_games_is_marked_so_no_rate_is_read_from_it():
    got = build([("a", "white", "win", 100), ("b", "white", "resigned", 100)])
    assert zone(got, "ahead")["enough"] is False
    many = build(
        [(f"g{i}", "white", "win" if i % 2 else "resigned", 100) for i in range(lossmap.MIN_GAMES)]
    )
    assert zone(many, "ahead")["enough"] is True


def test_the_result_names_its_version_and_rules_so_a_later_change_is_a_new_measurement():
    got = build([("a", "white", "win", 100)])
    assert got["version"] == lossmap.VERSION and got["zone_ply"] == 10 and got["threshold_cp"] == 50
