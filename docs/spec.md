# AI Chess Coach — Product Specification

**Version:** 0.4 · **Date:** 5 October 2026 · **Owner:** Karthik Raman · **Status:** Draft for build; supersedes v0.2 and v0.3

---

## 00. What changed and why

| # | Change | Reason |
|---|---|---|
| C1 | **Purpose reset:** personal chess improvement + AI-builder portfolio. Revenue later. | Stated goal. Market novelty is no longer the bar; depth of build and proof of results are. |
| C2 | **User zero is the builder** (Chess.com, rated under 1000), then 5–10 invited players | Fastest feedback loop; an honest n=1 case study is a strong portfolio asset. |
| C3 | **Four non-negotiable pillars:** Play, Analysis, Pattern recognition, Coaching | Stated requirement. Play returns to V1 (it was moved to V1.1 in v0.3). |
| C4 | **Surface: web app + MCP server** (ChatGPT/Claude as secondary clients) | Full control of board UX; the MCP layer shows the multi-surface capability. |
| C5 | **Differentiation is redefined as "proof"**: grounded coaching with published accuracy, and measured change in real games | Research showed the blind-spot map (Chess.com Insights) and intent-first coaching (Chessalyz) already exist. What isn't published anywhere is verified accuracy plus a before/after result. |
| C6 | GTM and pricing replaced by a **Portfolio & sharing plan** and a **Later monetisation** note | Revenue isn't a V1 goal. |

All grounding, verification, eval and honesty rules from v0.2/v0.3 still apply unless changed below.

---

## 01. Purpose and thesis

**Purpose (in order):**
1. Help me (and a few others under 1200) stop losing games to the same tactical misses.
2. Build a portfolio-grade AI system: a tool-using coach agent, rigorous evals, a multi-surface MCP backend, and a measured learning outcome.
3. Keep a credible path to monetisation once results exist.

**Thesis:** A coach that is *provably correct* about the board and *provably useful* in the player's real games is more credible than one that is just fluent. Every claim the coach makes is checked against the engine and rule-based detectors, and every progress claim comes with a denominator.

**Problem statement:**
Players under about 1200 keep losing games to the same tactical misses, mostly hanging pieces and missed threats, because they don't check the board consistently before moving.
Engine reviews and AI coaches flag wrong moves, but rarely show the recurring pattern, are sometimes confidently wrong (one study found 22% incorrect claims from a frontier LLM without tools), and never show whether training changed anything.
This product plays, analyses, finds the learner's recurring misses, coaches them with verified explanations, and measures whether those misses fall in the learner's next real games.

## 02. Users

| User | Description | What V1 must do for them |
|---|---|---|
| **U0 — Builder (me)** | Chess.com, rated under 1000, rapid/blitz | Sync my games, play practice games, show my patterns, coach me, track my real-game miss rate monthly |
| **U1 — Invited friends (3–4, from early Nov)** | Friends rated 300–1200, Chess.com or Lichess | Same loop with a simple sign-in; data isolated per user |
| **Later** | Public users | Out of scope until the U0/U1 results justify it |

**First training scope, in order:** (1) hanging my own pieces, (2) missing opponent's hanging pieces, (3) missing opponent threats, (4) simple forks. The order follows what most often decides games under 1000; I'll confirm it with my own baseline data.

## 03. The four pillars

### Pillar A — Play

| ID | Requirement | Acceptance criteria |
|---|---|---|
| A1 | Play a full game in the web app | Colour choice; legal moves only; promotion, check, mate, stalemate, draws, resign; PGN export. |
| A2 | Opponent strength | V1: Stockfish with a limited skill level (labelled "Level n", not Elo). Increment: **Maia-2** (MIT licence) as a human-like opponent set near my rating, if its lowest supported rating band works for under 1000. |
| A3 | Play modes | **Play** (no hints, counts as real evidence) and **Practice** (hints, scan prompts, takebacks, feedback; always marked assisted). Switching mid-game marks the game assisted permanently. Takebacks are unlimited and all assistance is Practice-only (ADR 0005). |
| A4 | Start from my critical positions | Practice can start from any position in my analysed games, so I can replay my mistakes. |
| A5 | Time control (optional) | Simple clock for Play mode so the habits trained resemble real rapid games. |

### Pillar B — Analysis

| ID | Requirement | Acceptance criteria |
|---|---|---|
| B1 | Game sources | (a) games played in the app; (b) **Chess.com sync by username** through the public API (no login; requests made one at a time); (c) Lichess sync; (d) PGN import. Deduplicate across sources. |
| B2 | Engine analysis | Stockfish with a recorded version and budget; scores normalised to the learner's perspective; mate scores handled separately; unstable evaluations flagged as uncertain. |
| B3 | Post-game review | Up to three key moments per game, chosen from my active patterns first and then by size of mistake. Each has the move played, acceptable alternatives, consequence, and one takeaway. |
| B4 | Board explorer | Navigate the game, try branches without changing the main line, arrows for explanations. |
| B5 | Batch analysis | Analyse my last 50–100 Chess.com games in the background: a fast pass over every position, deep analysis only on flagged positions. Show progress. |

### Pillar C — Pattern recognition

| ID | Requirement | Acceptance criteria |
|---|---|---|
| C1 | Motif detectors | Deterministic, versioned detectors for the four scope motifs. Each runs on **every** position where I'm to move, recording `opportunity → taken / missed / not applicable / uncertain`. Material outcome confirmed by the engine. |
| C2 | Blind-spot map | Up to three patterns, each shown as **missed / available**, with a rate per 100 moves, recency window, confidence label (tentative / established) and linked examples. |
| C3 | Thresholds | Tentative at ≥3 misses across ≥2 games; established at ≥8 opportunities. Uncertain positions are excluded from both numerator and denominator. Thresholds are configurable product rules, not statistical guarantees. |
| C4 | Context tags | Tag each miss with game phase, time left on the clock (when the PGN has it), and piece type, so patterns like "hangs pieces with under 2 minutes left" can surface. |
| C5 | Challenge | I can dispute a pattern; disputes are logged and reviewed against the detector. |

### Pillar D — Coaching

| ID | Requirement | Acceptance criteria |
|---|---|---|
| D1 | Ask "why?" | On any position or branch: short explanation plus an optional verified line. Every tactical claim is checked before it's shown. |
| D2 | Intent first (skippable) | At key moments, ask "What were you considering?", then compare my answer with the verified threats and name the specific gap. My answer is stored as self-reported, never inferred. |
| D3 | Training sessions | Five positions per session: two from my games, two curated on the same motif, one held-out test. Equivalent good moves are accepted. |
| D4 | Hint ladder | Stage 0 scan prompt ("Checks, captures, threats?") → concept cue → piece/square → consequence → answer on request. Assistance is recorded. |
| D5 | Fading scan prompts | In Practice games, scan prompts appear with a probability that drops as my **real-game** miss rate for the active pattern improves. |
| D6 | Coach plan | One focus at a time, explained with my examples; I can change it. |
| D7 | Monthly progress | Compare a baseline window with the latest window of real Chess.com 10|0 and 15|10 games (per time control and combined, with game mix): missed/available per motif, rate per 100 moves, sample size, and an "early signal" label below the minimum sample. No rating-gain claims. |

## 04. Principles

| ID | Principle |
|---|---|
| P1 | The backend owns chess state; the LLM never decides legality. |
| P2 | No tactical claim without a check (engine line or detector). |
| P3 | Errors are rates with denominators, never bare counts. |
| P4 | Practice is not assessment; assisted results are always labelled. |
| P5 | Admit uncertainty; abstain rather than guess. |
| P6 | One focus at a time; the player can override. |
| P7 | Real games are the scoreboard; drills are leading indicators. |

## 05. Architecture

```
Web app (board, chat, dashboards)        ChatGPT / Claude (via MCP)
            │                                      │
            └──────────── API / MCP server ────────┘
                               │
                         Coach agent harness
             (intent → tools → draft → verify → respond)
       ┌──────────┬──────────┬───────────┬───────────┬──────────┐
   Chess core  Engine svc  Motif       Learner     Sync svc   Coach LLM
   (rules,     (Stockfish, detectors   service     (Chess.com, (explain,
   state,      Maia later) (versioned) (evidence,  Lichess,    question,
   PGN/FEN)                            patterns,   PGN)        summarise)
                                       progress)
```

| Component | Owns | Must not own |
|---|---|---|
| Chess core | Rules, state, branches, PGN/FEN | Coaching text |
| Engine service | Evaluations, lines, opponent moves | Teaching claims |
| Motif detectors | Opportunity detection, uncertainty flags | Explanations |
| Learner service | Evidence, patterns, attempts, progress windows, fading state | Ratings or mastery claims |
| Sync service | Fetching public games, dedupe, source IDs | Credentials |
| Coach agent harness | Intent routing, tool calls, budgets, verification, one repair attempt | Changing state without checks |
| Coach LLM | Explanations, questions, summaries from supplied evidence | Legality, counts, invented lines |
| MCP server | Same tools exposed to ChatGPT/Claude | Its own game state |

**Agent loop (H1):** classify intent → fetch exact state → call permitted tools → draft an answer linked to evidence → **verify** (legality, line consistency, claim check, hint leakage) → return. If verification fails, one repair attempt; then return only verified facts with an uncertainty note.

**Model routing (H2):** One coach model plus a baseline. Add a cheaper model for classification only if evals show no quality loss.

**Suggested stack (open to change):** TypeScript web app with an existing board library; Python backend with `python-chess`; Stockfish binary; Maia-2 later; Postgres; one coach model via API; an MCP server over the same tool layer.

## 06. Tools (shared by web app and MCP)

`sync_games`, `import_pgn`, `start_game`, `make_move`, `get_game`, `create_branch`, `analyse_position`, `review_game`, `get_blind_spot_map`, `submit_intent`, `start_training_session`, `submit_training_attempt`, `get_progress`.

**Contracts (from v0.2):** ownership check, expected revision and idempotency key on state-changing calls; structured evidence IDs plus a separate display payload; explicit error codes; everything versioned (prompts, models, engine settings, detector rules, drill bank, eval sets); export and delete; PGN comments treated as untrusted data.

## 07. Evaluation (showcase centrepiece)

| ID | Eval | Target |
|---|---|---|
| E1 | Rules and state | Zero illegal transitions, duplicate moves, cross-user access, or assisted results labelled unassisted |
| E2 | **Grounded vs raw coaching** | Break explanations into atomic claims and check each against the engine and detectors (ACT-Eval style). Compare three configurations: raw LLM, tool-grounded, grounded + verifier. Target ≥98% correct checkable claims for grounded + verifier; publish all three numbers. |
| E3 | Detector accuracy | Per motif, on ~50 labelled positions each: precision ≥90%, recall ≥80%; uncertain rate reported. A motif that fails is hidden from the map. |
| E4 | Intent comparison | ≥90% of "gap" statements name a threat actually on the board; zero claims about intent the player didn't state. |
| E5 | Hint leakage | <5% of early-stage hints reveal the answer. |
| E6 | Operations | p95 engine reply ≤2s; first coaching response ≤8s; cost per review and per training session tracked. |
| E7 | **Competitor benchmark (qualitative)** | Run 10 of my games through Chess.com Game Review/Insights and Chessalyz; blind-compare explanation correctness and usefulness against this coach. |

Freeze each eval set before tuning; report denominators and failure categories.

## 08. Measurement — personal case study

- **Baseline:** my last 100 Chess.com rapid games (10|0 and 15|10) before training starts (frozen, published).
- **Primary metric:** missed/available per motif and rate per 100 moves, in real Chess.com 10|0 and 15|10 games — shown per time control and combined, with the game mix for each window.
- **Leading indicators:** held-out drill success, delayed retest after 7 days, scan-prompt fading level.
- **Cadence:** monthly windows of at least 30 games.
- **Honesty:** n=1 is a case study, not proof. Report confounders (games played, time control changes, other study). For invited players, report each person's result separately; no pooled claims under 10 players.

## 09. Delivery plan

**Capacity:** 1–2 hours a day. **First usable version:** 12 October 2026 (for me only).

### Week 1 — core loop for U0

| Day | Focus | Output |
|---|---|---|
| 1 | Foundations | Repo, stack, board in the web app, chess core with legal moves; MCP skeleton exposing `get_game`. |
| 2 | Play | Play vs Stockfish (levels, colour, resign, PGN export); Play/Practice flag. |
| 3 | Sync + analysis | Chess.com sync for my username; Stockfish batch pass; post-game review for one game. |
| 4 | Detector 1 | "Hanging my own piece" and "missed free piece" detectors with 50 labelled positions each; first precision/recall numbers. |
| 5 | Blind-spot map + baseline | Map over my last 100 games; baseline frozen. |
| 6 | Coaching | Grounded "why?" with verifier; intent-first question on review moments. |
| 7 | Evals + write-up | E1, E2 (raw vs grounded), E3 first run; short README and a demo clip. |

**Day-1 checkpoint:** if the board plus legal-move core takes more than ~3 hours, cut the clock (A5) and Lichess (B1c) from the first fortnight.

### Weeks 2–4 (me only)

- **Week 2:** Training sessions and hint ladder; threat detector; E2 eval report published.
- **Week 3:** Fork detector; fading scan prompts; MCP tools usable from Claude and ChatGPT.
- **Week 4:** Sign-in and per-user data isolation; Lichess sync; first monthly progress report; readiness check for friends.

### Early November — invited friends (3–4)

Start once I'm satisfied with the loop. Each friend gets their own baseline; results are reported per person.

### Month 2+

Maia-2 opponent; competitor benchmark (E7); public eval report; first case-study write-up.

**Deferred:** opening repertoire, multiplayer, public ratings, coach personalities, live help during real games (never), payments.

## 10. Portfolio and sharing plan

| Asset | When |
|---|---|
| Public GitHub repo with architecture, tool contracts and reproducible evals | Week 1 onwards (visibility to decide) |
| Eval report: raw vs grounded vs verified coaching, detector precision/recall | End of week 2 |
| Demo video: play → sync → map → coach → practice | End of week 1, refreshed monthly |
| Case study: "My hanging-piece rate over 90 days" with denominators and confounders | Month 3 |
| Write-ups (blog/LinkedIn): building a grounded chess agent; what evals caught | Monthly |

Claims must distinguish shipped capability, offline eval results, my personal outcome, and anything causal. Actual numbers only.

## 11. Later monetisation (not in scope now)

The research suggests features alone won't support pricing: Chess.com Diamond (Insights), Chessalyz ($4.99–25/month), Aimchess and free tools like Blunder Tutor already cover sync, patterns and drills. A paid version would need **evidence of improvement** — the case study and invited-player results — as its main selling point. Revisit after month 3 with real data.

## 12. Budget

₹10,000/month cap kept. With one to ten users, the main costs are coach-model calls and batch analysis. Track cost per review and per session from day one.

## 13. Decisions (agreed 5 Oct 2026)

1. **Repo:** Public from day 1, labelled work-in-progress. No secrets or player data in the repo (`.env` and a data folder git-ignored from the first commit). Commit history counts as build evidence.
2. **Models:** Coach = a current Claude Sonnet-class model via the Anthropic API. Eval-only baseline = a current GPT model with no tools, so E2 can be compared with the published ACT-Eval figure (22% incorrect claims for GPT-5.4 without tools). A small model for intent classification only if evals show no quality loss.
3. **Case-study time controls:** Chess.com rapid **10|0** and **15|10**, fixed for 90 days. Report each separately and combined; show the game mix per window, because 15|10 gives more thinking time and usually fewer misses, so a shift in mix alone can move the combined rate.
4. **Invited players:** 3–4 friends start about 3–4 weeks after the first usable version (around early November 2026), once I'm satisfied with the loop. Sign-in and data isolation are built in weeks 3–4.

## Appendix — Research basis (5 Oct 2026)

- Hanging pieces and missed threats are the most-cited problem under ~1200 in Chess.com forum threads and improvement blogs.
- Chess.com Game Review AI explanations are criticised as vague or wrong; LLM chess commentary had 22% incorrect claims without tools (ACT-Eval, Aug 2026).
- Chess.com Insights (Diamond) shows found vs missed forks/pins/mates and hanging pieces; Chessalyz asks what you were thinking and syncs Chess.com/Lichess; Aimchess, Chessiro, Blunder Tutor and BlackBox find patterns and build drills from your games.
- No tool found that publishes the accuracy of its coaching or measures before/after miss rates for a trained pattern in real games.
- Chess.com public API: no authentication; monthly PGN archives; serial requests not rate-limited. Maia-2: MIT licence.
