# 0022. Opening repertoire: lines from public games, checked by the engine, drilled in Practice

Status: accepted (owner, 2026-11-11: "lets build the opening repertoire"). The grilling step was skipped at the owner's request, so the decisions below are mine and open to change.

## Context

The owner wants to learn five openings thoroughly: Jobava London, Italian and Queen's Gambit with White; Caro-Kann and King's Indian with Black. Lines should run into the middlegame, each with the principles that matter, and be practised as drills. `docs/` source notes (the "Public Sources for Opening Principles" page) found that public data covers lines and middlegame drills fully but that no free source covers opening principles in depth, and that books and courses are copyrighted.

## Decisions

1. **Lines come from public games.** Lichess rated Rapid games (CC0), both players in a band (default 700 to 1500), streamed from the start of the September 2026 file and counted, never stored. A game belongs to an opening by a fixed gate on its first moves (`openingtrie.OPENINGS`; changing a gate is a new `VERSION`). Only counts of move prefixes are kept. The 3,000 games already on the Mac were too thin (19 King's Indian games), so the owner approved reading about 300 MB.
2. **Our moves are the most played, then engine-checked; their replies are what players really play.** For our side take the most played move at each position. For the opponent keep every reply with at least 6% of the games at that position, while the line still holds at least 0.3% of all the opening's games and at least 5 games, to 20 plies (move 10). The first floors tried (8% and 1%) gave only 7 to 12 lines per opening, ending at move 4 to 5; these give 14 to 31 lines, still ending at moves 4 to 8 for most because players at this level leave the book early. Each of our moves is then checked with the pinned depth-18 evidence engine: a move more than 50 cp worse than the best is replaced by the best among the played moves or the line stops there (rule 2).
3. **Drills are Practice.** Playing a line is assisted, never evidence, and does not feed the study rates (rule 4, ADR 0005). Misses are kept in a separate ledger so missed lines return sooner. Nothing here changes Play.
4. **No copyrighted text and no share-alike text.** Principles and notes are written in our own words and verified (rule 2); Wikipedia and Wikibooks text is not copied, because share-alike does not fit the AGPL repo. Books and courses are learned from and cited, not reproduced (Tier 3 in the sources page). Principles are a later slice.
5. **The first-slip study is not the place to measure this.** It was designed to measure one new training (`docs/personal-study-v1.md`). The repertoire is a second intervention, so it is logged separately and the study's decision rule does not read it.

## ## Result of the first build

From 925,802 Lichess games (September 2026, band 700 to 1500) the five openings have 1,508 (Jobava), 4,787 (Italian), 1,934 (Queen's Gambit), 2,985 (Caro-Kann) and 585 (King's Indian) games. Lines reach 5 to 15 plies. Data alone will not reach move 10; going further needs engine-led continuations, labelled as such, and is not built.

## Not decided here

How "all lines" ends beyond move 10; plan notes and principles per line; middlegame puzzles per opening (Lichess puzzle file, opening tags); other languages. Each is its own slice.

## Reversal

Delete `app/learner/openingtrie.py` and `data/repertoire/`; nothing else reads them until the line builder and drills land.
