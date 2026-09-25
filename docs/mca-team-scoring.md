# MCA team results (local scoring script)

Offline laptop tool: scrape an [ITS YOUR RACE](https://www.itsyourrace.com/) series page, score every team with **2026 MCA Chapter 11** + **Appendix A**, and write a markdown standings report. This is **not** part of the Pi kiosk Admin Race Results sync (that path matches individual athletes).

## Prerequisites

```bash
make install-dev   # needs curl_cffi + beautifulsoup4
```

## Run

From the repo root:

```bash
PYTHONPATH=src python scripts/mca-team-results.py \
  --url 'https://www.itsyourrace.com/results.aspx?id=17320' \
  --team Roseville \
  --out docs/mca-team-results.md
```

| Flag | Default | Meaning |
|------|---------|---------|
| `--url` | series `id=17320` | IYR series results URL |
| `--team` | `Roseville` | Team to bold / detail (case-insensitive) |
| `--out` | `docs/mca-team-results.md` | Markdown report path |

Re-run after more categories post; Cloudflare may 403 occasionally — wait and retry.

## What it scores

- Appendix A place → points (Varsity / JV3 / base columns; bonuses already in the grid)
- HS Division I: top 8, max 6 per gender
- HS Division II and Middle School: top 4, max 3 per gender
- Team D1/D2 inferred from split fields (`… D1` / `… D2`); combined-only teams use D2 caps and are marked †
- Team penalties are not on IYR pages and are not applied

## Code map

| Piece | Path |
|-------|------|
| CLI | [`scripts/mca-team-results.py`](../scripts/mca-team-results.py) |
| Fetch all categories | [`src/raspberry_pab/race_results/series_fetch.py`](../src/raspberry_pab/race_results/series_fetch.py) |
| Scoring | [`src/raspberry_pab/race_results/mca_scoring.py`](../src/raspberry_pab/race_results/mca_scoring.py) |
| HTTP client | [`src/raspberry_pab/race_results/client.py`](../src/raspberry_pab/race_results/client.py) |
| Tests | [`tests/test_mca_scoring.py`](../tests/test_mca_scoring.py) |

## Live on the kiosk

Admin → **Race Results** → **Live team standings** enables background polling of the series URL. The kiosk shows a bottom ticker (focus team place + top 3). Every interval (default 5 minutes) the matrix runs SCROLLONCE with a short place message (rotating buckets). Matrix updates skip while reminder alerts are busy.

## Checklist

1. `make install-dev`
2. Run the command above (quote the URL in zsh)
3. Open [`mca-team-results.md`](mca-team-results.md) for standings + focus-team detail
4. Re-run when skipped categories later get results
5. On the Pi: enable Live team standings in Admin and confirm the kiosk ticker
