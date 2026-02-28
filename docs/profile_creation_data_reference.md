# Profile Creation — Data Reference for Design

*How the data library supports profile creation UX, what we can infer from each user choice, and what each flow approach requires.*

*Last updated: February 24, 2026*

---

## 1. Data Library at a Glance

The data library is a curated database of firearms, ammunition, and optics specifications. It ships bundled with the app as a read-only SQLite database. Users never interact with it directly — it powers search, auto-fill, and smart defaults during profile creation.

### What We Have Today

| Entity | What It Represents | Rows | Status |
|---|---|---|---|
| **Caliber** | A cartridge designation (e.g., "6.5 Creedmoor", ".308 Winchester") | 25 | Ready — hand-curated, comprehensive for target audience |
| **Chamber** | What a gun barrel is machined for (usually 1:1 with caliber, but not always) | 26 | Ready — includes special cases like .223 Wylde |
| **Chamber ↔ Caliber links** | Which ammo is safe to fire in which chamber | 30 | Ready — captures directional compatibility |
| **Manufacturer** | Companies that make bullets, ammo, rifles, optics | 32 | Ready — covers all major brands for our audience |
| **Bullet** | A specific projectile (e.g., "Hornady 140gr ELD Match") — the core ballistic unit | 15 | Prototype seed — 6.5 CM and .308 only. Target: 150-200 |
| **Cartridge** | A factory-loaded round (e.g., "Hornady 6.5 CM 140gr ELD Match #81500") | 15 | Prototype seed — 6.5 CM and .308 only. Target: 200-300 |
| **Rifle Model** | A factory rifle configuration (e.g., "Bergara B-14 HMR in 6.5 CM, 22\" barrel") | 15 | Prototype seed — 4 calibers. Target: TBD |
| **Optic** | A riflescope SKU (e.g., "Vortex Viper PST Gen II 5-25x50 MRAD") | 16 | Prototype seed — major precision brands. Target: TBD |
| **Reticle** | A reticle pattern (e.g., "EBR-7C MRAD") | 13 | Prototype seed — common precision reticles. Target: TBD |

### What Prototype Seed Data Looks Like

To make this concrete — here's the actual data in the database today for our two priority calibers:

**6.5 Creedmoor — Bullets (8 seeded):**
Hornady 140gr ELD Match, Hornady 143gr ELD-X, Hornady 147gr ELD Match, Sierra 140gr MatchKing HPBT, Berger 140gr Hybrid Target, Nosler 140gr RDF, Lapua 140gr Scenar-L, Barnes 127gr LRX

**6.5 Creedmoor — Factory Cartridges (6 seeded):**
Hornady 140gr ELD Match @ 2710fps, Hornady 147gr ELD Match @ 2695fps, Hornady 143gr ELD-X @ 2700fps, Federal Gold Medal 140gr SMK @ 2700fps, Federal Gold Medal 130gr Berger Hybrid @ 2875fps, Nosler Match Grade 140gr RDF @ 2650fps

**.308 Winchester — Bullets (7 seeded):**
Sierra 168gr MatchKing HPBT, Sierra 175gr MatchKing HPBT, Hornady 168gr ELD Match, Hornady 178gr ELD Match, Hornady 230gr A-Tip Match, Nosler 168gr Custom Competition, Berger 185gr Hybrid Target

**.308 Winchester — Factory Cartridges (9 seeded):**
Federal Gold Medal 175gr SMK @ 2600fps, Federal Gold Medal 168gr SMK @ 2650fps, Hornady 178gr ELD Match @ 2600fps, Hornady 168gr ELD Match @ 2700fps, Hornady 178gr ELD-X @ 2600fps, Black Hills 175gr SMK @ 2600fps, Berger 185gr Juggernaut OTM @ 2560fps, Lapua 167gr Scenar @ 2625fps, Winchester Match 168gr HPBT @ 2680fps

**Rifle Models (15 seeded across 4 calibers):**
6.5 CM: Bergara B-14 HMR (22", 1:8), Bergara B-14 HMR PRO (24", 1:8), Tikka T3x TAC A1 (24", 1:8), Ruger Precision (24", 1:8), Howa 1500 HCR (24", 1:8), Savage 110 Tactical (24", 1:8), MPA BA Comp (26", 1:8)
.308 Win: Bergara B-14 HMR (20", 1:10), Tikka T3x TAC A1 (24", 1:11), Ruger Precision (20", 1:10), Savage 110 Tactical (24", 1:10), Remington 700 SPS Tactical (20", 1:10)
6.5 PRC: Bergara B-14 HMR (24", 1:8) | .300 WM: Tikka T3x TAC A1 (24", 1:10) | .300 PRC: Ruger Precision (26", 1:9)

*This seed data is enough to prototype the full profile creation flow for 6.5 CM and .308 Win. Other calibers fall back to inference-only until the pipeline delivers more data.*

**The key takeaway:** Calibers, chambers, and manufacturers are comprehensive and stable. These are editorial data — they change slowly (a few new calibers per year) and are fully maintainable by hand. Bullets, cartridges, rifle models, and optics have prototype seed data covering our two priority calibers (6.5 CM and .308 Win), but need 10-20x more rows for comprehensive V1 coverage. The automated data collection pipeline to populate these is still being built.

### How Entities Relate

```
User picks...                What it unlocks...

  Manufacturer ─────────────┬──── filters Rifle Models
       │                    ├──── filters Bullets
       │                    └──── filters Cartridges
       │
  Caliber/Chamber ──────────┬──── bullet diameter (exact)
       │                    ├──── action length (short/long/magnum)
       │                    ├──── compatible ammo (via chamber↔caliber)
       │                    └──── filters Rifle Models, Cartridges, Bullets
       │
  Rifle Model ──────────────┬──── barrel length (exact)
       │                    ├──── twist rate (exact)
       │                    └──── chamber → caliber (linked)
       │
  Cartridge ────────────────┬──── bullet weight, BC values (via linked Bullet)
       │                    ├──── published muzzle velocity
       │                    └──── test barrel length (context for MV)
       │
  Bullet ───────────────────┬──── BC (G1 and/or G7, published + estimated)
       │                    ├──── weight, diameter, sectional density
       │                    └──── type (match, hunting, lead-free, etc.)
       │
  Optic ────────────────────┬──── click unit (mil or MOA) + click value
                            ├──── adjustment range (elevation/windage travel)
                            └──── focal plane (FFP/SFP)
```

### Manufacturer Breakdown

We have 32 manufacturers, tagged by what they make:

| Role | Count | Examples |
|---|---|---|
| Bullet makers | 8 | Hornady, Federal, Sierra, Berger, Nosler, Barnes, Lapua, Speer |
| Ammo makers (loaded cartridges) | 12 | Hornady, Federal, Black Hills, Sellier & Bellot, IMI, PPU, Winchester, Remington, Nosler, Lapua, PSA, Speer |
| Rifle makers (bolt-action) | 8 | Bergara, Tikka, Ruger, Howa, Savage, Remington, Masterpiece Arms, Aero Precision |
| Rifle makers (AR platform) | 10 | Daniel Defense, Knight's Armament, LaRue, Aero Precision, JP Enterprises, Seekins, LMT, Geissele, BCM, LWRC |
| Data providers | 1 | Applied Ballistics |

*Note: Many manufacturers span categories. Hornady makes both component bullets and loaded ammo. Federal owns Sierra. Remington makes both rifles and ammo.*

---

## 2. The Caliber as Master Key

Caliber is the single most information-dense choice a user can make. From one selection, we learn a remarkable amount — enough to populate smart defaults for nearly every field in the profile.

### What Picking a Caliber Tells Us

| We learn... | How it helps |
|---|---|
| **Bullet diameter** (exact, in inches) | Auto-fills bullet diameter. No user input needed. |
| **Action length** (mini / short / long / magnum) | Narrows barrel length options. Short-action calibers typically run 20-24" barrels; magnums run 24-26"+. |
| **Is this a precision/long-range cartridge?** | Affects default zero distance, likely use case, and which bullets to suggest first. |
| **Compatible chambers** | Most calibers have exactly one chamber. A few have interesting cases (.223 Rem / 5.56 NATO / .223 Wylde). |
| **Year introduced** | Newer cartridges (6.5 CM, 7mm PRC) have more predictable specs; legacy cartridges (.30-06, .270 Win) have wider variation. |
| **Typical grain weights** | Each caliber has a narrow band of common bullet weights. 6.5 CM is almost always 120-147gr. .308 Win is 150-175gr. |
| **Typical twist rates** | Modern precision calibers are very consistent: 6.5 CM is almost universally 1:8. Older calibers vary more. |
| **Likely zero distance** | 100 yards for most rifle calibers. 50/200 for .223/5.56. 300 for some magnum hunting setups. |

### Worked Example: User Picks "6.5 Creedmoor"

Instantly known:
- Bullet diameter: **0.264"**
- Action length: **Short action**
- Common for long-range: **Yes**
- Year introduced: **2007** (modern, predictable specs)

Confidently inferrable:
- Barrel length: **22"** (most common) or **24"** — show as 2-3 options
- Twist rate: **1:8** (nearly universal for 6.5 CM)
- Zero distance: **100 yards** (standard for LR calibers)
- Common bullet weights: **120gr, 130gr, 135gr, 140gr, 143gr, 147gr** — show as options
- Likely BC range: G7 **0.255–0.351** (based on common match bullets)
- Published MV range: **2,600–2,800 fps** (factory loads in 24" test barrels)

What the user still needs to tell us:
- Their actual barrel length (if different from default)
- Their ammo / bullet choice → MV and BC
- Their actual MV (if they've chronographed)
- Zero conditions (distance, already defaulted)

**From one tap, we've gone from 15+ unknown fields to 3-4 meaningful decisions.**

### All 25 Calibers — Key Properties

| # | Caliber | Bullet Dia. | Action | LR? | Typical Weights | Typical Twist | Typical Barrel |
|---|---------|------------|--------|-----|-----------------|---------------|----------------|
| 1 | 6.5 Creedmoor | .264" | Short | Yes | 120-147gr | 1:8 | 22-24" |
| 2 | .308 Winchester | .308" | Short | Yes | 150-175gr | 1:10 | 20-24" |
| 3 | 6mm Dasher | .243" | Short | Yes | 105-115gr | 1:7.5-1:8 | 24-26" |
| 4 | 6mm GT | .243" | Short | Yes | 105-115gr | 1:7.5-1:8 | 22-24" |
| 5 | 6mm Creedmoor | .243" | Short | Yes | 95-115gr | 1:7.5-1:8 | 22-26" |
| 6 | .223 Remington | .224" | Mini | No | 55-77gr | 1:7-1:12 | 16-20" |
| 7 | 5.56x45mm NATO | .224" | Mini | No | 55-77gr | 1:7-1:9 | 14.5-20" |
| 8 | .300 Win Mag | .308" | Long | Yes | 168-220gr | 1:10 | 24-26" |
| 9 | .300 PRC | .308" | Magnum | Yes | 200-230gr | 1:9-1:10 | 24-26" |
| 10 | 6.5 PRC | .264" | Short | Yes | 130-147gr | 1:8 | 24-26" |
| 11 | 7mm PRC | .284" | Short | Yes | 160-180gr | 1:8-1:8.5 | 22-24" |
| 12 | .338 Lapua Mag | .338" | Magnum | Yes | 250-300gr | 1:9.3-1:10 | 26-27" |
| 13 | .270 Winchester | .277" | Long | No | 130-150gr | 1:10 | 22-24" |
| 14 | .30-06 Springfield | .308" | Long | No | 150-180gr | 1:10 | 22-24" |
| 15 | 7mm Rem Mag | .284" | Long | Yes | 150-175gr | 1:9-1:9.5 | 24-26" |
| 16 | .260 Remington | .264" | Short | No | 120-140gr | 1:8 | 22-24" |
| 17 | 7.62x51mm NATO | .308" | Short | No | 147-175gr | 1:10-1:12 | 18-22" |
| 18 | .243 Winchester | .243" | Short | No | 55-105gr | 1:8-1:10 | 22-24" |
| 19 | .300 WSM | .308" | Short | Yes | 168-200gr | 1:10 | 22-24" |
| 20 | 7mm-08 Rem | .284" | Short | No | 140-162gr | 1:9.5 | 22" |
| 21 | 6.5x55 Swedish | .264" | Long | No | 120-140gr | 1:8 | 22-24" |
| 22 | .300 AAC Blackout | .308" | Mini | No | 110-220gr | 1:7-1:8 | 8-16" |
| 23 | .338 Win Mag | .338" | Long | No | 200-250gr | 1:10 | 24-26" |
| 24 | 6mm ARC | .243" | Mini | Yes | 103-108gr | 1:7.5 | 18-24" |
| 25 | 6.5-284 Norma | .264" | Long | Yes | 130-147gr | 1:8 | 26-28" |

### Chamber vs. Caliber — The Interesting Cases

Most calibers map 1:1 to a chamber (6.5 Creedmoor the caliber → 6.5 Creedmoor the chamber). But a few cases are important for UX:

| Chamber | Accepts (primary) | Also accepts | UX implication |
|---|---|---|---|
| **.223 Wylde** | .223 Remington | 5.56x45mm NATO | Most popular AR-15 precision chamber. User picks this chamber, can shoot either caliber's ammo. |
| **5.56 NATO** | 5.56x45mm NATO | .223 Remington | Military spec. Safe to fire both. |
| **.223 Remington** | .223 Remington | *(5.56 NOT safe)* | Rare on modern rifles, but important safety distinction. |
| **.308 Winchester** | .308 Winchester | 7.62x51mm NATO | Universally considered interchangeable in modern rifles. |
| **7.62x51mm NATO** | 7.62x51mm NATO | .308 Winchester | Military spec. Both directions are safe. |

**Design implication:** For most calibers, we don't need to ask about the chamber at all — it's the same thing. We only need to surface the chamber distinction for the .223/5.56 and .308/7.62 families, and even there it mainly affects which ammo we show as compatible.

---

## 3. Rifle Platform — The Other Opening Move

If caliber answers "what ammo do you shoot?", rifle platform answers "what kind of gun do you shoot?" — and for many shooters, the gun comes to mind first. "I have a bolt gun" or "I shoot an AR" is often the most natural starting point.

Platform is also a legitimate ballistic input: it determines **sight height** (the vertical distance from bore centerline to optic centerline), which the solver uses to calculate the initial trajectory. And it's a powerful UX filter — it constrains caliber options, barrel length ranges, and even which manufacturers to show.

### The Three Platforms

| Platform | What It Is | Sight Height | Barrel Range | Caliber Constraint |
|---|---|---|---|---|
| **Bolt Action** | Manually cycled action. The precision standard. | ~1.5–1.75" | 20–28" (varies by caliber) | Any caliber — no restriction |
| **AR-15** | Small-frame semi-auto (mil-spec lower). The most popular rifle platform in the US. | ~2.5–2.8" | 10.3–20" | Mini-action calibers only: .223, 5.56, .300 BLK, 6mm ARC |
| **AR-10** | Large-frame semi-auto (LR-308 / SR-25 pattern). | ~2.5–2.8" | 16–24" | Short-action calibers: .308, 6.5 CM, .260 Rem, 6.5 PRC, .243 Win, 7mm-08 |

*Sight height difference matters ballistically: at 100 yards the effect is small, but at 1,000+ yards a 1" sight height error shows up in the solution. Auto-filling this from platform is a real accuracy win that most competitors miss.*

### What Platform Tells Us

| We learn... | How it helps |
|---|---|
| **Sight height** (exact default) | Auto-fills a real solver input. Bolt ≈ 1.5". AR ≈ 2.6". User can refine, but the default is correct for 80%+ of setups. |
| **Caliber filter** | AR-15 → show only 4-5 calibers. AR-10 → show only 6-7. Bolt → show all. Dramatic list reduction for AR users. |
| **Barrel length norms** | Gas guns run shorter barrels than bolt guns in the same caliber. 6.5 CM bolt = 22-24". 6.5 CM AR-10 = 18-22". |
| **Manufacturer filter** | Bolt gun makers and AR makers are largely different brands. Filters the manufacturer list when showing rifle models. |
| **Visual identity** | Each platform has a distinct silhouette. Design can use this for illustrations, profile cards, and icons — making the profile feel personal. |

### Platform × Caliber Compatibility

Every caliber in our database maps to one or more platforms. Here's the full matrix:

| # | Caliber | Bolt Action | AR-15 | AR-10 | Most Common Platform |
|---|---------|:-----------:|:-----:|:-----:|---------------------|
| 1 | 6.5 Creedmoor | ✓ | — | ✓ | Bolt (but AR-10 growing) |
| 2 | .308 Winchester | ✓ | — | ✓ | Split ~60/40 bolt/AR-10 |
| 3 | 6mm Dasher | ✓ | — | — | Bolt only (wildcat) |
| 4 | 6mm GT | ✓ | — | ✓ | Bolt (AR-10 emerging) |
| 5 | 6mm Creedmoor | ✓ | — | ✓ | Bolt |
| 6 | .223 Remington | ✓ | ✓ | — | AR-15 |
| 7 | 5.56x45mm NATO | ✓ | ✓ | — | AR-15 |
| 8 | .300 Win Mag | ✓ | — | — | Bolt only |
| 9 | .300 PRC | ✓ | — | — | Bolt only |
| 10 | 6.5 PRC | ✓ | — | ✓ | Bolt (AR-10 rare) |
| 11 | 7mm PRC | ✓ | — | — | Bolt only |
| 12 | .338 Lapua Mag | ✓ | — | — | Bolt only |
| 13 | .270 Winchester | ✓ | — | ✓ | Bolt |
| 14 | .30-06 Springfield | ✓ | — | ✓ | Bolt |
| 15 | 7mm Rem Mag | ✓ | — | — | Bolt only |
| 16 | .260 Remington | ✓ | — | ✓ | Bolt |
| 17 | 7.62x51mm NATO | ✓ | — | ✓ | AR-10 (military heritage) |
| 18 | .243 Winchester | ✓ | — | ✓ | Bolt |
| 19 | .300 WSM | ✓ | — | — | Bolt only |
| 20 | 7mm-08 Rem | ✓ | — | ✓ | Bolt |
| 21 | 6.5x55 Swedish | ✓ | — | — | Bolt only |
| 22 | .300 AAC Blackout | ✓ | ✓ | — | AR-15 |
| 23 | .338 Win Mag | ✓ | — | — | Bolt only |
| 24 | 6mm ARC | ✓ | ✓ | — | AR-15 (purpose-built) |
| 25 | 6.5-284 Norma | ✓ | — | — | Bolt only |

**The filtering power:**
- Bolt Action → all 25 calibers (no reduction, but that's expected — bolt guns shoot everything)
- AR-15 → **4 calibers** (.223 Rem, 5.56 NATO, .300 BLK, 6mm ARC)
- AR-10 → **~12 calibers** (short-action family: .308, 6.5 CM, .260, .243, 6mm CM, 6mm GT, 6.5 PRC, 7mm-08, 7.62 NATO, .270, .30-06, .300 BLK via conversion)

For an AR-15 user, picking platform first instantly reduces caliber selection from 25 options to 4. That's a massive UX win.

### Flow Order: Platform-First vs. Caliber-First

Either order works — but they serve different users:

**Platform-First** ("What kind of gun?"):
- Best for AR users: their platform is highly defining — it immediately narrows caliber to a short list
- Matches the mental model of "I have an AR-15" → "it's in .223 Wylde" → "I shoot 77gr SMKs"
- Enables the silhouette/illustration moment at the very first step — visually engaging, feels like building *your* gun
- For bolt action users, it's less powerful (still shows all 25 calibers) but still feels like a natural opening question

**Caliber-First** ("What do you shoot?"):
- Best for bolt-action precision shooters: their caliber is highly defining — 6.5 CM tells us almost everything
- More information-dense as a first choice (caliber carries bullet diameter, action length, etc.)
- For AR users, caliber-first works but they still need to pick platform afterward (for sight height, barrel length)

**A reasonable default:** Platform-first as the opening question, then caliber. The filtering is dramatic for AR users and harmless for bolt users. The silhouette moment sets the tone. Caliber follows immediately.

But this is a design call — both orderings are valid. The data supports either.

### Design Opportunity: Silhouettes

Three platform silhouettes give the profile creation flow a visual anchor:

- **Bolt Action:** classic long-range bolt rifle profile — scope, heavy contour barrel, maybe a bipod hint
- **AR-15:** unmistakable flat-top AR silhouette — shorter, buffer tube, pistol grip, carry handle or optic rail
- **AR-10:** similar to AR-15 but with a larger frame, longer handguard, bigger magwell

These aren't just decorative — they persist into the profile card in the Arsenal, giving each gun a visual identity. "That's my 6.5 CM bolt gun" vs. "that's my .308 AR."

*Note: We don't currently have platform/type data in the schema. This is pure UX-side logic — the app knows the 3 platforms, the caliber-platform compatibility matrix, and the sight height defaults. No backend changes needed.*

---

## 4. Profile Creation Flows — Systematic Comparison

*The flows below use platform + caliber as the opening sequence (see Section 3 for the case for platform-first ordering, and Section 2 for why caliber is so information-dense). Either order works — the data supports both, and the design team should prototype both to see which feels better.*

The ballistic solver needs a specific set of inputs to run (see Section 6). There are multiple paths to collect those inputs. Each path makes different trade-offs between data library dependency, number of user decisions, and accuracy of the resulting profile.

### Flow A: Rifle-First (Current Prototype)

*"I know exactly what gun I have. Look it up."*

| Step | User does | We auto-fill | Data source |
|---|---|---|---|
| 1. Search for rifle | Types "Bergara HMR 6.5" | — | RifleModel table (search) |
| 2. Confirm rifle | Taps result | Manufacturer, chamber, barrel length, twist rate | RifleModel record |
| 3. Search for ammo | Types "Hornady 140 ELD Match" | — | Cartridge table (search) |
| 4. Confirm ammo | Taps result | Bullet weight, BC (G1/G7), published MV, bullet diameter | Cartridge → Bullet |
| 5. Confirm zero | Adjusts if needed (default 100yd) | Zero distance (defaulted) | Inferred from caliber |

**Strengths:** Fewest user decisions. Most accurate auto-fill. Feels like "the app knows my gear."

**Weaknesses:** Requires comprehensive RifleModel and Cartridge data. If the user's rifle isn't in the database, the flow breaks — they need to bail to manual entry. This is the highest-risk path from a data coverage standpoint.

**Data readiness:** Not ready for production. Prototype seed data exists for 6.5 CM and .308 Win only (15 rifle models, 15 cartridges) — enough for prototyping but not comprehensive coverage. Target: ~50-80 rifle models across all priority calibers, ~200-300 cartridges. Blocked by automated pipeline.

---

### Flow B: Platform + Caliber Progressive Narrowing

*"What are you shooting? I'll figure out the rest."*

| Step | User does | UI | We learn / auto-fill |
|---|---|---|---|
| 1. Pick platform | 3 large tap targets with silhouettes: **Bolt Action** / **AR-15** / **AR-10** | Sight height auto-filled (1.5" bolt, 2.6" AR). Filters caliber list. |
| 2. Pick caliber | Filtered list (all 25 for bolt, 4 for AR-15, ~12 for AR-10), sorted by popularity | Bullet diameter, action length, compatible chambers |
| 3. Pick barrel length | 2-4 options informed by platform + caliber (e.g., bolt + 6.5 CM → 22" / 24") | Barrel length locked in |
| 4. Confirm twist rate | Pre-filled from caliber default, editable | Twist rate (usually just confirm) |
| 5. Pick ammo *or* enter bullet | Search cartridges, or go to handloader path | BC, MV, bullet weight |
| 6. Confirm zero | Pre-filled 100yd (or 50/200 for .223/5.56) | Zero distance |

**Strengths:** Works today for steps 1-4 with zero pipeline dependency. Each step is a small, curated list — not a search box. The "just a few taps" experience. The platform silhouette at step 1 makes it immediately visual and personal — you're building *your* gun profile. For AR-15 users, step 2 shows only 4 calibers instead of 25 — dramatic simplification. Gracefully degrades: even if ammo search fails (step 5), the user can manually enter BC + MV and still get a solution.

**Weaknesses:** Slightly more steps than rifle-first. The user doesn't get the "you know my exact gun" moment. Barrel length and twist rate options are inferred defaults, not exact specs.

**Data readiness:** Steps 1-4 are ready today. Step 5 depends on Bullet/Cartridge data (pending pipeline). Manual fallback always works.

**This is the lightest-lift path that still delivers the "smart defaults" experience.**

---

### Flow C: Handloader Path

*"I reload my own ammo. I know my bullet and MV."*

~20-30% of serious long-range shooters handload. They already know their bullet and have chronographed their muzzle velocity. They don't need or want to pick a factory cartridge.

| Step | User does | We auto-fill |
|---|---|---|
| 1. Pick platform | Same as Flow B, step 1 (bolt/AR-15/AR-10 silhouettes) | Sight height, caliber filter |
| 2. Pick caliber | Same as Flow B, step 2 | Bullet diameter, defaults |
| 3. Pick/confirm rifle details | Same as Flow B, steps 3-4 (barrel length, twist) | Barrel length, twist rate |
| 4. Search for bullet | Types "Berger 140 Hybrid" | BC (G1/G7), weight, type |
| 5. Enter muzzle velocity | Types their chrono'd MV (e.g., "2720") | — |
| 6. Confirm zero | Pre-filled | Zero distance |

**Strengths:** Fastest path for handloaders — they skip the cartridge entirely. Respects that they already have the most critical data point (actual MV from their chronograph). This should feel first-class, not like a workaround.

**Weaknesses:** Requires Bullet table data for step 4. Manual MV entry is required (but handloaders expect this).

**Data readiness:** Steps 1-3 ready today. Step 4 depends on Bullet data (pending pipeline). Manual fallback available.

---

### Flow D: Manual Escape Hatch

*"My gear isn't in your database. Let me just type it in."*

Always available. Every field is directly editable. This is the fallback when the library doesn't have what the user needs.

| Step | User does |
|---|---|
| 1. Enter caliber (or pick from list) | Name + bullet diameter |
| 2. Enter barrel specs | Barrel length, twist rate |
| 3. Enter bullet/load specs | Weight, BC (G1 or G7), muzzle velocity |
| 4. Enter zero | Zero distance |

**Strengths:** Always works, regardless of database coverage. Necessary escape hatch.

**Weaknesses:** Most effort. Highest risk of bad data (user may not know their BC). No "the app knows" moment. This is what every competitor makes the default path — it's the experience we're trying to improve upon.

**Data readiness:** Always ready. No dependencies.

---

### Flow E: Hybrid — Platform + Caliber with Optional Rifle Enrichment

*"Start smart, get more specific if you want."*

This is Flow B with an optional rifle lookup layered on top — the recommended approach.

| Step | User does | Notes |
|---|---|---|
| 1. Pick platform | Bolt / AR-15 / AR-10 silhouettes | Same as Flow B step 1. Sight height auto-filled, caliber list filtered. |
| 2. Pick caliber | Tap from filtered list | Same as Flow B step 2 |
| 3a. *(Optional)* Look up rifle | "Want to look up your exact rifle?" → search | Only if RifleModel data is available. Overrides barrel/twist defaults with exact specs. |
| 3b. *(Default)* Pick barrel length | 2-4 curated options based on platform + caliber | If user skips rifle lookup or rifle not found |
| 4. Pick ammo or enter bullet | Search or manual entry | Same as Flow B step 5 / Flow C step 4 |
| 5. Confirm zero | Pre-filled | Done |

**Strengths:** Gets the best of both worlds. Opens with a visual platform moment (silhouettes), then narrows intelligently. Works today with platform + caliber defaults. Gets better over time as the rifle model database grows. The rifle lookup is additive, not required — users who skip it still get a good profile. No dead ends.

**Weaknesses:** Slightly more complex to implement (conditional step 3a/3b). Need to decide how prominently to surface the rifle lookup.

**Data readiness:** Core flow ready today. Rifle lookup improves as RifleModel data arrives. Can ship without it and add later.

---

### Flow Comparison Summary

| | Rifle-First (A) | Platform + Caliber (B) | Handloader (C) | Manual (D) | Hybrid (E) |
|---|---|---|---|---|---|
| **User decisions** | 2-3 | 5-6 | 5-6 | 4+ | 4-5 |
| **Auto-fill accuracy** | Exact | Inferred defaults | Exact bullet, manual MV | None | Mix |
| **Library dependency** | HIGH | LOW (steps 1-4) | MEDIUM (bullet) | NONE | LOW + incremental |
| **Ready to ship today?** | No | Steps 1-4 yes | Steps 1-3 yes | Yes | Steps 1-3b yes |
| **Dead-end risk** | High (rifle not found) | Low (always has manual fallback) | Medium (bullet not found) | None | Low |
| **Visual identity** | Depends on rifle data | Platform silhouette at step 1 | Platform silhouette at step 1 | None | Platform silhouette at step 1 |
| **"The app knows me" feel** | Strong | Moderate | Moderate | None | Moderate → Strong over time |

---

## 5. What Each Choice Narrows — The Decision Cascade

Each user choice dramatically narrows the set of remaining options. This is what makes the "curated small list" UX possible — by the time the user reaches step 3 or 4, there are only a handful of sensible options left.

### Platform Selection — The First Filter

Picking a platform constrains everything downstream:

| What it filters | Bolt Action | AR-15 | AR-10 |
|---|---|---|---|
| **Caliber list** | All 25 (no reduction) | 4 calibers | ~12 calibers |
| **Sight height** | ~1.5" (auto-filled) | ~2.6" (auto-filled) | ~2.6" (auto-filled) |
| **Barrel length range** | 20-28" (wide, varies by caliber) | 10.3-20" (shorter) | 16-24" (mid-range) |
| **Manufacturer filter** | Bergara, Tikka, Savage, Ruger, etc. | Daniel Defense, BCM, Aero, etc. | LaRue, KAC, LMT, JP, etc. |
| **Visual identity** | Classic bolt rifle silhouette | Flat-top AR silhouette | Large-frame AR silhouette |

For AR-15 users, this single tap reduces caliber options from 25 → 4. For bolt users, the reduction is minimal but the visual moment and sight height auto-fill are still valuable.

### Caliber Selection — The Big Filter

Picking a caliber immediately constrains:

| What it filters | Example: User picks "6.5 Creedmoor" |
|---|---|
| **Bullet diameter** | Locked to 0.264" — eliminates every bullet not in 6.5mm |
| **Compatible bullets** | From (all bullets in DB) → only 6.5mm bullets (typically 15-30 options per caliber) |
| **Compatible cartridges** | From (all cartridges in DB) → only 6.5 CM factory loads (typically 20-40 per caliber) |
| **Compatible rifle models** | From (all rifles in DB) → only rifles chambered in 6.5 CM |
| **Action length** | Short action → barrel length options narrow to 20-26" range |
| **Barrel length defaults** | 22" or 24" (the two most common for 6.5 CM bolt guns) |
| **Twist rate default** | 1:8 (nearly universal) |
| **Zero distance default** | 100 yards |
| **Common bullet weights** | 120gr, 130gr, 135gr, 140gr, 143gr, 147gr |

### Platform + Caliber Combined — The Barrel Length Filter

Once we know platform + caliber, barrel length options narrow dramatically:

| Platform + Caliber | Barrel Length Options | Twist Rate | Notes |
|---|---|---|---|
| 6.5 CM + Bolt | 20", 22", **24"** | 1:8 | 22" and 24" cover 90%+ of users |
| 6.5 CM + AR-10 | 18", 20", **22"**, 24" | 1:8 | Shorter barrels more common on gas guns |
| .308 Win + Bolt | 20", **22"**, 24" | 1:10 | Very consistent |
| .308 Win + AR-10 | 16", 18", **20"** | 1:10 | Shorter barrels, military heritage |
| .223 Rem + AR-15 | 14.5", 16", 18", **20"** | 1:7, 1:8, 1:9 | Twist rate actually matters here — depends on bullet weight intent |
| .300 BLK + AR-15 | 8", **10.3"**, 16" | 1:7, 1:8 | Short barrels dominate (suppressed use case) |
| .300 Win Mag + Bolt | **24"**, 26" | 1:10 | Very consistent |
| .338 Lapua + Bolt | **26"**, 27" | 1:9.3, 1:10 | Long barrels only |

*Bold = suggested default. The design should highlight the default while showing alternatives.*

### Bullet Weight — Narrowing the Ammo Step

Knowing the caliber immediately bounds the reasonable bullet weights. This is powerful for the ammo selection step — instead of searching the entire database, we can show a short list of common weights:

| Caliber | Common Weights | "Default" Weight | Why |
|---|---|---|---|
| 6.5 Creedmoor | 120, 130, 135, 140, 143, 147gr | 140gr | Most popular match load (Hornady 140 ELD-M) |
| .308 Winchester | 147, 150, 155, 168, 175, 178, 185gr | 175gr / 168gr | 175 SMK or 168 BTHP are the precision standards |
| .223 / 5.56 | 55, 62, 69, 73, 77gr | 77gr (precision) or 55gr (general) | Depends heavily on twist rate and use case |
| .300 Win Mag | 168, 175, 190, 200, 210, 220, 230gr | 200-215gr | Heavy bullets dominate for LR work |
| .300 PRC | 200, 212, 215, 220, 225, 230gr | 212-225gr | Designed for heavy, high-BC bullets |
| 6.5 PRC | 130, 135, 140, 143, 147gr | 143gr | Same bullets as 6.5 CM, faster |
| 7mm PRC | 160, 168, 175, 180gr | 175gr | Built around heavy 7mm bullets |
| .338 Lapua | 250, 270, 285, 300gr | 285gr | Hornady ELD-M 285 is the standard |

---

## 6. Solver Input Requirements

The ballistic solver needs specific inputs to produce a solution. Here's what it requires, what's optional, and how each profile creation flow provides them.

### Required Inputs (Solver Won't Run Without These)

| Input | What It Is | Where It Comes From |
|---|---|---|
| **Muzzle velocity** (fps) | How fast the bullet leaves the barrel | Factory cartridge spec, chrono measurement, or manual entry |
| **Ballistic coefficient** (G1 or G7) | How well the bullet resists air drag | Bullet record (published or estimated), or manual entry |
| **Bullet weight** (grains) | Mass of the projectile | Bullet or cartridge record, or manual entry |
| **Bullet diameter** (inches) | Width of the projectile | Auto-filled from caliber — user should never need to enter this |
| **Zero distance** (yards) | Distance at which the rifle is zeroed | Defaulted from caliber (usually 100yd), user-adjustable |
| **Sight height** (inches) | Height of scope centerline above bore | Defaulted (1.5" for bolt, 2.6" for AR), user-adjustable |
| **Target distance** (yards) | What distance to solve for | Entered at solve time, not during profile creation |

### Optional Inputs (Improve Accuracy)

| Input | What It Is | Where It Comes From |
|---|---|---|
| **Barrel length** (inches) | Affects MV adjustment from published values | Rifle model, platform + caliber inference, or manual entry |
| **Twist rate** (e.g., "1:8") | Affects stability / spin drift correction | Rifle model, caliber default, or manual entry |
| **Barrel twist direction** | Right or left hand twist | Defaulted to right (RH), almost universal |
| **Atmospheric conditions** | Temperature, pressure, humidity | Phone sensors + weather API (separate from profile creation) |
| **Wind speed + direction** | Wind conditions | Manual input at solve time |
| **Incline angle** | Shooting uphill/downhill | Phone sensors or manual input at solve time |
| **Latitude** | For Coriolis correction | GPS, minor effect at typical distances |

### How Each Flow Fills the Required Inputs

| Required Input | Flow A (Rifle-First) | Flow B (Platform + Caliber) | Flow C (Handloader) | Flow D (Manual) |
|---|---|---|---|---|
| Muzzle velocity | Cartridge record | Cartridge record or manual | User enters (chrono'd) | User enters |
| Ballistic coefficient | Bullet record (via cartridge) | Bullet record or manual | Bullet record | User enters |
| Bullet weight | Cartridge record | Cartridge/bullet record or manual | Bullet record | User enters |
| Bullet diameter | Caliber (via rifle → chamber) | Caliber (direct pick) | Caliber (direct pick) | User enters |
| Zero distance | Default from caliber | Default from caliber | Default from caliber | User enters |
| Sight height | Default from platform | Default from platform | Default from platform | User enters |

---

## 7. Data Gaps & Dependencies

### What the Backend Team Is Building

The automated data collection pipeline will populate:

| Entity | Target Count (V1) | Priority | Notes |
|---|---|---|---|
| **Bullet** | 150-200 | High | Shared across factory and handloader paths. Core ballistic data. |
| **Cartridge** | 200-300 | High | Factory ammo. Each references a Bullet. Covers ~8 priority calibers. |
| **Rifle Model** | 50-80 | Medium | Nice-to-have for exact auto-fill. Not required for caliber-first flow. |
| **Optic** | TBD | Lower | Useful for click value auto-fill. Not blocking profile creation. |
| **Reticle** | TBD | Lower | Linked from optics. Not blocking. |

### What's Unblocked Today vs. What's Waiting

| Flow Component | Status | Depends On |
|---|---|---|
| Platform selection (Bolt/AR-15/AR-10) | **Ready now** | Nothing — static UI logic, 3 tap targets + silhouettes |
| Caliber selection (filtered by platform) | **Ready now** | Nothing — editorial data, hand-curated, platform × caliber matrix is static |
| Sight height auto-fill from platform | **Ready now** | Nothing — hardcoded defaults (1.5" bolt, 2.6" AR) |
| Barrel length inference from platform + caliber | **Ready now** | Nothing — can be hardcoded from domain knowledge |
| Twist rate defaults from caliber | **Ready now** | Nothing — can be hardcoded |
| Zero distance defaults from caliber | **Ready now** | Nothing — can be hardcoded |
| Rifle model search + auto-fill | Blocked | RifleModel data (pipeline) |
| Factory ammo search + auto-fill | Blocked | Cartridge + Bullet data (pipeline) |
| Bullet search (handloader path) | Blocked | Bullet data (pipeline) |
| Optic search + click value auto-fill | Blocked | Optic + Reticle data (pipeline) |
| Manual entry for all fields | **Ready now** | Nothing |

### Recommended Phasing

**Phase 1 (shippable now):** Platform + caliber progressive narrowing (Flow B / Flow E without rifle lookup). User picks platform (with silhouette) → caliber (filtered list) → barrel length → twist rate. Platform auto-fills sight height and filters calibers; caliber auto-fills everything else. Ammo/bullet selection falls back to manual entry until pipeline data arrives. This flow works today and provides the "few taps, not a ton of typing" experience — plus the visual identity moment of picking your platform.

**Phase 1.5 (when Bullet + Cartridge data lands):** Add ammo search + bullet search to the caliber-first flow. Handloader path (Flow C) becomes fully powered. This is the big unlock — most of the solver's accuracy depends on BC and MV, which come from the Bullet and Cartridge tables.

**Phase 2 (when RifleModel data lands):** Layer in optional rifle lookup (Flow E, step 3a). "Want to look up your exact rifle for precise specs?" This enriches barrel length and twist rate with exact values, replacing the inferred defaults. The flow doesn't depend on this — it just gets more precise.

**Phase 2+ (when Optic data lands):** Add optic selection to the profile creation flow. Auto-fill click unit (mil/MOA), click value, and adjustment range. Today this is manual entry in the app's rifle profile.

---

## Technical Appendix: Schema Details

*For engineers who need the exact column names, types, and relationships.*

### Caliber Table

```
caliber
├── id                    UUID (PK)
├── name                  String(255), unique    — "6.5 Creedmoor"
├── alt_names             JSON array             — ["6.5 CM", "6.5 Creed", "6.5mm Creedmoor"]
├── bullet_diameter_inches Float, NOT NULL        — 0.264
├── case_length_inches    Float, nullable
├── saami_designation     String(255), nullable
├── popularity_rank       Integer, nullable       — 1 = most popular (6.5 CM)
├── action_length         String(50), nullable    — "mini" | "short" | "long" | "magnum"
├── is_common_lr          Boolean, default false  — true for precision/LR cartridges
├── description           Text, nullable          — "The dominant precision rifle cartridge..."
├── rim_type              String(50), nullable    — "rimless" | "belted" | "rebated"
├── coal_inches           Float, nullable         — max cartridge overall length
├── max_pressure_psi      Integer, nullable       — SAAMI MAP
├── year_introduced       Integer, nullable
├── parent_caliber_id     UUID FK → caliber.id    — self-referential (cartridge family trees)
├── notes                 Text, nullable
├── source_url            String(500), nullable
├── created_at            DateTime (UTC)
└── updated_at            DateTime (UTC)
```

### Chamber + Join Table

```
chamber
├── id          UUID (PK)
├── name        String(255), unique    — "6.5 Creedmoor", ".223 Wylde"
├── alt_names   JSON array, nullable
├── notes       Text, nullable         — safety notes for multi-caliber chambers
├── source      String(500), nullable
├── created_at  DateTime (UTC)
└── updated_at  DateTime (UTC)

chamber_accepts_caliber (join table)
├── chamber_id  UUID FK → chamber.id   (composite PK)
├── caliber_id  UUID FK → caliber.id   (composite PK)
└── is_primary  Boolean, default true  — 1 = native caliber, 0 = also accepts
```

### Manufacturer Table

```
manufacturer
├── id          UUID (PK)
├── name        String(255), unique    — "Hornady", "Federal Premium"
├── alt_names   JSON array, nullable   — ["Federal", "Federal Ammunition", "ATK Federal"]
├── website_url String(500), nullable
├── logo_url    String(500), nullable
├── type_tags   JSON array, nullable   — ["bullet_maker", "ammo_maker"]
├── country     String(100), nullable  — "USA"
├── notes       Text, nullable
├── created_at  DateTime (UTC)
└── updated_at  DateTime (UTC)
```

### Bullet Table

```
bullet
├── id                    UUID (PK)
├── manufacturer_id       UUID FK → manufacturer.id
├── name                  String(255)            — "ELD Match", "MatchKing"
├── alt_names             JSON array, nullable   — ["ELDM", "ELD-M"]
├── sku                   String(100), nullable  — "#26331"
├── caliber_id            UUID FK → caliber.id
├── weight_grains         Float, NOT NULL        — 140.0
├── bc_g1_published       Float, nullable        — manufacturer's published G1 BC
├── bc_g1_estimated       Float, nullable        — third-party tested (AB, etc.)
├── bc_g7_published       Float, nullable
├── bc_g7_estimated       Float, nullable
├── bc_source_notes       Text, nullable
├── length_inches         Float, nullable        — bullet length (for stability calc)
├── sectional_density     Float, nullable
├── type_tags             JSON array, nullable   — ["boat-tail", "polymer-tip", "cup-and-core"]
├── used_for              JSON array, nullable   — ["match", "hunting-big-game"]
├── base_type             String(50), nullable   — "boat-tail" | "flat-base" | "rebated-boat-tail"
├── tip_type              String(50), nullable   — "polymer-tip" | "open-tip" | etc.
├── construction          String(50), nullable   — "cup-and-core" | "bonded" | "monolithic"
├── is_lead_free          Boolean, default false
├── popularity_rank       Integer, nullable
├── source_url            String(500), nullable
├── extraction_confidence Float, nullable
├── last_verified_at      DateTime, nullable
├── created_at            DateTime (UTC)
└── updated_at            DateTime (UTC)
```

### Cartridge Table

```
cartridge
├── id                        UUID (PK)
├── manufacturer_id           UUID FK → manufacturer.id
├── product_line              String(255), nullable   — "Precision Hunter", "Gold Medal"
├── name                      String(500)             — "Hornady 6.5 CM 140gr ELD Match"
├── alt_names                 JSON array, nullable
├── sku                       String(100), nullable   — "#81500"
├── caliber_id                UUID FK → caliber.id
├── bullet_id                 UUID FK → bullet.id
├── bullet_weight_grains      Float, NOT NULL         — 140.0 (denormalized for search)
├── muzzle_velocity_fps       Integer, NOT NULL       — 2710
├── test_barrel_length_inches Float, nullable         — 24.0 (context for MV)
├── round_count               Integer, nullable       — 20
├── bullet_match_confidence   Float, nullable         — pipeline entity resolution score
├── bullet_match_method       String(50), nullable    — "exact_sku" | "composite_key" | "fuzzy"
├── popularity_rank           Integer, nullable
├── source_url                String(500), nullable
├── extraction_confidence     Float, nullable
├── last_verified_at          DateTime, nullable
├── created_at                DateTime (UTC)
└── updated_at                DateTime (UTC)
```

### Rifle Model Table

```
rifle_model
├── id                    UUID (PK)
├── manufacturer_id       UUID FK → manufacturer.id
├── model                 String(255)            — "B-14 HMR", "T3x TAC A1"
├── manufacturer_url      String(500), nullable
├── alt_names             JSON array, nullable
├── chamber_id            UUID FK → chamber.id
├── barrel_length_inches  Float, nullable        — 22.0
├── twist_rate            String(20), nullable   — "1:8"
├── weight_lbs            Float, nullable
├── description           Text, nullable
├── barrel_material       String(100), nullable
├── barrel_finish         String(100), nullable
├── model_family          String(255), nullable  — groups variants (e.g., "B-14 HMR")
├── source_url            String(500), nullable
├── created_at            DateTime (UTC)
└── updated_at            DateTime (UTC)
```

### Optic + Reticle Tables

```
reticle
├── id              UUID (PK)
├── name            String(255), unique    — "EBR-7C MRAD"
├── alt_names       JSON array, nullable
├── unit            String(10), NOT NULL   — "mil" | "moa"
├── manufacturer_id UUID FK → manufacturer.id
├── description     Text, nullable
├── source_url      String(500), nullable
├── created_at      DateTime (UTC)
└── updated_at      DateTime (UTC)

optic
├── id                    UUID (PK)
├── manufacturer_id       UUID FK → manufacturer.id
├── name                  String(500)            — "Vortex Viper PST Gen II 5-25x50 EBR-7C MRAD"
├── alt_names             JSON array, nullable
├── model_family          String(255), nullable  — "Viper PST Gen II"
├── product_line          String(255), nullable  — "Viper PST"
├── sku                   String(100), nullable
├── reticle_id            UUID FK → reticle.id
├── click_unit            String(10), NOT NULL   — "mil" | "moa"
├── click_value           Float, NOT NULL        — 0.1 (mils) or 0.25 (MOA)
├── magnification_min     Float, NOT NULL        — 5.0
├── magnification_max     Float, NOT NULL        — 25.0
├── objective_diameter_mm Float, NOT NULL        — 50.0
├── tube_diameter_mm      Float, NOT NULL        — 30.0
├── focal_plane           String(10), NOT NULL   — "ffp" | "sfp"
├── elevation_travel_mils Float, nullable
├── windage_travel_mils   Float, nullable
├── weight_oz             Float, nullable
├── length_inches         Float, nullable
├── source_url            String(500), nullable
├── created_at            DateTime (UTC)
└── updated_at            DateTime (UTC)
```

### Entity Alias Table (Pipeline Metadata)

```
entity_alias
├── id          UUID (PK)
├── entity_type String(50)     — "caliber", "manufacturer", "bullet", etc.
├── entity_id   UUID           — FK to the relevant entity
├── alias       String(500)    — "6.5 CM", "Hornaday" (misspelling), "SMK"
└── alias_type  String(50)     — "abbreviation", "misspelling", "alternate_name", "sku"
                                  "military_designation", "nickname"

Unique constraint on (entity_type, entity_id, alias)
Currently: 115 aliases covering manufacturers and calibers
```

---

*Source files: `src/drift/models/`, seed data: `data/*.json`, migrations: `alembic/versions/`*
