---
name: AI Chess Coach
description: A patient, encouraging chess coach where the board leads and every colour carries meaning.
colors:
  action-green: "#3caa5a"
  ink: "#08060d"
  slate-text: "#6b6375"
  paper: "#ffffff"
  hairline: "#e5e4e7"
  parchment: "#f4f3ec"
  night: "#16171d"
  night-surface: "#1f2028"
  night-hairline: "#2e303a"
  night-text: "#9ca3af"
  night-ink: "#f3f4f6"
  hint-gold: "#e0b030"
  hint-cream: "#fff3c4"
  hint-ink: "#3a2e00"
  verdict-best: "#3a9d5d"
  verdict-good: "#7fae52"
  verdict-book: "#a1744f"
  verdict-slip: "#d8b13a"
  verdict-mistake: "#e58f2a"
  verdict-blunder: "#ca3431"
  error-red: "#c0392b"
  right-green: "#2a7a40"
  wrong-red: "#b03a2e"
  threat-red: "#d9534f"
  established-bg: "#d6f0dc"
  established-ink: "#1c5a2a"
  tentative-bg: "#f5e6b8"
  tentative-ink: "#6b4e00"
  board-dark: "#403d39"
  board-light: "#f0f0f0"
  answer-blue: "rgba(80, 140, 230, 0.85)"
  select-yellow: "rgba(255, 215, 0, 0.55)"
typography:
  display:
    fontFamily: "system-ui, 'Segoe UI', Roboto, sans-serif"
    fontSize: "56px"
    fontWeight: 500
    lineHeight: 1.45
    letterSpacing: "-1.68px"
  headline:
    fontFamily: "system-ui, 'Segoe UI', Roboto, sans-serif"
    fontSize: "24px"
    fontWeight: 500
    lineHeight: 1.18
    letterSpacing: "-0.24px"
  title:
    fontFamily: "system-ui, 'Segoe UI', Roboto, sans-serif"
    fontSize: "1em"
    fontWeight: 600
  body:
    fontFamily: "system-ui, 'Segoe UI', Roboto, sans-serif"
    fontSize: "18px"
    fontWeight: 400
    lineHeight: 1.45
    letterSpacing: "0.18px"
  label:
    fontFamily: "system-ui, 'Segoe UI', Roboto, sans-serif"
    fontSize: "0.75em"
    fontWeight: 400
  notation:
    fontFamily: "ui-monospace, Consolas, monospace"
    fontWeight: 700
rounded:
  xs: "4px"
  sm: "6px"
  md: "8px"
  lg: "10px"
  pill: "14px"
spacing:
  xxs: "4px"
  xs: "6px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "20px"
components:
  button-primary:
    backgroundColor: "{colors.action-green}"
    textColor: "{colors.paper}"
    rounded: "{rounded.md}"
    padding: "8px 14px"
  button-toggle-on:
    backgroundColor: "{colors.hint-cream}"
    textColor: "{colors.board-dark}"
    rounded: "{rounded.sm}"
  card:
    backgroundColor: "{colors.paper}"
    rounded: "{rounded.md}"
    padding: "12px 14px"
  hint-card:
    backgroundColor: "{colors.paper}"
    rounded: "{rounded.lg}"
    padding: "10px 12px"
  chip:
    backgroundColor: "{colors.parchment}"
    textColor: "{colors.slate-text}"
    typography: "{typography.label}"
    rounded: "{rounded.lg}"
    padding: "2px 8px"
  chip-established:
    backgroundColor: "{colors.established-bg}"
    textColor: "{colors.established-ink}"
    rounded: "{rounded.lg}"
    padding: "2px 8px"
  chip-tentative:
    backgroundColor: "{colors.tentative-bg}"
    textColor: "{colors.tentative-ink}"
    rounded: "{rounded.lg}"
    padding: "2px 8px"
  move-badge-best:
    backgroundColor: "{colors.verdict-best}"
    textColor: "{colors.paper}"
    size: "22px"
  move-badge-blunder:
    backgroundColor: "{colors.verdict-blunder}"
    textColor: "{colors.paper}"
    size: "22px"
  eval-bar:
    backgroundColor: "{colors.board-dark}"
    rounded: "{rounded.xs}"
    width: "22px"
---

# Design System: AI Chess Coach

## Overview

**Creative North Star: "The Patient Coach"**

The coach sits beside the player, not above them. The board is the largest thing on every screen, and everything else waits beside it: the verdict, the threat warning, the hint ladder, the coach's explanation. Nothing shouts. When the player gets something wrong, the screen says so plainly, with the cost and the reason, and then offers the next step. When the player gets something right, the screen is warm about it: a green badge, a short "right" line, and on a real checkmate, confetti.

The surfaces are quiet so the colour can mean something. White paper, hairline borders and slate text carry the structure. Colour appears where it explains a chess fact: the verdict of a move, a piece in danger, a free piece missed, the next hint. The mood is warm and encouraging without becoming a game show. Celebration is earned and brief; it never replaces the explanation.

Density is medium. One task per screen, the board on the left, the things you act on in a column beside it, so the player never scrolls away from the position to read feedback.

**Key Characteristics:**
- The board leads; supporting panels sit beside it, not below it.
- Flat paper surfaces with hairline borders; no shadow-based depth.
- Colour is reserved for meaning: verdicts, danger, help and action.
- One action accent: Action Green.
- Warm, brief celebration for real success; honest, specific feedback for mistakes.
- System fonts throughout; monospace only for move notation.

## Colors

A calm paper-and-ink base with a fixed chess-verdict palette and a single green action accent.

### Primary
- **Action Green** (#3caa5a): the one accent. The primary button ("Submit", "Next"), the "good" feedback stripe and success states. It also replaces the leftover template purple on the active tab underline (see Do's and Don'ts).

### Secondary
- **Hint Gold** (#e0b030) with **Hint Cream** (#fff3c4) and **Hint Ink** (#3a2e00): everything that is help. The active hint toggle, the completed and next steps of the hint stepper, a pressed "Why?" button. Gold means "the coach is helping you now".

### Tertiary
- **Answer Blue** (rgba(80, 140, 230, 0.85)): the player's own answer in tests and practice: the arrow of the move they chose, the square they tapped. Blue means "this is what you said", kept apart from the verdict colours that judge it.

### Neutral
- **Ink** (#08060d): headings and card headlines.
- **Slate Text** (#6b6375): body text, notes, legends.
- **Paper** (#ffffff): page and card background.
- **Hairline** (#e5e4e7): every border, the dashed divider above "Why?".
- **Parchment** (#f4f3ec): neutral chips and inline code.
- **Night set** for dark mode: **Night** (#16171d) page, **Night Surface** (#1f2028), **Night Hairline** (#2e303a), **Night Text** (#9ca3af), **Night Ink** (#f3f4f6).
- **Board Dark** (#403d39) and **Board Light** (#f0f0f0): the two halves of the evaluation bar.

### Verdict palette (fixed)
- **Best** (#3a9d5d) ★, **Good** (#7fae52) 👍, **Book** (#a1744f) 📖, **Slip** (#d8b13a) ?!, **Mistake** (#e58f2a) ?, **Blunder** (#ca3431) ??. Used on the move badge on the board and as the left stripe of the feedback card.

### Status colours
- **Right Green** (#2a7a40) and **Wrong Red** (#b03a2e): the "what was right" and "what was wrong" lines in feedback text.
- **Threat Red** (#d9534f): the border of the "Watch out" threat box, over an 8% red wash.
- **Error Red** (#c0392b): app errors and the budget-stopped usage line.
- **Established** (#d6f0dc on #1c5a2a) and **Tentative** (#f5e6b8 on #6b4e00): confidence chips on Blind spots cards.

### Board overlays
- **Select Yellow** (rgba(255, 215, 0, 0.55)): the selected square; a lighter yellow (rgba(255, 230, 0, 0.3)) marks the last move.
- **Danger and opportunity marks**: red (rgba(220, 60, 50, 0.6)) on your piece that can be taken; green (rgba(60, 170, 90, 0.6)) on a free piece you missed. The legend under the board uses the same two swatches.

### Named Rules
**The Fixed Verdict Rule.** The six verdict colours follow the chess convention players already know and never change. They mean a move verdict and nothing else: never reuse them for buttons, charts or decoration.

**The One Accent Rule.** Action Green is the only accent. Purple, blue or any new hue never becomes a second "brand" colour.

**The Gold Means Help Rule.** Gold and cream mark the coach's help. If a screen shows gold, the player is being assisted.

## Typography

**Display Font:** system-ui (with 'Segoe UI', Roboto, sans-serif)
**Body Font:** system-ui (with 'Segoe UI', Roboto, sans-serif)
**Label/Mono Font:** ui-monospace (with Consolas, monospace), for move notation only

**Character:** The native system face keeps the app feeling like a calm tool on the player's own device; weight, not a display font, carries the hierarchy.

### Hierarchy
- **Display** (500, 56px, -1.68px tracking; 36px below 1024px): page titles only.
- **Headline** (500, 24px, 1.18 line height; 20px below 1024px): section heads.
- **Title** (600, 1em, Ink): card headlines and hint-card heads.
- **Body** (400, 18px / 1.45, 0.18px tracking; 16px below 1024px): all running text. Feedback and notes step down to 0.9em.
- **Label** (400, 0.75em to 0.8em): chips, legends, the usage line, stepper steps.
- **Notation** (700, monospace): move names (SAN) in the move lanes.

### Named Rules
**The Notation Rule.** Monospace is for chess moves only. Prose, numbers and labels stay in the system face.

## Layout

Practice and Play use a two-column grid: the board column (up to 560px) on the left and a side column (at least 260px) on the right, 20px apart, inside a 1000px container. Below 860px the grid collapses to one column at 560px, board first. Supporting pages (Blind spots, Progress) use a 900px column with a card grid of auto-fit 300px columns and 16px gaps. Review boards shrink to 360px.

Spacing steps are 4, 6, 8, 12, 16 and 20px. Panels in the side column stack with 10px gaps. In the chat's full-screen board view, the board grows to the available height (min(92vw, 100vh − 150px)).

**The Board Beside Rule.** Anything the player must read to act on the current position (verdict, threats, hints, Why?) sits in the side column next to the board, never below the fold.

## Elevation & Depth

The system is flat. Depth comes from hairline borders, tonal washes and the left stripe of a feedback card, not from shadows. The only shadow is the small lift under move badges on the board (0 1px 3px rgba(0,0,0,0.5)), so they read above the pieces. The checkmate banner is an overlay band (72% black, or 88% green on a win), not a raised card.

**The Flat Paper Rule.** Cards and panels never get drop shadows. Use a hairline border or a tonal wash instead.

## Shapes

Corners are gently rounded and stay small. 4px for small marks (eval bar, code, legend swatches), 6px for compact controls (hint button, lane rows), 8px for cards, feedback and the primary button, 10px for the hint card and chips, 14px for stepper pills, and full circles for move badges and lane numbers. Borders are 1px hairlines; the feedback card uses a 6px left border as its verdict stripe.

## Components

### Buttons
- **Shape:** gently rounded (8px).
- **Primary:** Action Green fill, white text, weight 600, 8px × 14px padding, no border. Disabled at 50% opacity.
- **Toggle on (hint, Why?):** Hint Cream fill with a Hint Gold border and Board Dark text.
- **Default:** the browser button, used for secondary actions (Undo, Resign, navigation).

### Chips
- **Style:** pill (10px), label size, Parchment fill by default.
- **State:** Established (green) and Tentative (amber) show how sure a Blind-spot finding is.

### Cards / Containers
- **Corner Style:** 8px (cards), 10px (hint card).
- **Background:** Paper.
- **Shadow Strategy:** none (see The Flat Paper Rule).
- **Border:** 1px Hairline.
- **Internal Padding:** 12px × 14px (cards), 10px × 12px (hint card).

### Navigation
- **Tabs:** a centred row of buttons with 8px gaps. The active tab is bold with a 2px underline.

### Feedback card (signature)
A bordered card with a 6px left stripe in the verdict colour: Good, Slip, Mistake or Blunder. Inside, "right" lines in Right Green and "wrong" lines in Wrong Red, then a dashed divider and the coach's Why? explanation.

### Threat box (signature)
"Watch out": a Threat Red 1px border over an 8% red wash, 8px radius. It names what the opponent threatens next.

### Move badge (signature)
A 22px circle at the top-right corner of the moved piece's square, filled with the verdict colour, white symbol, 1.5px white ring and the system's only shadow.

### Evaluation bar (signature)
A 22px-wide vertical bar beside the board, Board Light over Board Dark, with the height animating in 0.4s. The score label sits on the winning side's end. Shown only in Practice.

### Hint stepper
Three pill steps. Pending steps sit at 60% opacity; the next step gets a Hint Gold border; done steps fill with Hint Cream.

## Do's and Don'ts

### Do:
- **Do** use Action Green (#3caa5a) as the only accent, including for the active tab underline.
- **Do** keep the six verdict colours exactly as listed, and only for move verdicts.
- **Do** keep help visuals (eval bar, move badges, red and green board marks, threat box, hint gold) in Practice only. Play and tests show none of them.
- **Do** put feedback, threats and hints in the side column beside the board.
- **Do** celebrate real success briefly (badge, a "right" line, confetti on a player's checkmate) and always pair it with the explanation.
- **Do** respect reduced motion: confetti is hidden when the player asks for less motion.

### Don't:
- **Don't** use the template purple (#aa3bff, and its dark-mode #c084fc). It is a Vite starter leftover in `web/src/index.css`; migrate the tab underline to Action Green.
- **Don't** add drop shadows to cards or panels.
- **Don't** use a verdict colour for anything other than a verdict.
- **Don't** use gold or cream for anything except the coach's help.
- **Don't** use monospace for anything except move notation.
