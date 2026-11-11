"""Opening counter (ADR 0022): which first moves players in a rating band actually play in each repertoire opening."""

import io

import pytest

from app.learner import openingtrie as T


def game(moves, white=1000, black=1000, event="Rated Rapid game", result="1-0"):
    text = " ".join(
        f"{i // 2 + 1}. {m} {{ [%clk 0:10:00] }}"
        if i % 2 == 0
        else f"{i // 2 + 1}... {m} {{ [%clk 0:10:00] }}"
        for i, m in enumerate(moves)
    )
    return f'[Event "{event}"]\n[WhiteElo "{white}"]\n[BlackElo "{black}"]\n[Result "{result}"]\n\n{text} {result}\n\n'


def test_san_moves_are_read_without_clock_comments_numbers_or_results():
    assert T.moves_of(
        "1. e4 { [%clk 0:10:00] } 1... c6 { [%clk 0:10:00] } 2. d4 d5 3. Nc3?! dxe4 1-0"
    ) == ["e4", "c6", "d4", "d5", "Nc3", "dxe4"]


def test_castling_promotion_and_check_marks_are_kept_in_the_move():
    assert T.moves_of("1. e4 e5 2. O-O O-O-O 3. e8=Q+ Qxh7# 0-1")[2:] == [
        "O-O",
        "O-O-O",
        "e8=Q+",
        "Qxh7#",
    ]


def test_only_as_many_moves_as_asked_for_are_returned():
    assert T.moves_of("1. e4 e5 2. Nf3 Nc6", max_plies=3) == ["e4", "e5", "Nf3"]


@pytest.mark.parametrize(
    "key,moves",
    [
        ("jobava", ["d4", "d5", "Nc3", "Nf6", "Bf4", "e6"]),
        ("jobava", ["d4", "Nf6", "Nc3", "d5", "Bf4", "c5"]),
        ("italian", ["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5"]),
        ("queens_gambit", ["d4", "d5", "c4", "e6"]),
        ("caro_kann", ["e4", "c6", "d4", "d5"]),
        ("kings_indian", ["d4", "Nf6", "c4", "g6", "Nc3", "Bg7", "e4", "d6"]),
    ],
)
def test_each_opening_recognises_its_own_move_orders(key, moves):
    assert T.OPENINGS[key].matches(moves)


@pytest.mark.parametrize(
    "key,moves",
    [
        ("jobava", ["d4", "d5", "c4", "e6"]),  # no Nc3 and Bf4
        ("italian", ["e4", "e5", "Nf3", "Nc6", "Bb5"]),  # Ruy Lopez
        ("queens_gambit", ["d4", "d5", "Nf3", "Nf6"]),
        ("caro_kann", ["e4", "e6"]),
        ("kings_indian", ["d4", "Nf6", "c4", "e6"]),
    ],
)
def test_a_different_opening_is_not_counted(key, moves):
    assert not T.OPENINGS[key].matches(moves)


def test_each_opening_names_the_side_the_player_has():
    assert [
        T.OPENINGS[k].side
        for k in ("jobava", "italian", "queens_gambit", "caro_kann", "kings_indian")
    ] == ["white", "white", "white", "black", "black"]


def test_counting_adds_every_prefix_of_each_matching_game():
    games = game(["e4", "c6", "d4", "d5"]) + game(["e4", "c6", "Nc3", "d5"])
    got = T.count(io.StringIO(games), low=600, high=1500, max_plies=4)
    caro = got["caro_kann"]
    assert caro.games == 2
    assert caro.nodes[("e4",)] == 2 and caro.nodes[("e4", "c6")] == 2
    assert caro.nodes[("e4", "c6", "d4")] == 1 and caro.nodes[("e4", "c6", "Nc3")] == 1


def test_a_game_outside_the_rating_band_or_not_rapid_is_skipped_and_counted():
    games = (
        game(["e4", "c6", "d4", "d5"], white=400)
        + game(["e4", "c6", "d4", "d5"], event="Rated Blitz game")
        + game(["e4", "c6", "d4", "d5"], black=2000)
    )
    got = T.count(io.StringIO(games), low=600, high=1500, max_plies=4)
    assert (
        got["caro_kann"].games == 0 and got["_stats"]["skipped"] == 3 and got["_stats"]["seen"] == 3
    )


def test_a_game_too_short_to_show_the_opening_is_skipped():
    got = T.count(io.StringIO(game(["e4", "c6"])), low=600, high=1500, max_plies=4, min_plies=8)
    assert got["_stats"]["skipped"] == 1


def test_a_game_with_unreadable_ratings_is_skipped_not_guessed():
    bad = (
        '[Event "Rated Rapid game"]\n[WhiteElo "?"]\n[BlackElo "1000"]\n\n1. e4 c6 2. d4 d5 1-0\n\n'
    )
    assert T.count(io.StringIO(bad), low=600, high=1500, max_plies=4)["_stats"]["skipped"] == 1


def test_the_saved_counts_keep_only_repeated_lines_and_say_where_they_came_from(tmp_path):
    games = game(["e4", "c6", "d4", "d5"]) * 3 + game(["e4", "c6", "Nc3", "d5"])
    got = T.count(io.StringIO(games), low=600, high=1500, max_plies=4)
    path = T.save(got, tmp_path, month="2026-09", low=600, high=1500, source="test")
    data = T.load(path)
    assert (
        data["version"] == T.VERSION and data["month"] == "2026-09" and data["band"] == [600, 1500]
    )
    caro = data["openings"]["caro_kann"]
    assert caro["games"] == 4
    assert ["e4 c6 d4 d5", 3] in caro["lines"] and all(n >= T.MIN_COUNT for _, n in caro["lines"])
