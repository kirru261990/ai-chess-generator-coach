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

## Hand-check result on the owner's games, version 2 (2026-10-31): 27 of 30, the gate is met exactly

`handcheck_m3` version 2 (flags from `missed_threat` v3, ADR 0014; 15 games per time control, the newest older-than-the-window games, none of the 30 of
version 1; page wording as the eval-set checks: point values, the whole line shown, "green instead of red"). The owner answered all 30: **27 real,
3 not real** (gate 27). By time control: 10|0 12 of 15, 15|10 15 of 15. The three: one "no" on A (the owner saw no threat, 10|0, a capture); one "no"
on C (a fork the owner thought could not have been stopped, 10|0); one "can't tell" on C (10|0). Version 1 scored 14 of 30 on `missed_threat` v1.
**Caveats, stated before any use of the number:**
- It passes **exactly at the gate**, on 30 items, so the interval is wide (27 of 30 has a 95% Wilson interval of about 0.74 to 0.97).
- **Not fully independent:** the owner asked the assistant about several boards while answering, and the assistant explained the position and the
  question on three of them that were then answered as real (items 2 and 7) or not (item 4); the wording of A and C was also changed twice during the
  answering because the owner found them unclear (the answers already given were kept; the saved sample did not change). Without the two assisted
  real items the figure would be 25 of 28 (0.89), just under the same proportion.
- The owner's games are not in the repository (aggregate numbers only here); the sample, key, page and answers are in the git-ignored `data/evidence/`.
**Reading:** the detector's flags on the owner's real games are mostly real (at least 27 of 30 on this sample), which is a first, thin pass of ADR
0011 (d)'s second condition. It is not yet a clean one. Before M3 is shown as a weakness: repeat with a fresh sample from games the assistant has not
discussed (or have the owner answer without chat), then run the real-game rates report (TASKS M3e) and show it with its denominators and floors.

## Hand-check result on the owner's games, version 3 (2026-10-30): 23 of 30, the gate (27) is not met

`handcheck_m3` version 3: fresh sample (none of the games of versions 1 and 2), flags from `missed_threat` v3, and **answered by the owner without
asking the assistant**. Only 11 fresh flagged games existed at 900+10, so the 30 are 11 at 900+10 and 19 at 600 (the sampler tops a short time
control up from the other; the scan took `--target 19`). **Result: 23 real of 30.** 600: 17 of 19; 900+10: 6 of 11.
The seven not real: five "no" on C (m3c-01, 19, 21, 26, 30), one "can't tell" on C (28), one "no" on B (20).

**Why (engine check of the seven, 2026-10-30, depth 16):**
- m3c-21: the engine's best move does not stop the threat either (`Bc5+` still works, eval stays +377); the player's move was only worse against it. A fault: a `missed` needs a move that neutralises the threat.
- m3c-19: already lost (-508 before; the best move is -509 after). The threat is real, nothing saves the game.
- m3c-01, 26: only one or two defences hold, hard to find.
- m3c-28, 30: the defence is a counter-attack or a capture of the attacker (`exd5`, `c6`), not a block.
- m3c-20: after `e6` the capture `Bxf5` looks like an even trade; the loss comes from the opened e-file afterwards.

**Reading:** the version 2 pass (27 of 30) did not hold on a clean, fresh sample. M3 is **not** shown as a weakness (ADR 0011 (d)); the real-game
rates (TASKS M3e) stay blocked. Candidate v4 rules: the engine's best move must neutralise
the threat (its forced-threat loss below the threshold), and skip positions already lost. **The owner has said there will be no further
hand-check on their games and the detector is not to be run on them again**, so v4 can be tested only on the frozen Lichess sets and unit tests;
the seven positions above must not be used to claim an improvement (the rules were fitted to them).
