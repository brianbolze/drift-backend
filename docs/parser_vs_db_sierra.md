# Parser vs DB comparison — sierra

Ran `sierra` parser over every cached page on `sierrabullets.com` and joined by `source_url` to the current DB. DB is read-only — no inserts.

## Coverage

- Manufacturer (DB): `Sierra Bullets`
- URLs in fetched cache: **248**
- Parser extracted a result: **245**
- Parser declined: 3
- Matched DB row, all fields agree: **127**
- Matched DB row, at least one field differs: **14**
- URL not in DB (filtered by rejected-caliber list, failed to resolve, or not ingested): **104**
- Matched rows that are `is_locked=True` (curation-protected): 2

- Parser BC values already represented in DB (canonical or bullet_bc_source): **228**
- Parser BC values **not** in DB (new data the parser would add): **0**

## Discrepancies by field

| Field | Count |
|---|---:|
| `sku` | 14 |

## Diffs (first 30)

### `https://sierrabullets.com/22-cal-77-gr-hpbt-matchking-smk-cannelure` _bullet_
- sku: parser='9377' db='9377GT'

### `https://sierrabullets.com/22-cal-80-gr-hpbt-cn-matchking-smk` _bullet_
- sku: parser='9390' db='9390T'

### `https://sierrabullets.com/22-cal-90-gr-hpbt-cn-matchking-smk` _bullet_
- sku: parser='9290' db='9290T'

### `https://sierrabullets.com/270-cal-140-gr-tipped-gameking-tgk` _bullet_
- sku: parser='4440' db='4440T'

### `https://sierrabullets.com/30-cal-165-gr-tipped-gameking-tgk` _bullet_
- sku: parser='4665' db='4665T'

### `https://sierrabullets.com/30-cal-180-gr-tipped-gameking-tgk-optimized-for-30-06` _bullet_
- sku: parser='4681' db='4681T'

### `https://sierrabullets.com/30-cal-210-gr-hpbt-cn-matchking-smk` _bullet_
- sku: parser='9240' db='9240T'

### `https://sierrabullets.com/30-cal-210-gr-tipped-gameking-tgk` _bullet_
- sku: parser='4610' db='4610GT'

### `https://sierrabullets.com/338-cal-300-gr-hpbt-matchking-smk/` _bullet_
- sku: parser='9300' db='9300T'

### `https://sierrabullets.com/375-cal-350-gr-hpbt-cn-matchking-smk` _bullet_
- sku: parser='9350' db='9350T'

### `https://sierrabullets.com/6-5mm-100-gr-hpbt-matchking-smk` _bullet_
- sku: parser='1711' db='1711C'

### `https://sierrabullets.com/6mm-100-gr-tipped-gameking-tgk` _bullet_
- sku: parser='4110' db='4110T'

### `https://sierrabullets.com/6mm-90-gr-tipped-gameking-tgk` _bullet_
- sku: parser='4100' db='4100T'

### `https://sierrabullets.com/7mm-165-gr-tipped-gameking-tgk` _bullet_
- sku: parser='4565' db='4565T'

## URLs not present in DB

### bullet (104)
- `https://sierrabullets.com/10mm-150-gr-jhp-sports-master`
- `https://sierrabullets.com/10mm-165-gr-jhp-sig-v-crown`
- `https://sierrabullets.com/10mm-165-gr-jhp-sports-master`
- `https://sierrabullets.com/10mm-180-gr-jhp-sports-master`
- `https://sierrabullets.com/20-cal-36-gr-tipped-varmintking-tvk`
- `https://sierrabullets.com/22-cal-45-gr-hornet-varmintking-vk`
- `https://sierrabullets.com/22-cal-52-gr-hpbt-matchking-smk`
- `https://sierrabullets.com/22-cal-55-gr-sbt-gameking-sgk`
- `https://sierrabullets.com/22-cal-55-gr-spt-varmintking-vk`
- `https://sierrabullets.com/22-cal-69-gr-tipped-varmintking-tvk`
- `https://sierrabullets.com/22-cal-77-gr-hpbt-matchking-smk`
- `https://sierrabullets.com/22-cal-77-gr-hpbt-matchking-x-mkx-ktzx`
- `https://sierrabullets.com/223-cal-45-gr-hornet-varmintking-svk`
- `https://sierrabullets.com/25-cal-90-gr-tipped-varmintking-tvk`
- `https://sierrabullets.com/270-cal-135-gr-hpbt-matchking-x-mkx`
- `https://sierrabullets.com/270-cal-140-gr-hpbt-gameking-sgk`
- `https://sierrabullets.com/270-cal-140-gr-sbt-gameking-sgk`
- `https://sierrabullets.com/30-cal-125-gr-spt-pro-hunter`
- `https://sierrabullets.com/30-cal-125-gr-tipped-matchking-tmk`
- `https://sierrabullets.com/30-cal-150-gr-fmjbt-gameking-sgk`
- … 84 more
