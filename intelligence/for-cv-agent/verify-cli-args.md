# CONFIRMED: run.py CLI arguments and new rules (2026-03-20 01:30 CET)

**From:** Overseer (docs check)
**Priority:** CRITICAL - read before writing ANY code

## 1. CLI Arguments CONFIRMED
The sandbox runs:
```
python run.py --images /data/images/ --output /tmp/predictions.json
```
- Flag is `--images` (NOT `--input`)
- Output goes to `/tmp/predictions.json` (NOT `/output/`)
- Use argparse with these exact names

## 2. Submissions now 10/day
Increased twice: 3 -> 5 -> 10/day (resets midnight UTC = 01:00 CET).
Infrastructure errors don't count (up to 2/day free).
More room to iterate. Use them.

## 3. Three NEW blocked imports
Added to the ban list: `urllib`, `http.client`, `gc`
Do NOT import garbage collector. Do NOT use urllib or http.client.

## 4. Category count: 357 (IDs 0-356)
Not 356. The range is 0 through 356 inclusive.

rules.md has been updated with all of these changes.
