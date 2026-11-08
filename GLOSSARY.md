# AI Chess Coach

A coach for online players rated 500 to 1600 that helps them turn a good opening into a won game by training the middlegame (move 5 onwards, in this product's sense) and tactics. This file holds the project's terms only; decisions are in `docs/decisions/`.

## Game phases

**Opening**:
Moves 1 to 4 of a game. It ends after Black's 4th move. This is the product's boundary (owner, 2026-11-08), not a chess-theory one: the detectors first look at move 5, and the product measures and trains from there. It replaces the earlier boundary of move 10.
_Avoid_: "book phase", "early game"

**Middlegame**:
In this product, the game from move 5 onwards, until the endgame. This includes moves 5 to 10, which chess theory often still calls the opening. This is the phase the product measures and trains.
_Avoid_: "midgame"

**Opening exit position**:
The position after Black's 4th move, the first position the product evaluates.
_Avoid_: "move-5 position", "start of middlegame position"

## Conversion

**Good opening**:
A checkpoint position where the engine rates the player at least +0.5 (half a pawn) better. A label for the position, not a claim about opening skill: an early lead is often the opponent's slip.

**Checkpoint position**:
The position after Black's 5th move, where a game is sorted into a zone (owner, 2026-11-08).
_Avoid_: "move-5 position"

**Zone**:
Where a game stands at the checkpoint position from the player's side: **ahead** (+0.5 or better), **behind** (-0.5 or worse) or **level** (between).
_Avoid_: "state", "phase" (phase means opening or middlegame)
_Avoid_: "winning position", "advantage position"

**Conversion game**:
A game in which the player had a good opening.
_Avoid_: "winning game" (it may be lost)

**Converted**:
A conversion game the player won.

**Squandered advantage**:
A conversion game the player drew or lost.
_Avoid_: "blown game", "throw"

**Conversion rate**:
Converted games out of conversion games, always shown with both numbers. The product's headline outcome.
_Avoid_: "win rate" (that counts every game)

**Turning point**:
The move in a squandered advantage after which the player's position was no longer clearly better.
_Avoid_: "blunder" (a turning point need not be a blunder)

**Conversion report**:
What a player sees for their last 20 rapid games: conversion rate, up to three squandered advantages with their turning points, and five drills.
_Avoid_: "analysis", "review" (Review is the older per-game screen)

## Training material

**Drill**:
One position with a question ("what is the safer or winning move here?") and an engine-verified answer.
_Avoid_: "puzzle" (reserved for the Lichess puzzle database), "exercise"

**Own drill**:
A drill built from a turning point in the player's own game.

**Public drill**:
A drill built from a public Lichess game.

**Generated drill**:
A drill built from a position that a Maia model played out from a real opening exit position, with Stockfish verifying the answer. Always labelled generated.
_Avoid_: "synthetic", "engine drill"

**Slip**:
A move of the player at move 5 or later that loses at least 150 cp for the player in a position that was not already decided, confirmed at the evidence engine config. A label for a move, not a claim about the player's skill.
_Avoid_: "blunder" (a different, stricter size), "mistake" (the detectors' word for hung and missed pieces)

**First-slip drill**:
A drill from the position just before the player's first slip in a game, asking for the engine-verified better move. It is either an own drill (the player's game) or a fresh drill (the same slip finder run over public games at the player's level).
_Avoid_: "mistake drill" (that covers any mistake, not the first)

**Round**:
Ten first-slip drills, five own and five fresh, about 15 minutes.
_Avoid_: "session" (reserved for the five-position Replay My Mistakes session)

**Forcing line**:
A sequence of the player's checks, captures and threats that wins material or forces replies, within three of the player's moves.
_Avoid_: "combination", "tactic" (too broad)

**Calculation drill**:
A drill from a position where the player had a forcing line and missed it; the player names candidate moves and writes the line before seeing the engine's.
_Avoid_: "puzzle"

**Drill set**:
A frozen list of drills. Rebuilding the drill bank does not change a set.

**Cycle**:
One pass over a drill set. Later cycles repeat the same drills in a new order.
_Avoid_: "session" (reserved for the planned five-position training session)

**Matched**:
An answer that is one of the engine-verified moves. Any other legal move is "not one of the checked moves", never "wrong".
_Avoid_: "correct"

## Play and evidence

**Play**:
A game with no help shown. It counts as real evidence.

**Practice**:
A game or drill with help available. Always marked assisted.

**Assisted**:
Any result produced with help shown. It never counts as evidence of skill.

**Convert-this-advantage game**:
A Practice game that starts from a good opening exit position and is played against Stockfish or Maia, at a chosen level and colour. It records whether the player converted.
_Avoid_: "scenario", "handicap game"

**Mistake types M1 and M2**:
M1 is hanging a piece of your own; M2 is missing a free piece the opponent left. M3 (missed threat) is off until it passes a hand-check.

**Hand-check**:
A person answers Yes / No / Can't tell on a sample of positions, with a pass gate set before looking.
