# missed_threat_v3

84 items for scoring `missed_threat` (M3, ADR 0011 and 0013) on **real games**: Lichess Rapid games, both players 600 to 1200 (CC0), one
position per game: 29 `missed`, 25 `met` (15 clean, 10 `other_loss`), 30 `not_applicable`. Rule: `LABEL_RULE.md` (with two amendments made
after the owner's check rounds). Built by `evals/tools/build_missed_threat_set_v3.py`, frozen by `freeze_missed_threat_v3.py`. Frozen: see
`FROZEN.md` (an exception: the owner-check gate was not met; the `uncertain` class is kept apart in `uncertain_unverified.jsonl`).

Checked by a person on 24 items per round (`check_round1.md`, `check_round2.md`); the rest rest on the engine labels. Static threats only
(a capture or mate the exchange count finds); the exchange count does not see pins. No detector had been run at the freeze.
Scored by `evals/tools/score_missed_threat.py --set missed_threat_v3`.
