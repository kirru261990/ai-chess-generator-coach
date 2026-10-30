# 0013 — M3 `missed_threat` v2: the threat must explain the loss

Status: detector built 2026-10-30 (PR pending); eval set and hand-check not done. Decided by: Claude (all decisions below; the owner may change them). Builds on ADR 0011 ("Hand-check
result" and "Next"). Nothing in `missed_threat` v1, the frozen M3 window or the 30 judged positions changes.

## Problem

v1 scored 14 of 30 real on the hand-check (gate 27). ADR 0011 traced 16 not-real flags: 6 are a detector defect, 7 were right and the
page wording failed, 3 are open. The defect: v1 calls a move `missed` when it loses at least 150 cp **and** the threat line still wins
after it. It never checks that the loss **comes from** the threat. A move can lose a bishop to something else while an unrelated
threat also happens to stand.

## v2 rule: forced-threat loss (FTL)

After the player's move M, if the threat move T is legal, play T and let the evidence engine search the result:

    FTL = eval_before − eval(position after M, T, then best play)      (player's point of view, evidence depth)

If T is not legal after M, the threat is stopped (v1 already handles this) and FTL is not computed.

`missed` needs, in addition to v1's checks (loss ≥ `M3_EVAL_LOSS_CP` at both depths; threat still works):

    FTL ≥ M3_EVAL_LOSS_CP   and   FTL ≥ loss / 2

The second term means the threat explains most of the move's loss. Several winning replies for the opponent are fine: T is forced
by the rule, not required to be the engine's best reply.

When the loss is large and the threat still works but FTL fails, the outcome is **`uncertain`, reason `loss_not_from_threat`**,
excluded from both sides of the rate (AGENTS rule 5). It is not `met`: the player did not meet the threat, and we cannot say the
miss cost anything.

Why `uncertain` and not `met`: counting these as `met` would lower the rate for moves that did ignore a real threat but also made
a bigger blunder elsewhere (hc3-29: executing the threat backfires on the opponent, yet the owner judged the flag real). Abstaining
is the conservative choice; the owner may move them to `met` later (reverse: one line in `detect`).

## Cases the tests must cover (written before the code)

1. The six defect cases (hc3-02, 03, 08, 11, 15, 26): FTL ≤ 0 → `loss_not_from_threat`, never `missed`.
2. A threat that costs and is ignored (hc3-20, 21, 28 pattern: FTL ≈ loss) → `missed`.
3. Several winning replies for the opponent, T not the engine's best → still `missed` if FTL holds.
4. hc3-29 pattern (FTL negative, owner said real) → `uncertain`, documented as a known disagreement.
5. T illegal after M → `met` (`defended`), no FTL call.
6. Discovered-attack pattern (hc3-27) → `missed`.

Positions are taken from FENs in the repo's hand-check data; they guide tests, they are **not** a scoring set.

## Version, eval and hand-check

- `missed_threat.VERSION` → `"2"`; `M3_` constants are copied into each record as before. v2 adds `ftl` and `ftl_config_id` to
  the record. The 30 positions already judged are **not** re-scored.
- **Eval:** a new frozen set `missed_threat_v3` of real-game positions (not puzzles; v2 puzzles were too clean), built by
  `evals/tools/` without importing the detector, labels fixed before running v2. Report precision and recall with denominators.
- **Hand-check wording (decided in ADR 0011 "Next" (b)):** A "if you had skipped, what could they do next?", B "does your move stop
  that, or answer it with something bigger?", C "could another legal move have avoided or answered it?". **Real = A yes, B yes
  (still there), C yes**; the mapping is frozen before the new sample is judged. "Did you see it?" is collected as information only.
- **New sample:** 30 flags (15 per time control, one per game) from older games neither in the M3 window nor in the first sample
  (about 350 remain). Gate **27 of 30**.
- **No M3 rate is reported as a weakness** until both the eval and the new hand-check pass (ADR 0011 (d); TASKS M3e stays blocked).

## Built (2026-10-30)

`missed_threat.VERSION` = "2"; `M3_FTL_MIN_SHARE` = 0.5 in `prd_rules.py` (copied into `m3_thresholds`). The check runs last, only for moves
that would otherwise be `missed`, so it adds one engine search per missed candidate and none for the other outcomes. A forced
threat that ends the game (mate) is scored without a search. Tests: `tests/test_detector_missed_threat.py` (cases 1 to 6 above as
scripted-engine rules, plus the boundaries at half the loss and at 150 cp). Not yet run on real positions.

## Private regression run (2026-10-30)

`evals/tools/m3_regression_private.py` builds `data/evidence/missed_threat_v3_private/` (git-ignored: the owner's games) from the first
hand-check: 26 labelled items (20 `missed`, 6 `not_missed`; hc3-05, 20, 21, 28 left out as undecided), labels fixed in the script from
the owner's answers and ADR 0011 before v2 was run. v2 result: all 6 defect cases abstain (`loss_not_from_threat`); 19 of 20 `missed`
stay `missed`; the one that abstains is hc3-29, the known disagreement (case 4). **This is a regression check, not a score:** the
rule was derived from these positions (ADR 0011 forbids scoring a retuned detector on them). The real test is the new hand-check
sample. The public frozen set from Lichess rapid games is still to build and needs the owner's OK for the download.

## Not in this step

No change to M1 or M2 (`RULES_VERSION` stays 1), the rates pass, or the web app.

## Reversal

Set `missed_threat.VERSION` back to `"1"` and remove the FTL block in `detect`. v1 records stay readable; retire v2 rows with
`evidence_run retire`.
