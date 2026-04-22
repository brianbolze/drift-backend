# Parser vs DB comparison — hornady

Ran `hornady` parser over every cached page on `www.hornady.com` and joined by `source_url` to the current DB. DB is read-only — no inserts.

## Coverage

- Hornady URLs in fetched cache: **776**
- Parser extracted a result: **761**
- Parser declined: 15
- Matched DB row, all fields agree: **339**
- Matched DB row, at least one field differs: **0**
- URL not in DB (filtered by rejected-caliber list, failed to resolve, or not ingested): **422**
- Matched rows that are `is_locked=True` (curation-protected): 17

- Parser BC values already represented in DB (canonical or bullet_bc_source): **223**
- Parser BC values **not** in DB (new data the parser would add): **0**

## URLs not present in DB

### cartridge (276)
- `https://www.hornady.com/ammunition/handgun/10mm-auto-135-gr-monoflex-handgun-hunter`
- `https://www.hornady.com/ammunition/handgun/10mm-auto-150-gr-ftx-leverevolution`
- `https://www.hornady.com/ammunition/handgun/10mm-auto-155-gr-hp-xtp`
- `https://www.hornady.com/ammunition/handgun/10mm-auto-155-gr-xtp-american-gunner`
- `https://www.hornady.com/ammunition/handgun/10mm-auto-175-gr-flexlock-critical-duty`
- `https://www.hornady.com/ammunition/handgun/10mm-auto-180-gr-xtp`
- `https://www.hornady.com/ammunition/handgun/10mm-auto-200-gr-dgh-backcountry-defense`
- `https://www.hornady.com/ammunition/handgun/25-auto-35-gr-ftx-critical-defense`
- `https://www.hornady.com/ammunition/handgun/25-auto-35-gr-xtp`
- `https://www.hornady.com/ammunition/handgun/30-super-carry-100-gr-ftx-critical-defense`
- `https://www.hornady.com/ammunition/handgun/32-auto-60-gr-ftx-critical-defense`
- `https://www.hornady.com/ammunition/handgun/32-auto-60-gr-xtp`
- `https://www.hornady.com/ammunition/handgun/32-h-r-mag-80gr-ftx-critical-defense`
- `https://www.hornady.com/ammunition/handgun/327-federal-mag-80-gr-ftx-critical-defense`
- `https://www.hornady.com/ammunition/handgun/357-mag-125-gr-ftx-critical-defense`
- `https://www.hornady.com/ammunition/handgun/357-mag-125-gr-xtp-american-gunner`
- `https://www.hornady.com/ammunition/handgun/357-mag-130-gr-monoflex-handgun-hunter`
- `https://www.hornady.com/ammunition/handgun/357-mag-135-gr-critical-duty`
- `https://www.hornady.com/ammunition/handgun/357-mag-140-gr-ftx-leverevolution`
- `https://www.hornady.com/ammunition/handgun/357-mag-158-gr-xtp`
- … 256 more

### bullet (146)
- `https://www.hornady.com/bullets/handgun/10mm-.400-180-gr-fmj-fp`
- `https://www.hornady.com/bullets/handgun/10mm-.400-200-gr-dgh`
- `https://www.hornady.com/bullets/handgun/10mm-400-155-gr-xtp`
- `https://www.hornady.com/bullets/handgun/10mm-400-180-gr-hap-500`
- `https://www.hornady.com/bullets/handgun/10mm-400-180-gr-xtp`
- `https://www.hornady.com/bullets/handgun/10mm-400-200-gr-hap-1800`
- `https://www.hornady.com/bullets/handgun/10mm-400-200-gr-xtp`
- `https://www.hornady.com/bullets/handgun/30-cal-309-90-gr-xtp`
- `https://www.hornady.com/bullets/handgun/38-cal-357-125-gr-fp-xtp`
- `https://www.hornady.com/bullets/handgun/38-cal-357-140-gr-ftx-357-mag`
- `https://www.hornady.com/bullets/handgun/38-cal-357-158-gr-fp-xtp`
- `https://www.hornady.com/bullets/handgun/38-cal-358-158-gr-lrn`
- `https://www.hornady.com/bullets/handgun/38-cal-358-158-gr-swc-hp`
- `https://www.hornady.com/bullets/handgun/41-cal-410-210-gr-xtp`
- `https://www.hornady.com/bullets/handgun/44-cal-.430-240-gr-dgh`
- `https://www.hornady.com/bullets/handgun/44-cal-430-180-gr-xtp`
- `https://www.hornady.com/bullets/handgun/44-cal-430-200-gr-xtp`
- `https://www.hornady.com/bullets/handgun/44-cal-430-225-gr-ftx-44-mag`
- `https://www.hornady.com/bullets/handgun/44-cal-430-240-gr-xtp`
- `https://www.hornady.com/bullets/handgun/44-cal-430-300-gr-xtp`
- … 126 more
