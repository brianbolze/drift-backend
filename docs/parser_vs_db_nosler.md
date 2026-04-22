# Parser vs DB comparison — nosler

Ran `nosler` parser over every cached page on `www.nosler.com` and joined by `source_url` to the current DB. DB is read-only — no inserts.

## Coverage

- Manufacturer (DB): `Nosler`
- URLs in fetched cache: **455**
- Parser extracted a result: **422**
- Parser declined: 33
- Matched DB row, all fields agree: **228**
- Matched DB row, at least one field differs: **3**
- URL not in DB (filtered by rejected-caliber list, failed to resolve, or not ingested): **191**
- Matched rows that are `is_locked=True` (curation-protected): 0

- Parser BC values already represented in DB (canonical or bullet_bc_source): **136**
- Parser BC values **not** in DB (new data the parser would add): **0**

## Discrepancies by field

| Field | Count |
|---|---:|
| `weight` | 2 |
| `bc_g1` | 1 |

## Diffs (first 30)

### `https://www.nosler.com/270-wsm-130gr-expansion-tip-ammunition.html` _cartridge_
- bc_g1: parser=15.0 db=0.459

### `https://www.nosler.com/416-caliber-400gr-solid-25ct.html` _bullet_
- weight: parser=416.0 db=400.0

### `https://www.nosler.com/458-caliber-500gr-solid-25ct.html` _bullet_
- weight: parser=458.0 db=500.0

## URLs not present in DB

### bullet (75)
- `https://www.nosler.com/10mm-135gr-jhp-asp-250ct.html`
- `https://www.nosler.com/10mm-150gr-jhp-asp-250ct.html`
- `https://www.nosler.com/10mm-180gr-jhp-asp-250ct.html`
- `https://www.nosler.com/10mm-200gr-jhp-asp-250ct.html`
- `https://www.nosler.com/17-caliber-20gr-fbhp-varmageddon-100ct.html`
- `https://www.nosler.com/20-caliber-40gr-ballistic-tip-varmint-100ct.html`
- `https://www.nosler.com/204-caliber-32gr-ballistic-tip-varmint-100ct.html`
- `https://www.nosler.com/22-caliber-35gr-tipped-varmageddon-100ct.html`
- `https://www.nosler.com/22-caliber-40gr-ballistic-tip-varmint-100ct.html`
- `https://www.nosler.com/22-caliber-50gr-ballistic-tip-lead-free-100ct.html`
- `https://www.nosler.com/22-caliber-53gr-fb-tipped-varmageddon-bullet-100ct.html`
- `https://www.nosler.com/22-caliber-60gr-ballistic-tip-varmint-100ct.html`
- `https://www.nosler.com/22-caliber-77gr-hpbt-custom-competition-100ct.html`
- `https://www.nosler.com/25-caliber-100gr-ballistic-tip-hunting-50ct.html`
- `https://www.nosler.com/25-caliber-100gr-partition-50ct.html`
- `https://www.nosler.com/25-caliber-115gr-ballistic-silvertip-50ct.html`
- `https://www.nosler.com/25-caliber-115gr-partition-50ct.html`
- `https://www.nosler.com/270-caliber-130gr-accubond-50ct.html`
- `https://www.nosler.com/270-caliber-130gr-ballistic-tip-hunting-50ct.html`
- `https://www.nosler.com/270-caliber-130gr-partition-50ct.html`
- … 55 more

### cartridge (116)
- `https://www.nosler.com/17-rem-fireball-20gr-tipped-varmageddon-ammunition.html`
- `https://www.nosler.com/17-remington-20gr-fbhp-varmageddon-ammunition.html`
- `https://www.nosler.com/17-remington-20gr-tipped-varmageddon-ammunition.html`
- `https://www.nosler.com/22-250-remington-55gr-ballistic-tip-varmint-ammunition.html`
- `https://www.nosler.com/22-nosler-55gr-ballistic-tip-varmint-ammunition.html`
- `https://www.nosler.com/22-nosler-70gr-accubond-trophy-grade-ammunition.html`
- `https://www.nosler.com/221-rem-fireball-40gr-fb-tipped-varmageddon-ammunition.html`
- `https://www.nosler.com/222-remington-50gr-ballistic-tip-varmint-noslercustom-ammunition.html`
- `https://www.nosler.com/223-rem-53gr-fb-tipped-varmageddon-ammunition.html`
- `https://www.nosler.com/223-remington-55gr-expansion-tip-ammunition.html`
- `https://www.nosler.com/243-winchester-90gr-ballistic-tip-hunting-ammunition.html`
- `https://www.nosler.com/243-winchester-90gr-expansion-tip-ammunition.html`
- `https://www.nosler.com/25-06-rem-100gr-partition-trophy-grade-ammunition.html`
- `https://www.nosler.com/25-06-remington-100gr-expansion-tip-ammunition.html`
- `https://www.nosler.com/257-rob-p-110gr-accubond-trophy-grade-ammunition.html`
- `https://www.nosler.com/257-roberts-p-100gr-ballistic-tip-noslercustom-ammunition.html`
- `https://www.nosler.com/257-roberts-p-100gr-partition-noslercustom-ammunition.html`
- `https://www.nosler.com/257-roberts-p-115gr-ballistic-tip-noslercustom-ammunition.html`
- `https://www.nosler.com/26-nosler-140gr-accubond-trophy-grade-ammunition.html`
- `https://www.nosler.com/260-rem-120gr-ballistic-tip-hunting-ammunition.html`
- … 96 more
