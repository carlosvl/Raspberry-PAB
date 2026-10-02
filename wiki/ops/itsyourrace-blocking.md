---
title: ITS YOUR RACE blocks the scraper fingerprint
type: ops
sources:
  - src/raspberry_pab/race_results/client.py
  - tests/test_race_results_client.py
  - user (2026-10-02)
updated: 2026-10-02
---

# ITS YOUR RACE blocks the scraper fingerprint

`RaceResultsClient` fetches itsyourrace.com with `curl_cffi` browser impersonation, because plain clients get a Cloudflare 403 challenge. The impersonated browser version matters.

- **2026-10-02:** the Pi's live team standings went empty. Fetching `Results.aspx?id=17320` returned **HTTP 403 with `chrome131`** and **200 with `chrome124`** (about 90 KB), reproduced twice each with the app's own client on the Pi (curl_cffi 0.16.2). It had worked with `chrome131` a few hours earlier, so IYR/Cloudflare changed what it accepts.
- **Fix:** `DEFAULT_IMPERSONATE = "chrome124"` in `client.py`; `tests/test_race_results_client.py` pins the default.
- **If it breaks again:** the symptom is `HTTP 403 for https://www.itsyourrace.com/... (curl_cffi/<name>)` in the journal and an empty team strip (the board hides it with no buckets). Try another fingerprint from the same Python on the Pi before changing code.
- `mca_archive.py` still uses `chrome131` for a different host (the MCA archive); it was not changed.
