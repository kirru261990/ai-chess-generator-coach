# Prompt for the second reviewer (paste this to GPT, then attach or paste `handcheck_second.md`)

You are the second human-style reviewer for a chess eval set. Please answer a hand-check sheet **from the boards only**.

**Rules (important for the result to mean anything):**
1. Use only the sheet I give you (`handcheck_second.md`). **Do not open or read `positions.jsonl`, `LABEL_RULE.md`,
   `provenance.json` or any file in `evals/` other than the sheet.** They contain the proposed answers. Do not browse the
   repository for them.
2. Do not run any code from this repository (no detectors, no builder script).
3. You may use any chess tool of your own (for example python-chess or Stockfish) to check a position. **Tell me which
   tools you used and for which items**, so I can report tool-assisted answers separately.
4. If you cannot tell, write `can't tell`. That is allowed.

**What the questions mean.** Each item has three questions, answered yes / no / can't tell.
- Only a capture available on the **very next move** counts. A check, fork or skewer that wins material a move later does
  not count.
- "Win material" means winning at least two pawns' worth by capturing a knight, bishop, rook or queen after the opponent's
  best recapture. A rook for a bishop counts. An even trade does not. Pawns do not count.
- The first kind of item ("Before this move, could the side to move win material…"): answer A, B and C.
- The second kind ("After this move, can the opponent win…"): answer A, then B only if A is yes, or C only if A is no.

**Reply format**, one line per item, nothing else on the line:
```
rp1-201: A yes, B no, C no
rp1-099: A no, B -, C yes
```
Use `-` for a question that does not apply.

Afterwards, add a short note listing any item whose question seemed ambiguous or whose position looked illegal.
