# Third-party software and data

This project is licensed **AGPL-3.0-or-later** (see `LICENSE`). Everything below is used under its own licence. Rule from
`docs/decisions/0001-open-source-reuse.md`: **before adding a dependency, check its licence and add a row here** (a test
enforces that every direct dependency is listed).

Why AGPL: the backend depends on python-chess (GPL-3.0-or-later), so the combined work must be GPL-compatible; AGPL-3.0 is
compatible with it and also covers people using a modified, hosted copy. Not legal advice.

Versions are the ones locked on 2026-10-07 (`backend/uv.lock`, `web/pnpm-lock.yaml`).

## Python, runtime (`backend/pyproject.toml` dependencies)

| Package | Version | Licence | URL | How it is used |
|---|---|---|---|---|
| python-chess (`chess`) | 1.11.2 | **GPL-3.0-or-later** | https://github.com/niklasf/python-chess | Rules, FEN/PGN, engine I/O. The reason the repo cannot be MIT |
| fastapi | 0.142.2 | MIT | https://github.com/fastapi/fastapi | Web API |
| uvicorn | 0.54.0 | BSD-3-Clause | https://uvicorn.dev/ | Runs the API |
| mcp | 2.3.0 | MIT | https://modelcontextprotocol.io | MCP server |
| httpx | 0.28.1 | BSD-3-Clause | https://github.com/encode/httpx | Chess.com sync client |
| python-dotenv | 1.2.4 | BSD-3-Clause | https://github.com/theskumar/python-dotenv | Reads `.env` |

Used through the above (not declared directly): pydantic 2.13.5 (MIT), starlette 1.7.0 (BSD-3-Clause).

## Python, development only (`dependency-groups.dev`)

| Package | Version | Licence | URL | How it is used |
|---|---|---|---|---|
| pytest | 9.1.1 | MIT | https://docs.pytest.org | Tests |
| ruff | 0.16.10 | MIT | https://docs.astral.sh/ruff | Lint |
| zstandard | 0.25.0 | BSD-3-Clause | https://github.com/indygreg/python-zstandard | Reads the Lichess puzzle file in the eval tooling |

## Web, runtime (`web/package.json` dependencies)

| Package | Version | Licence | URL | How it is used |
|---|---|---|---|---|
| react | 19.3.0 | MIT | https://react.dev | UI |
| react-dom | 19.3.0 | MIT | https://react.dev | UI |
| react-chessboard | 5.12.1 | MIT | https://github.com/Clariity/react-chessboard | The board |

## Web, development only (`devDependencies`)

| Package | Version | Licence | URL |
|---|---|---|---|
| vite | 8.3.2 | MIT | https://vite.dev |
| @vitejs/plugin-react | 6.1.1 | MIT | https://github.com/vitejs/vite-plugin-react |
| typescript | 6.0.3 | Apache-2.0 | https://www.typescriptlang.org |
| vitest | 5.0.3 | MIT | https://vitest.dev |
| oxlint | 1.86.0 | MIT | https://oxc.rs |
| @types/node | 24.19.1 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| @types/react | 19.3.0 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |
| @types/react-dom | 19.3.0 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |

## Not packages: programs and data

| Resource | Licence / terms | How it is used |
|---|---|---|
| Stockfish | GPL-3.0 | Run as a **separate program** over UCI (not linked, not distributed with this repository). If a Stockfish binary is ever shipped with the project, its source must be offered |
| Lichess puzzle database (`lichess_db_puzzle.csv.zst`) | CC0 | Eval positions for `real_play_v1`; the file stays in `data/` (git-ignored) and is not redistributed. Cite Lichess anyway |
| Chess.com public API | Chess.com's terms | Game sync, serial requests with a contact User-Agent; the owner's games stay in `data/` and are never committed |

## Checked on 2026-10-07

- All 47 Python packages installed in the backend environment were scanned: **python-chess is the only copyleft (GPL/AGPL) one**; every package declares a licence.
- Permissive licences (MIT, BSD, Apache-2.0) are compatible with AGPL-3.0. Licences were read from package metadata, not from a legal review.

## Before shipping a built web bundle
The Vite build bundles React and other MIT code. Before publishing a built bundle, make sure the licence notices of bundled
packages are included with it.

## Planned, not used yet (see ADR 0001)
Maia-2 (MIT), ChessBench (code Apache-2.0; data CC0 and CC-BY 4.0, which needs attribution here and in any report that uses it),
Lichess games database (CC0). Add rows when they are first used.
