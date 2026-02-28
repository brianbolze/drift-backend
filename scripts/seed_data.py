"""Seed the backend database with hand-curated Manufacturer, Caliber, Chamber,
ChamberAcceptsCaliber, and EntityAlias records.

Usage:
    python scripts/seed_data.py          # uses DATABASE_URL from env / .env
    python scripts/seed_data.py --reset  # drops and recreates seeded tables first

This is Step 2 of the build plan. All data here is editorial — curated from
SAAMI specs, manufacturer sites, and community consensus, not scraped.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure src/ is on sys.path when running as a script
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from sqlalchemy.orm import Session  # noqa: E402

from drift.database import get_engine, get_session_factory  # noqa: E402
from drift.models import (  # noqa: E402
    Base,
    Bullet,
    BulletBCSource,
    Caliber,
    CaliberPlatform,
    Cartridge,
    Chamber,
    ChamberAcceptsCaliber,
    EntityAlias,
    Manufacturer,
    Optic,
    Platform,
    Reticle,
    RifleModel,
)

# ---------------------------------------------------------------------------
# Manufacturer seed data
# Source: design proposal MVP scope + domain expert curation (2026-02-28)
# Reviewed and extended by firearms domain expert from original 38 → 86 entries.
# Key corrections: Vista Outdoor → CSG/Kinetic Group ownership (Nov 2024),
# Sierra/Barnes/Savage under JDH Capital, Berger remains Nammo Group.
# ---------------------------------------------------------------------------

MANUFACTURERS = [
    # --- Bullet Makers ---
    {
        "name": "Barnes Bullets",
        "alt_names": ["Barnes", "Barnes Bullets LLC"],
        "website_url": "https://www.barnesbullets.com",
        "type_tags": ["bullet_maker"],
        "country": "USA",
        "parent_company": "Bullseye Acquisitions / JDH Capital",
        "notes": (
            "Pioneer of monolithic copper bullets (TSX, TTSX, LRX). LRX line relevant for long-range hunting. "
            "Owned by Bullseye Acquisitions/JDH Capital (same group as Sierra and Savage), NOT Remington/Vista."
        ),
    },
    {
        "name": "Berger Bullets",
        "alt_names": ["Berger", "Burger", "Berger Bullets Nammo"],
        "website_url": "https://www.bergerbullets.com",
        "type_tags": ["bullet_maker"],
        "country": "USA",
        "parent_company": "Nammo Group (Capstone Precision Group)",
        "notes": (
            "76% of top-200 PRS shooters use Berger bullets. Hybrid Target and VLD designs dominate competition. "
            "109gr LRHT is the #1 6mm bullet in PRS (39% share). Owned by Nammo Group since Oct 2016 (NOT sold to "
            "JRS Enterprises — that claim is unverified)."
        ),
    },
    {
        "name": "Cutting Edge Bullets",
        "alt_names": ["CEB", "Cutting Edge", "CE Bullets"],
        "website_url": "https://www.cuttingedgebullets.com",
        "type_tags": ["bullet_maker"],
        "country": "USA",
        "notes": (
            "#1 bullet brand in ELR (Extreme Long Range) competitions. Monolithic solid copper/brass "
            "lathe-turned. SealTite Band technology. Founded by Dan Smitchko."
        ),
    },
    {
        "name": "Federal Premium",
        "alt_names": ["Federal", "Federal Ammunition", "ATK Federal", "Kinetic Group Federal"],
        "website_url": "https://www.federalpremium.com",
        "type_tags": ["ammo_maker", "bullet_maker"],
        "country": "USA",
        "parent_company": "Czechoslovak Group (CSG) / The Kinetic Group",
        "notes": (
            "Gold Medal Match line is the factory ammo benchmark. Federal Gold Medal Berger loads (156 EOL, "
            '153.5 LRHT) used by PRS competitors. As of Nov 2024, owned by Czechoslovak Group (CSG) as part of '
            '"The Kinetic Group" after Vista Outdoor split. Also owns CCI and Speer.'
        ),
    },
    {
        "name": "Hammer Bullets",
        "alt_names": ["Hammer", "Hammer Hunting Bullets"],
        "website_url": "https://www.hammerbullets.com",
        "type_tags": ["bullet_maker"],
        "country": "USA",
        "parent_company": "H D Custom Rifles & Ammunition LLC",
        "notes": (
            "Patented solid copper with driving band design. Reduces barrel fouling. Popular with long-range "
            "hunters. Controlled petal shedding for deep penetration. Validated to 900+ yds on elk."
        ),
    },
    {
        "name": "Hornady",
        "alt_names": ["Hornady Manufacturing", "Hornaday", "Hornady Mfg"],
        "website_url": "https://www.hornady.com",
        "type_tags": ["bullet_maker", "ammo_maker"],
        "country": "USA",
        "notes": (
            "Major bullet/ammo maker. ELD Match and A-Tip lines are precision staples. Also makes brass. "
            "Independently family-owned, based in Grand Island, NE. Founded 1949."
        ),
    },
    {
        "name": "Lapua",
        "alt_names": ["Nammo Lapua", "Lupua", "Lapua Oy"],
        "website_url": "https://www.lapua.com",
        "type_tags": ["bullet_maker", "ammo_maker"],
        "country": "Finland",
        "parent_company": "Nammo Group",
        "notes": (
            "Premium brass and Scenar/Scenar-L bullet line. Lapua brass is used by ~46% of top PRS shooters "
            "(with Alpha Munitions, they account for 92%). Parent company Nammo (same group as Berger, "
            "Vihtavuori, SK)."
        ),
    },
    {
        "name": "Lehigh Defense",
        "alt_names": ["Lehigh", "Lehigh Bullets"],
        "website_url": "https://www.lehighdefense.com",
        "type_tags": ["bullet_maker", "ammo_maker"],
        "country": "USA",
        "notes": (
            "Controlled Fracturing technology. More defense/LE focused but has rifle bullets. Match Solid line "
            "for precision. Based in Clarksville, TX."
        ),
    },
    {
        "name": "Norma",
        "alt_names": ["Norma Ammunition", "Norma Precision", "Norma Ammo"],
        "website_url": "https://www.norma-ammunition.com",
        "type_tags": ["ammo_maker", "bullet_maker"],
        "country": "Sweden",
        "parent_company": "Beretta Holding",
        "notes": (
            "Premium ammo and brass. One of the top 4 brass brands used by PRS competitors. ~240 employees, 100+ "
            "calibers. Founded 1902. Owned by Beretta. Also makes component bullets."
        ),
    },
    {
        "name": "Nosler",
        "alt_names": ["Nosler Inc", "Nossler"],
        "website_url": "https://www.nosler.com",
        "type_tags": ["bullet_maker", "ammo_maker", "rifle_maker"],
        "country": "USA",
        "notes": (
            "Invented the Partition bullet. Makes loaded ammo (Trophy Grade), component bullets (AccuBond LR, "
            "RDF, Custom Competition), brass, and the Model 21 rifle. Independent, based in Bend, OR."
        ),
    },
    {
        "name": "Sierra Bullets",
        "alt_names": ["Sierra", "Sierra Bullet"],
        "website_url": "https://www.sierrabullets.com",
        "type_tags": ["bullet_maker"],
        "country": "USA",
        "parent_company": "Bullseye Acquisitions / JDH Capital",
        "notes": (
            "MatchKing line is the precision standard. Sierra is NOT part of the CSG/Kinetic Group — sold by "
            "Clarus Corp to JDH Capital (Bullseye Acquisitions) in Dec 2023 for $175M. Same ownership group as "
            "Savage Arms and Barnes."
        ),
    },
    {
        "name": "Speer",
        "alt_names": ["Speer Ammunition", "Speer Ammo"],
        "website_url": "https://www.speer.com",
        "type_tags": ["bullet_maker", "ammo_maker"],
        "country": "USA",
        "parent_company": "Czechoslovak Group (CSG) / The Kinetic Group",
        "notes": (
            "Gold Dot line for duty/defense. Less relevant to precision/LR rifle market. Now owned by "
            "CSG/Kinetic Group (Nov 2024) after Vista Outdoor split."
        ),
    },
    # --- Ammo / Brass Makers ---
    {
        "name": "Alpha Munitions",
        "alt_names": ["Alpha", "Alpha Brass", "ADG", "Alpha Dog Gear"],
        "website_url": "https://www.alphamunitions.com",
        "type_tags": ["ammo_maker"],
        "country": "USA",
        "notes": (
            "Premium brass — with Lapua, accounts for 92% of top-200 PRS brass market. American-made in Salt "
            "Lake City, UT. Rapidly growing among competitive shooters."
        ),
    },
    {
        "name": "Black Hills Ammunition",
        "alt_names": ["Black Hills", "BHA", "BH Ammo", "Blackhills"],
        "website_url": "https://www.black-hills.com",
        "type_tags": ["ammo_maker"],
        "country": "USA",
        "notes": (
            "Premium loaded ammo favored by precision shooters. MK 262 Mod 1 military contract. 77gr TMK loads "
            "popular for AR precision. Independent, family-owned."
        ),
    },
    {
        "name": "IMI Systems",
        "alt_names": ["IMI", "IMI Ammunition", "Israeli Military Industries", "IMI Defense"],
        "website_url": "https://www.imisystems.com",
        "type_tags": ["ammo_maker"],
        "country": "Israel",
        "parent_company": "Elbit Systems",
        "notes": (
            "Military and commercial ammo. Razorcore line for precision. Owned by Elbit Systems since Nov 2018 "
            "(~$495M). Imported by various US distributors."
        ),
    },
    {
        "name": "Peterson Cartridge",
        "alt_names": ["Peterson", "Peterson Brass"],
        "website_url": "https://www.petersoncartridge.com",
        "type_tags": ["ammo_maker"],
        "country": "USA",
        "notes": (
            "Match-grade American-made brass specifically for long-range shooters. Based in Pittsburgh, PA. "
            "Known for extremely consistent weight/dimensions. Family-owned."
        ),
    },
    {
        "name": "Prvi Partizan",
        "alt_names": ["PPU", "Privi Partizan", "Privi", "Prvi"],
        "website_url": "https://www.prvipartizan.com",
        "type_tags": ["ammo_maker"],
        "country": "Serbia",
        "notes": (
            "Affordable brass-cased ammo. Popular for practice/training. Good quality for the price. Not a "
            "precision brand but widely used for volume shooting."
        ),
    },
    {
        "name": "Remington",
        "alt_names": ["Remington Arms", "Big Green", "Rem", "RemArms", "Remington 700"],
        "website_url": "https://www.remington.com",
        "type_tags": ["rifle_maker", "ammo_maker"],
        "country": "USA",
        "parent_company": "RemArms (rifles) / CSG (ammo)",
        "notes": (
            "Model 700 is the most common precision rifle action footprint (de facto standard). Post-2020 "
            "bankruptcy, firearms and ammo split. Remington Ammunition now under CSG/Kinetic Group. Rifles under "
            "RemArms (Roundhill Group)."
        ),
    },
    {
        "name": "Sellier & Bellot",
        "alt_names": ["S&B", "Sellier and Bellot", "Sellier Bellot"],
        "website_url": "https://www.sellier-bellot.cz",
        "type_tags": ["ammo_maker"],
        "country": "Czech Republic",
        "parent_company": "Colt CZ Group SE",
        "notes": (
            "One of the oldest ammo manufacturers (est. 1825). Owned by Colt CZ Group (acquired 2024 for $703M). "
            "Budget-friendly practice ammo. Not a primary precision brand but widely used for training."
        ),
    },
    {
        "name": "Starline Brass",
        "alt_names": ["Starline", "Starline Inc"],
        "website_url": "https://www.starlinebrass.com",
        "type_tags": ["ammo_maker"],
        "country": "USA",
        "notes": (
            "Nearly 50 years of brass production. Primarily handgun brass but expanding rifle offerings. Huge "
            "volume, good quality, very affordable. Independent."
        ),
    },
    {
        "name": "Winchester",
        "alt_names": ["Winchester Ammunition", "Win", "Olin Winchester"],
        "website_url": "https://www.winchester.com",
        "type_tags": ["ammo_maker"],
        "country": "USA",
        "parent_company": "Olin Corporation",
        "notes": (
            "Ammo manufactured by Olin Corporation. Brand name on many caliber designations (.308 Win, .270 Win, "
            "etc.). Olin/Winchester acquired AMMO Inc small-cal assets in Apr 2025. Match/precision ammo not a "
            "primary strength."
        ),
    },
    # --- Rifle Makers ---
    {
        "name": "Accuracy International",
        "alt_names": ["AI", "Accuracy Intl", "Accuracy Int'l"],
        "website_url": "https://www.accuracyinternational.com",
        "type_tags": ["rifle_maker"],
        "country": "United Kingdom",
        "notes": (
            "Military precision rifles (AXSR, AT-X). Used by military/LE worldwide. Premium price point. Less "
            "common in PRS (more tactical/military) but highly recognized. Founded 1978."
        ),
    },
    {
        "name": "Aero Precision",
        "alt_names": ["Aero", "Aero Precision USA", "AP"],
        "website_url": "https://www.aeroprecisionusa.com",
        "type_tags": ["rifle_maker"],
        "country": "USA",
        "notes": (
            "Major OEM supplier — makes receivers for many brands. M5 (.308/AR-10) and AR-15 lines are go-to for "
            "builders. Solus bolt-action line gaining traction in precision. Based in Tacoma, WA."
        ),
    },
    {
        "name": "Bergara",
        "alt_names": ["Bergara Rifles", "Bergara USA", "Bargara"],
        "website_url": "https://www.bergara.online/us",
        "type_tags": ["rifle_maker"],
        "country": "Spain",
        "notes": (
            "B-14 HMR is a benchmark for precision-for-the-money. Premier Competition Rifle (partnered with MPA "
            "chassis) gaining PRS traction. Known for hammer-forged barrel quality. Spanish barrel-making heritage."
        ),
    },
    {
        "name": "Bravo Company",
        "alt_names": ["BCM", "Bravo Company Manufacturing", "Bravo Company MFG"],
        "website_url": "https://www.bravocompanymfg.com",
        "type_tags": ["rifle_maker"],
        "country": "USA",
        "notes": (
            "Best value in duty-grade AR segment. Not competition-focused but hugely popular among serious "
            "shooters. RECCE-16 and MK2 lines."
        ),
    },
    {
        "name": "Browning",
        "alt_names": ["Browning Arms", "Browning Firearms"],
        "website_url": "https://www.browning.com",
        "type_tags": ["rifle_maker"],
        "country": "USA",
        "parent_company": "FN Herstal / Herstal Group",
        "notes": (
            "X-Bolt line is popular for hunting. X-Bolt Max Long Range is their precision-adjacent offering. "
            "Brand owned by FN Herstal (Belgium). Very large user base among hunters."
        ),
    },
    {
        "name": "CZ (Česká zbrojovka)",
        "alt_names": ["CZ", "CZ-USA", "Ceska Zbrojovka", "CZUB", "CZ Firearms"],
        "website_url": "https://www.cz-usa.com",
        "type_tags": ["rifle_maker"],
        "country": "Czech Republic",
        "parent_company": "Colt CZ Group SE",
        "notes": (
            "CZ 600 series with interchangeable barrels and sub-MOA guarantee. Also owns Colt. CZ 457 rimfire is "
            "widely used for trainer rifles. Cold hammer-forged barrels."
        ),
    },
    {
        "name": "Cadex Defence",
        "alt_names": ["Cadex", "Cadex Defense"],
        "website_url": "https://www.cadexdefence.com",
        "type_tags": ["rifle_maker", "chassis_maker"],
        "country": "Canada",
        "notes": (
            "Precision sniper rifles and chassis systems. CDX-MC Kraken multi-caliber rifle. Field Competition "
            "chassis used in PRS. Recoil management systems. Based in QC, Canada. Since 1994."
        ),
    },
    {
        "name": "Christensen Arms",
        "alt_names": ["Christensen", "CA", "Christenson Arms"],
        "website_url": "https://www.christensenarms.com",
        "type_tags": ["rifle_maker"],
        "country": "USA",
        "notes": (
            "Pioneer of carbon fiber barrel technology. Lightweight hunting and long-range precision rifles. MPR "
            "(Modern Precision Rifle) is their PRS-relevant model. 30th anniversary in 2025. Gunnison, UT."
        ),
    },
    {
        "name": "Curtis Custom",
        "alt_names": ["Curtis", "Curtis Actions"],
        "website_url": "https://www.curtiscustom.com",
        "type_tags": ["parts_maker", "rifle_maker"],
        "country": "USA",
        "notes": (
            "Custom actions (Valor, Axiom, Scout) and bespoke rifles. Premium quality. Texas-based. Requires FFL "
            "for shipping."
        ),
    },
    {
        "name": "Daniel Defense",
        "alt_names": ["DD", "Dan Def", "Daniel Defense Inc"],
        "website_url": "https://www.danieldefense.com",
        "type_tags": ["rifle_maker"],
        "country": "USA",
        "notes": (
            "Premium AR-15 and AR-10 maker. DDM4 series is benchmark for hard-use precision ARs. Cold "
            "hammer-forged barrels, most components in-house. Delta 5 bolt-action is their precision entry."
        ),
    },
    {
        "name": "Desert Tech",
        "alt_names": ["DT", "DesertTech", "Desert Tech SRS"],
        "website_url": "https://www.deserttech.com",
        "type_tags": ["rifle_maker"],
        "country": "USA",
        "notes": (
            "Bullpup precision rifles (SRS-A2, HTI). Compact form factor for precision shooting. MDR/MDRx lines "
            "discontinued 2024. Based in West Valley City, UT."
        ),
    },
    {
        "name": "GA Precision",
        "alt_names": ["GAP", "GA Prec", "George Gardner"],
        "website_url": "https://www.gaprecision.net",
        "type_tags": ["rifle_maker"],
        "country": "USA",
        "notes": (
            "Custom precision rifle builds by George Gardner. Consistently top-5 in PRS since inception (2012). "
            'FBI SWAT trusted. GAP is shorthand for "good enough for PRS." Kansas City area.'
        ),
    },
    {
        "name": "Geissele Automatics",
        "alt_names": ["Geissele", "Geisele", "Giesele", "Geissele Automatics LLC"],
        "website_url": "https://www.geissele.com",
        "type_tags": ["rifle_maker", "parts_maker"],
        "country": "USA",
        "notes": (
            "Known primarily for triggers (SSA-E is the gold standard AR trigger). Super Duty rifle is a "
            "benchmark premium AR. Most precision AR shooters have a Geissele trigger."
        ),
    },
    {
        "name": "Howa",
        "alt_names": ["Howa Machinery", "Howa 1500", "Howa USA"],
        "website_url": "https://www.howausa.com",
        "type_tags": ["rifle_maker"],
        "country": "Japan",
        "parent_company": "Howa Machinery Ltd (Japan)",
        "notes": (
            "Imported/distributed by Legacy Sports International in the US. Howa 1500 action is basis for many "
            "budget precision builds. Mini action popular in 6.5 Grendel builds."
        ),
    },
    {
        "name": "JP Enterprises",
        "alt_names": ["JP", "JPE", "JP Rifles"],
        "website_url": "https://www.jprifles.com",
        "type_tags": ["rifle_maker"],
        "country": "USA",
        "notes": (
            "Purpose-built competition gas guns. LRP-07 and CTR-02 are staples in PRS Gas Gun division. Known "
            "for tuned gas systems and match barrels."
        ),
    },
    {
        "name": "Knight's Armament",
        "alt_names": ["KAC", "Knight's", "Knights Armament", "Knight's Armament Company"],
        "website_url": "https://www.knightarmco.com",
        "type_tags": ["rifle_maker"],
        "country": "USA",
        "notes": (
            "SR-25 is the US military semi-auto precision platform (M110 SASS). SR-15 for 5.56. Extremely "
            "high-end, limited availability, cult following. Founded by Reed Knight."
        ),
    },
    {
        "name": "LWRC International",
        "alt_names": ["LWRC", "LWRCI"],
        "website_url": "https://www.lwrci.com",
        "type_tags": ["rifle_maker"],
        "country": "USA",
        "notes": (
            "Short-stroke piston ARs. REPR in .308 is a legitimate precision platform. Niche but respected among "
            "AR shooters."
        ),
    },
    {
        "name": "LaRue Tactical",
        "alt_names": ["LaRue", "Larue", "La Rue"],
        "website_url": "https://www.larue.com",
        "type_tags": ["rifle_maker"],
        "country": "USA",
        "notes": (
            "OBR (Optimized Battle Rifle) and PredatAR are legendary for accuracy. Often described as the most "
            "accurate factory AR. Cult following. MBT-2S trigger is a massive value play."
        ),
    },
    {
        "name": "Lewis Machine & Tool",
        "alt_names": ["LMT", "Lewis Machine", "LMT Defense"],
        "website_url": "https://www.lmtdefense.com",
        "type_tags": ["rifle_maker"],
        "country": "USA",
        "notes": (
            "Monolithic upper receiver design (MRP). .308 MWS is a respected precision platform. Quick-change "
            "barrel system. Military contracts worldwide (NZ, Estonia, UK)."
        ),
    },
    {
        "name": "Masterpiece Arms",
        "alt_names": ["MPA", "Masterpiece Arms Inc", "Master Piece Arms"],
        "website_url": "https://www.masterpiecearms.com",
        "type_tags": ["rifle_maker", "chassis_maker"],
        "country": "USA",
        "notes": (
            "Dominant PRS rifle/chassis brand. BA Comp chassis used by 29% of top-200 PRS shooters and 44% of "
            "top-25. MPA + Foundation + MDT = 79% of top PRS chassis market. Named official PRS chassis 5 "
            "consecutive years. Based in Comer, GA."
        ),
    },
    {
        "name": "Mossberg",
        "alt_names": ["O.F. Mossberg", "Mossberg & Sons"],
        "website_url": "https://www.mossberg.com",
        "type_tags": ["rifle_maker"],
        "country": "USA",
        "notes": (
            "Patriot line is a budget bolt-action option. MVP platform in 5.56/.308. Very large user base due to "
            "low pricing. Less precision-focused but many owners."
        ),
    },
    {
        "name": "Palmetto State Armory",
        "alt_names": ["PSA", "Palmetto", "Palmetto State"],
        "website_url": "https://www.palmettostatearmory.com",
        "type_tags": ["rifle_maker", "ammo_maker"],
        "country": "USA",
        "notes": (
            "Massive volume, aggressive pricing. Gen3 PA-10 in 6.5 CM is surprisingly capable. Also owns DAGR "
            "Arms and other brands. Sheer volume means many users will own one."
        ),
    },
    {
        "name": "Proof Research",
        "alt_names": ["Proof", "PROOF", "Proof Barrels"],
        "website_url": "https://www.proofresearch.com",
        "type_tags": ["rifle_maker", "parts_maker"],
        "country": "USA",
        "notes": (
            "Carbon fiber barrel technology (aerospace-grade). 12% of top PRS shooters use Proof barrels (2nd "
            "most popular after Bartlein). Conviction rifle system. NW Montana near Glacier."
        ),
    },
    {
        "name": "Ruger",
        "alt_names": ["Sturm Ruger", "Sturm Ruger & Co", "Ruger Firearms", "Rugar"],
        "website_url": "https://www.ruger.com",
        "type_tags": ["rifle_maker"],
        "country": "USA",
        "notes": (
            "Ruger Precision Rifle (RPR) was a game-changer — brought sub-$1500 chassis rifles to market. Huge "
            "install base among newer precision shooters. Also makes American Predator and Hawkeye lines."
        ),
    },
    {
        "name": "Sako",
        "alt_names": ["Sako Rifles", "Sako Finland", "Sakko"],
        "website_url": "https://www.sako.global",
        "type_tags": ["rifle_maker"],
        "country": "Finland",
        "parent_company": "Beretta Holding",
        "notes": (
            "Finnish precision bolt-action rifles. Makes Tikka rifles at their Riihimäki factory. TRG series is "
            "their precision/tactical line. Premium price point. Owned by Beretta since 2000."
        ),
    },
    {
        "name": "Savage Arms",
        "alt_names": ["Savage", "Savage Firearms", "Savage 110"],
        "website_url": "https://www.savagearms.com",
        "type_tags": ["rifle_maker"],
        "country": "USA",
        "parent_company": "Bullseye Acquisitions / JDH Capital",
        "notes": (
            "Model 110 platform is long-lived and accurate. AccuTrigger user-adjustable trigger was innovative. "
            "Impulse straight-pull gaining interest. Owned by JDH Capital (same group as Sierra, Barnes)."
        ),
    },
    {
        "name": "Seekins Precision",
        "alt_names": ["Seekins", "Seekins SP"],
        "website_url": "https://www.seekinsprecision.com",
        "type_tags": ["rifle_maker"],
        "country": "USA",
        "notes": (
            "Havak line well-regarded for factory precision bolt actions. SP10 for gas guns. HIT (Havak In "
            "Training) is an accessible entry. Based in Lewiston, ID."
        ),
    },
    {
        "name": "Sig Sauer",
        "alt_names": ["Sig", "SIG SAUER", "Sig Sauer Inc", "SIG"],
        "website_url": "https://www.sigsauer.com",
        "type_tags": ["optic_maker", "rifle_maker"],
        "country": "USA",
        "notes": (
            "Tango6T adopted by US Army (SDMR). Cross bolt-action rifle for hunting/precision. KILO rangefinders "
            "widely used. Large defense contractor. Based in Newington, NH."
        ),
    },
    {
        "name": "Tikka",
        "alt_names": ["Tikka Rifles", "Tikka T3x", "Tikka by Sako"],
        "website_url": "https://www.tikka.fi",
        "type_tags": ["rifle_maker"],
        "country": "Finland",
        "parent_company": "Beretta Group (via Sako)",
        "notes": (
            "Made by Sako (Beretta Group). T3x TAC A1 is popular precision chassis rifle. T3x CTR and Lite also "
            "widely used. Exceptional factory trigger. One of the most recommended entry precision rifles."
        ),
    },
    {
        "name": "Weatherby",
        "alt_names": ["Weatherby Inc", "Wby", "Weatherby Vanguard"],
        "website_url": "https://www.weatherby.com",
        "type_tags": ["rifle_maker", "ammo_maker"],
        "country": "USA",
        "notes": (
            "Known for proprietary magnum cartridges (.300 Wby Mag, .30-378 Wby). Mark V and Vanguard rifles. "
            "Vanguard is a rebranded Howa 1500. Recently moved HQ to Sheridan, WY."
        ),
    },
    # --- Chassis / Stock Makers ---
    {
        "name": "Area 419",
        "alt_names": ["Area419", "A419", "Area 419 LLC"],
        "website_url": "https://www.area419.com",
        "type_tags": ["parts_maker", "chassis_maker"],
        "country": "USA",
        "notes": (
            "Hellfire muzzle brake is PRS standard. ARCA rails, scope mounts, and accessories. XYLO chassis "
            "(American Rifle Co). Premium competition components. Major PRS retailer."
        ),
    },
    {
        "name": "Foundation Stocks",
        "alt_names": ["Foundation", "Foundation Rifle Stocks"],
        "website_url": "https://www.foundationstocks.com",
        "type_tags": ["chassis_maker"],
        "country": "USA",
        "notes": (
            "Top-3 PRS stock brand (with MPA and MDT = 79% of top chassis market). Genesis and Centurion models. "
            "Precision composite stocks machined from solid blocks."
        ),
    },
    {
        "name": "Grayboe",
        "alt_names": ["Grayboe Stocks"],
        "website_url": "https://www.grayboe.com",
        "type_tags": ["chassis_maker"],
        "country": "USA",
        "notes": "Fiberglass stocks (Ridgeback, Renegade). Affordable composite option. American-made.",
    },
    {
        "name": "KRG (Kinetic Research Group)",
        "alt_names": ["KRG", "Kinetic Research", "KRG Whiskey"],
        "website_url": "https://www.kineticresearchgroup.com",
        "type_tags": ["chassis_maker"],
        "country": "USA",
        "notes": (
            "Whiskey-3 Gen 7 and Bravo chassis are PRS staples. W3 is a top-5 chassis in PRS. AICS magazine "
            "compatible. High quality aluminum construction."
        ),
    },
    {
        "name": "MDT (Modular Driven Technologies)",
        "alt_names": ["MDT", "Modular Driven", "MDT Chassis", "Oryx by MDT"],
        "website_url": "https://www.mdttac.com",
        "type_tags": ["chassis_maker"],
        "country": "Canada",
        "notes": (
            "Top-3 PRS chassis brand (with MPA and Foundation = 79% of top PRS). ACC, ACC Elite, LSS-XL, and "
            "HNT26 lines. Also makes Oryx budget chassis. Based in Chilliwack, BC."
        ),
    },
    {
        "name": "Manners Composite Stocks",
        "alt_names": ["Manners", "Manners Stocks", "MCS"],
        "website_url": "https://www.mannersstocks.com",
        "type_tags": ["chassis_maker"],
        "country": "USA",
        "notes": (
            "Aerospace-grade carbon fiber stocks. PRS Series 2023 official stock sponsor. EH1 and TCS models "
            "popular in competition. Lifetime warranty."
        ),
    },
    {
        "name": "McMillan",
        "alt_names": ["McMillan Stocks", "McMillian", "McMillon", "McMillan USA"],
        "website_url": "https://www.mcmillanusa.com",
        "type_tags": ["chassis_maker"],
        "country": "USA",
        "notes": (
            "Iconic A5 and A4 stocks. Handcrafted fiberglass/carbon fiber since 1974. Heritage PRS brand, less "
            "dominant now but still respected. Founded by Gale McMillan."
        ),
    },
    {
        "name": "XLR Industries",
        "alt_names": ["XLR", "XLR Chassis"],
        "website_url": "https://www.xlrindustries.com",
        "type_tags": ["chassis_maker"],
        "country": "USA",
        "notes": (
            "American-made 6061 billet aluminum chassis. Element 4.0 and ENVY Pro. Element 4.0 Magnesium under 2 "
            "lbs. Established 2010."
        ),
    },
    # --- Optic Makers ---
    {
        "name": "Arken Optics",
        "alt_names": ["Arken", "Arken USA"],
        "website_url": "https://www.arkenopticsusa.com",
        "type_tags": ["optic_maker"],
        "country": "USA",
        "notes": (
            "Budget FFP scopes gaining popularity. EP5 5-25x is strong PRS entry-level value. Japanese glass, "
            "Chinese assembly. Texas-based brand."
        ),
    },
    {
        "name": "Athlon Optics",
        "alt_names": ["Athlon", "Athlon Optics USA"],
        "website_url": "https://www.athlonoptics.com",
        "type_tags": ["optic_maker"],
        "country": "USA",
        "notes": (
            "Cronus BTR (Japan-made) is their premium precision scope. Other lines from China. Strong value "
            "proposition. Lifetime warranty. Founded 2014."
        ),
    },
    {
        "name": "Bushnell",
        "alt_names": ["Bushnell Elite", "Bushnell Tactical", "Bushnell Optics"],
        "website_url": "https://www.bushnell.com",
        "type_tags": ["optic_maker"],
        "country": "USA",
        "parent_company": "Revelyst (formerly Vista Outdoor)",
        "notes": (
            "Elite Tactical line (XRS3, DMR3) relevant for precision. Owned by Vista Outdoor/Revelyst. Match Pro "
            "budget FFP scope is a strong value play."
        ),
    },
    {
        "name": "Element Optics",
        "alt_names": ["Element", "Element Optics USA"],
        "website_url": "https://www.element-optics.com",
        "type_tags": ["optic_maker"],
        "country": "USA",
        "notes": (
            "Budget-friendly premium scopes. Helix and Titan lines. Founded by Fredrik Axelsson (FX Airguns). "
            "Manufacturing in Sweden (Mariestad) and design in Utah. Growing fast."
        ),
    },
    {
        "name": "Kahles",
        "alt_names": ["Kahles Optics"],
        "website_url": "https://www.kahles.at",
        "type_tags": ["optic_maker"],
        "country": "Austria",
        "parent_company": "Swarovski Optik / Swarovski Group",
        "notes": (
            "Oldest riflescope manufacturer (est. 1898). K525i is highly regarded in PRS. Owned by Swarovski "
            "Optik since 1974. Austrian-made in Guntramsdorf."
        ),
    },
    {
        "name": "Leupold",
        "alt_names": ["Leupold & Stevens", "Leopold", "Leupold Optics"],
        "website_url": "https://www.leupold.com",
        "type_tags": ["optic_maker"],
        "country": "USA",
        "notes": (
            "Mark 5HD is the precision line. 19% of top PRS shooters (most popular brand by share, though "
            "declining from 22%). Long heritage in American optics. Made in Beaverton, OR."
        ),
    },
    {
        "name": "March Optics",
        "alt_names": ["March", "March Scopes", "DEON"],
        "website_url": "https://www.marchscopes.com",
        "type_tags": ["optic_maker"],
        "country": "Japan",
        "parent_company": "DEON Optical Design Corporation",
        "notes": (
            "Hand-built in Japan by DEON Optical Design. 30+ years optical design. 150+ parts all Japanese-made. "
            "20 quality inspections per scope. Popular in F-class and benchrest."
        ),
    },
    {
        "name": "Maven",
        "alt_names": ["Maven Optics", "Maven Built"],
        "website_url": "https://www.mavenbuilt.com",
        "type_tags": ["optic_maker"],
        "country": "USA",
        "notes": (
            "Direct-to-consumer model, Japanese glass. RS.4 5-30x is their precision rifle scope. Custom builder "
            "(color/engraving options). Based in Lander, WY."
        ),
    },
    {
        "name": "Nightforce Optics",
        "alt_names": ["Nightforce", "NF", "Night Force"],
        "website_url": "https://www.nightforceoptics.com",
        "type_tags": ["optic_maker"],
        "country": "USA",
        "parent_company": "Lightforce Performance Lighting (Australia)",
        "notes": (
            "ATACR 7-35x56 F1 is the fan favorite — all top-50 PRS shooters using NF run this model. 13% of top "
            "PRS shooters. Only brand in top-5 PRS optics for 10 consecutive years. Parent: Lightforce "
            "(Australia)."
        ),
    },
    {
        "name": "Revic",
        "alt_names": ["Revic Optics", "Revic PMR"],
        "website_url": "https://www.revicoptics.com",
        "type_tags": ["optic_maker"],
        "country": "USA",
        "parent_company": "Gunwerks (related)",
        "notes": (
            "Smart scopes with integrated ballistic engines. Acura RS25i and Radikl RS25b. Sister company to "
            "Gunwerks. Interesting tech for app integration."
        ),
    },
    {
        "name": "Schmidt & Bender",
        "alt_names": ["S&B Optics", "Schmidt Bender", "Schmidt and Bender", "Schmidt und Bender"],
        "website_url": "https://www.schmidtundbender.de/en",
        "type_tags": ["optic_maker"],
        "country": "Germany",
        "notes": (
            "Ultra-premium German optics for military/LE/hunting. PM II series is military precision standard. "
            "Family-owned since 1957. In-house production."
        ),
    },
    {
        "name": "Steiner",
        "alt_names": ["Steiner Optics", "Steiner Germany"],
        "website_url": "https://www.steiner-optics.com",
        "type_tags": ["optic_maker"],
        "country": "Germany",
        "parent_company": "Beretta Holding",
        "notes": (
            "Military and hunting optics. T6Xi tactical line relevant for precision. German technology, Beretta "
            "Group owned since 2008. M8Xi is their precision competition entry."
        ),
    },
    {
        "name": "Swarovski Optik",
        "alt_names": ["Swarovski", "Swarovski Optics", "Swaro"],
        "website_url": "https://www.swarovskioptik.com",
        "type_tags": ["optic_maker"],
        "country": "Austria",
        "parent_company": "Swarovski Group",
        "notes": (
            "Ultra-premium hunting optics. dS and X5(i) lines. Less common in PRS competition but gold standard "
            "for hunting glass. Owns Kahles brand. Made in Absam, Austria since 1949."
        ),
    },
    {
        "name": "Tangent Theta",
        "alt_names": ["TT", "Tangent Theta Inc", "TangentTheta"],
        "website_url": "https://www.tangenttheta.com",
        "type_tags": ["optic_maker"],
        "country": "Canada",
        "notes": (
            "17% of top PRS shooters (surging — grew from 4% to 20% in ~5 years). Tool-less Re-Zero feature. No "
            "manufacturer sponsorships — shooters choose freely. German glass. Made in Halifax, NS."
        ),
    },
    {
        "name": "US Optics",
        "alt_names": ["USO", "US Optics Inc"],
        "website_url": "https://www.usoptics.com",
        "type_tags": ["optic_maker"],
        "country": "USA",
        "notes": (
            "Hand-assembled custom riflescopes. LPVO pioneers. Foundation series (Buy American Act compliant). "
            "Since 1991, Rutherford College, NC."
        ),
    },
    {
        "name": "Vortex Optics",
        "alt_names": ["Vortex", "Vortex Optics Inc", "Vortx"],
        "website_url": "https://www.vortexoptics.com",
        "type_tags": ["optic_maker"],
        "country": "USA",
        "notes": (
            "Dominant precision optics brand by volume. Viper PST Gen II is PRS entry-level standard. Razor HD "
            "Gen III is competition-grade. Unconditional lifetime VIP warranty. Based in Barneveld, WI."
        ),
    },
    {
        "name": "Zero Compromise Optics",
        "alt_names": ["ZCO", "Zero Compromise", "ZC Optics"],
        "website_url": "https://www.zcompoptic.com",
        "type_tags": ["optic_maker"],
        "country": "Austria",
        "notes": (
            "Ultra-premium optics. ZC527 is considered among the best precision scopes available. Small batch. "
            "Design/testing in Orofino, ID; manufacturing in Austria. Founded 2018."
        ),
    },
    # --- Parts / Components ---
    {
        "name": "Bartlein Barrels",
        "alt_names": ["Bartlein", "Bartlien"],
        "website_url": "https://www.bartleinbarrels.com",
        "type_tags": ["parts_maker"],
        "country": "USA",
        "notes": (
            "49% of top PRS shooters use Bartlein barrels — more than the next 10 brands combined. Cut-rifled, "
            "single-point, 5R rifling options. The undisputed dominant PRS barrel maker."
        ),
    },
    {
        "name": "Criterion Barrels",
        "alt_names": ["Criterion", "Criterion Arms"],
        "website_url": "https://www.criterionbarrels.com",
        "type_tags": ["parts_maker"],
        "country": "USA",
        "notes": (
            "AR-platform and bolt-action barrels. CORE series for bolt guns. Hybrid profile is popular for "
            "precision AR builds. Button-rifled. Good value."
        ),
    },
    {
        "name": "Defiance Machine",
        "alt_names": ["Defiance", "Defiance Actions"],
        "website_url": "https://www.defiancemachine.com",
        "type_tags": ["parts_maker"],
        "country": "USA",
        "notes": (
            "Custom bolt-action receivers (actions). Tenacity, Deviant, Rebel, Ruckus series. Widely used by PRS "
            "gunsmiths for custom builds. Columbia Falls, MT."
        ),
    },
    {
        "name": "Impact Precision",
        "alt_names": ["Impact", "Impact 737", "IP"],
        "website_url": "https://www.impactprecision.com",
        "type_tags": ["parts_maker"],
        "country": "USA",
        "notes": (
            "737R action used by 57% of top-ranked PRS shooters — 3x more than any other brand. $1,470 MSRP "
            "(lowest among top actions). Dominant in PRS competition."
        ),
    },
    {
        "name": "Timney Triggers",
        "alt_names": ["Timney", "Timney Mfg"],
        "website_url": "https://www.timneytriggers.com",
        "type_tags": ["parts_maker"],
        "country": "USA",
        "notes": (
            "Precision aftermarket triggers for 75+ years. CNC machined, hand-tested. Rem 700, Ruger, Savage, AR "
            "platforms. Phoenix, AZ. Founded 1946."
        ),
    },
    {
        "name": "TriggerTech",
        "alt_names": ["Trigger Tech", "TriggerTech Inc"],
        "website_url": "https://www.triggertech.com",
        "type_tags": ["parts_maker"],
        "country": "Canada",
        "notes": (
            "Zero Creep Technology triggers. Rem 700, Tikka, and AR platforms. Acquired Hawkins Precision "
            "(2025), expanding product portfolio. Toronto-based."
        ),
    },
    {
        "name": "Zermatt Arms",
        "alt_names": ["Bighorn Arms", "Bighorn", "Bighorn Origin", "Zermatt"],
        "website_url": "https://www.zermattarms.com",
        "type_tags": ["parts_maker"],
        "country": "USA",
        "notes": (
            "Bighorn Origin action — Rem 700 footprint with Savage barrel compatibility. Popular for budget "
            "precision builds. Acquired Bighorn Arms in 2015. Bennett, NE."
        ),
    },
    # --- Data / Device Providers ---
    {
        "name": "Applied Ballistics",
        "alt_names": ["AB", "Applied Ballistics LLC", "AB Ballistics"],
        "website_url": "https://www.appliedballisticsllc.com",
        "type_tags": ["data_provider"],
        "country": "USA",
        "notes": (
            "Bryan Litz. Doppler-measured BC data and custom drag models. Gold standard for BC values. "
            "Integrated into Kestrel meters, many ballistic apps. Mobile lab with doppler radar in west-central "
            "MI."
        ),
    },
    {
        "name": "Garmin",
        "alt_names": ["Garmin Xero", "Garmin Ltd"],
        "website_url": "https://www.garmin.com",
        "type_tags": ["data_provider"],
        "country": "USA",
        "notes": (
            "Xero L60i laser rangefinder (7,000m range, ±0.25m accuracy) with Applied Ballistics integration. "
            "Xero X1i crossbow scope. Not a core precision brand but Xero is widely used."
        ),
    },
    {
        "name": "Kestrel Ballistics",
        "alt_names": ["Kestrel", "Kestrel Meters", "Kestrel 5700"],
        "website_url": "https://www.kestrelballistics.com",
        "type_tags": ["data_provider"],
        "country": "USA",
        "notes": (
            "Weather meters with Applied Ballistics integration. Kestrel 5700 Elite is THE standard tool for "
            "precision shooters — measures temp, pressure, humidity, wind. MIL-STD-810G rated."
        ),
    },
]


# ---------------------------------------------------------------------------
# Caliber seed data
# Source: design proposal MVP scope + ammo_db_research_notes.md §7 + domain
#         expert review (2026-02-20). Rankings revised per PRS equipment surveys.
# Dimensional data from SAAMI reference tables unless noted otherwise.
# ---------------------------------------------------------------------------

CALIBERS = [
    # --- Rank 1: 6.5 Creedmoor ---
    {
        "name": "6.5 Creedmoor",
        "alt_names": ["6.5 CM", "6.5 Creed", "6.5mm Creedmoor"],
        "bullet_diameter_inches": 0.264,
        "case_length_inches": 1.920,
        "coal_inches": 2.825,
        "max_pressure_psi": 62000,
        "rim_type": "rimless",
        "action_length": "short",
        "year_introduced": 2007,
        "is_common_lr": True,
        "lr_popularity_rank": 1,
        "description": (
            "The dominant precision rifle cartridge. Excellent ballistics in a short-action package with mild recoil."
        ),
    },
    # --- Rank 2: .308 Winchester ---
    {
        "name": ".308 Winchester",
        "alt_names": [".308 Win", "308", "7.62x51mm NATO"],
        "bullet_diameter_inches": 0.308,
        "case_length_inches": 2.015,
        "coal_inches": 2.810,
        "max_pressure_psi": 62000,
        "rim_type": "rimless",
        "action_length": "short",
        "year_introduced": 1952,
        "is_common_lr": True,
        "lr_popularity_rank": 2,
        "description": "The benchmark short-action cartridge. Universal availability, wide bullet selection.",
    },
    # --- Rank 3: 6mm Dasher (NEW — ~46% of top PRS shooters) ---
    {
        "name": "6mm Dasher",
        "alt_names": ["6 Dasher", "Dasher"],
        "bullet_diameter_inches": 0.243,
        "case_length_inches": 1.560,
        "coal_inches": 2.350,
        "rim_type": "rimless",
        "action_length": "short",
        "year_introduced": 2000,
        "is_common_lr": True,
        "lr_popularity_rank": 3,
        "description": "The dominant PRS competition cartridge (~46% of top shooters). Semi-wildcat turned mainstream.",
        "notes": (
            "No official SAAMI spec. Pressure ~58,000 PSI estimated from community load data. "
            "Based on 6mm BR case with 40-degree shoulder."
        ),
    },
    # --- Rank 4: 6mm GT (NEW — ~11% of top PRS shooters) ---
    {
        "name": "6mm GT",
        "alt_names": ["6GT"],
        "bullet_diameter_inches": 0.243,
        "case_length_inches": 1.800,
        "coal_inches": 2.750,
        "rim_type": "rimless",
        "action_length": "short",
        "year_introduced": 2019,
        "is_common_lr": True,
        "lr_popularity_rank": 4,
        "description": (
            "PRS competition cartridge designed by George Gardner (GA Precision) and Tom Jacobs. "
            "Small primer, 35-degree shoulder. Optimized for gas and bolt gun competition."
        ),
        "notes": "No official SAAMI spec. Pressure ~62,000 PSI estimated from community load data.",
    },
    # --- Rank 5: 6mm Creedmoor ---
    {
        "name": "6mm Creedmoor",
        "alt_names": ["6mm CM", "6 CM", "6 Creedmoor"],
        "bullet_diameter_inches": 0.243,
        "case_length_inches": 1.920,
        "coal_inches": 2.800,
        "max_pressure_psi": 62000,
        "rim_type": "rimless",
        "action_length": "short",
        "year_introduced": 2017,
        "is_common_lr": True,
        "lr_popularity_rank": 5,
        "description": "6.5 CM necked down to 6mm. Popular in PRS competition for lower recoil.",
    },
    # --- Rank 6: .223 Remington ---
    {
        "name": ".223 Remington",
        "alt_names": [".223 Rem", "223"],
        "bullet_diameter_inches": 0.224,
        "case_length_inches": 1.760,
        "coal_inches": 2.260,
        "max_pressure_psi": 55000,
        "rim_type": "rimless",
        "action_length": "mini",
        "year_introduced": 1964,
        "is_common_lr": False,
        "lr_popularity_rank": 6,
        "description": "The commercial counterpart to 5.56 NATO. Lower pressure spec than 5.56.",
    },
    # --- Rank 7: 5.56x45mm NATO ---
    {
        "name": "5.56x45mm NATO",
        "alt_names": ["5.56 NATO", "5.56", "5.56x45"],
        "bullet_diameter_inches": 0.224,
        "case_length_inches": 1.760,
        "coal_inches": 2.260,
        "max_pressure_psi": 62000,
        "rim_type": "rimless",
        "action_length": "mini",
        "is_common_lr": False,
        "lr_popularity_rank": 7,
        "description": "Military specification. Higher pressure and longer throat than .223 Rem.",
        "notes": (
            "MAP measured via NATO EPVAT (conformal transducer, case mouth) — not directly comparable "
            "to SAAMI piezo specs. Actual chamber pressure is similar to .223 Rem."
        ),
    },
    # --- Rank 8: .300 Winchester Magnum ---
    {
        "name": ".300 Winchester Magnum",
        "alt_names": [".300 Win Mag", "300WM", ".300 WM"],
        "bullet_diameter_inches": 0.308,
        "case_length_inches": 2.620,
        "coal_inches": 3.340,
        "max_pressure_psi": 64000,
        "rim_type": "belted",
        "action_length": "long",
        "year_introduced": 1963,
        "is_common_lr": True,
        "lr_popularity_rank": 8,
        "description": "Classic long-range magnum. Widely used in military sniper and competitive ELR.",
    },
    # --- Rank 9: .300 PRC ---
    {
        "name": ".300 PRC",
        "alt_names": [".300 Precision Rifle Cartridge"],
        "bullet_diameter_inches": 0.308,
        "case_length_inches": 2.580,
        "coal_inches": 3.700,
        "max_pressure_psi": 65000,
        "rim_type": "rimless",
        "action_length": "magnum",
        "year_introduced": 2018,
        "is_common_lr": True,
        "lr_popularity_rank": 9,
        "description": "Modern magnum designed around long, high-BC .30-cal bullets. USSOCOM adoption. Hornady design.",
    },
    # --- Rank 10: 6.5 PRC ---
    {
        "name": "6.5 PRC",
        "alt_names": ["6.5 Precision Rifle Cartridge"],
        "bullet_diameter_inches": 0.264,
        "case_length_inches": 2.030,
        "coal_inches": 2.955,
        "max_pressure_psi": 65000,
        "rim_type": "rimless",
        "action_length": "short",
        "year_introduced": 2018,
        "is_common_lr": True,
        "lr_popularity_rank": 10,
        "description": (
            "Short-magnum performance for 6.5mm bullets. ~200 fps faster than 6.5 CM. Popular for NRL Hunter."
        ),
    },
    # --- Rank 11: 7mm PRC ---
    {
        "name": "7mm PRC",
        "alt_names": ["7mm Precision Rifle Cartridge"],
        "bullet_diameter_inches": 0.284,
        "case_length_inches": 2.280,
        "coal_inches": 2.955,
        "max_pressure_psi": 65000,
        "rim_type": "rimless",
        "action_length": "short",
        "year_introduced": 2022,
        "is_common_lr": True,
        "lr_popularity_rank": 11,
        "description": "Modern short-action 7mm designed for long, high-BC bullets. Hornady design. Growing fast.",
    },
    # --- Rank 12: .338 Lapua Magnum ---
    {
        "name": ".338 Lapua Magnum",
        "alt_names": [".338 Lapua", "338LM", ".338 LM"],
        "bullet_diameter_inches": 0.338,
        "case_length_inches": 2.724,
        "coal_inches": 3.681,
        "max_pressure_psi": 60916,
        "rim_type": "rimless",
        "action_length": "magnum",
        "year_introduced": 1989,
        "is_common_lr": True,
        "lr_popularity_rank": 12,
        "description": "The ELR standard. Military and competition use at 1500+ yards.",
        "notes": "MAP of 60,916 PSI is CIP conversion from 4,200 bar (4200 x 14.5038).",
    },
    # --- Rank 13: .270 Winchester ---
    {
        "name": ".270 Winchester",
        "alt_names": [".270 Win", "270"],
        "bullet_diameter_inches": 0.277,
        "case_length_inches": 2.540,
        "coal_inches": 3.340,
        "max_pressure_psi": 65000,
        "rim_type": "rimless",
        "action_length": "long",
        "year_introduced": 1925,
        "is_common_lr": False,
        "lr_popularity_rank": 13,
        "description": "Classic hunting cartridge. One of the most popular deer cartridges in North America.",
    },
    # --- Rank 14: .30-06 Springfield ---
    {
        "name": ".30-06 Springfield",
        "alt_names": [".30-06", "30-06", "thirty-aught-six", ".30-06 Sprg"],
        "bullet_diameter_inches": 0.308,
        "case_length_inches": 2.494,
        "coal_inches": 3.340,
        "max_pressure_psi": 60000,
        "rim_type": "rimless",
        "action_length": "long",
        "year_introduced": 1906,
        "is_common_lr": False,
        "lr_popularity_rank": 14,
        "description": "The original American long-action cartridge. Parent case for many modern cartridges.",
    },
    # --- Rank 15: 7mm Remington Magnum ---
    {
        "name": "7mm Remington Magnum",
        "alt_names": ["7mm Rem Mag", "7mm Mag"],
        "bullet_diameter_inches": 0.284,
        "case_length_inches": 2.500,
        "coal_inches": 3.290,
        "max_pressure_psi": 61000,
        "rim_type": "belted",
        "action_length": "long",
        "year_introduced": 1962,
        "is_common_lr": True,
        "lr_popularity_rank": 15,
        "description": "Classic long-range hunting magnum. Being displaced by 7mm PRC.",
    },
    # --- Rank 16: .260 Remington ---
    {
        "name": ".260 Remington",
        "alt_names": [".260 Rem", "260"],
        "bullet_diameter_inches": 0.264,
        "case_length_inches": 2.035,
        "coal_inches": 2.800,
        "max_pressure_psi": 60000,
        "rim_type": "rimless",
        "action_length": "short",
        "year_introduced": 1997,
        "is_common_lr": False,
        "lr_popularity_rank": 16,
        "description": "The 6.5mm short-action predecessor to 6.5 Creedmoor. Largely displaced by 6.5 CM.",
    },
    # --- Rank 17: 7.62x51mm NATO ---
    {
        "name": "7.62x51mm NATO",
        "alt_names": ["7.62 NATO", "7.62x51"],
        "bullet_diameter_inches": 0.308,
        "case_length_inches": 2.015,
        "coal_inches": 2.810,
        "max_pressure_psi": 58000,
        "rim_type": "rimless",
        "action_length": "short",
        "is_common_lr": False,
        "lr_popularity_rank": 17,
        "description": "Military counterpart to .308 Win. Thicker brass, slightly lower pressure.",
        "notes": "Practically interchangeable with .308 Win in modern rifles, but technically distinct.",
    },
    # --- Rank 18: .243 Winchester ---
    {
        "name": ".243 Winchester",
        "alt_names": [".243 Win", "243"],
        "bullet_diameter_inches": 0.243,
        "case_length_inches": 2.045,
        "coal_inches": 2.710,
        "max_pressure_psi": 60000,
        "rim_type": "rimless",
        "action_length": "short",
        "year_introduced": 1955,
        "is_common_lr": False,
        "lr_popularity_rank": 18,
        "description": "Versatile short-action cartridge. Popular for deer and varmint.",
    },
    # --- Rank 19: .300 Winchester Short Magnum ---
    {
        "name": ".300 Winchester Short Magnum",
        "alt_names": [".300 WSM", "300WSM"],
        "bullet_diameter_inches": 0.308,
        "case_length_inches": 2.100,
        "coal_inches": 2.860,
        "max_pressure_psi": 65000,
        "rim_type": "rimless",
        "action_length": "short",
        "year_introduced": 2001,
        "is_common_lr": True,
        "lr_popularity_rank": 19,
        "description": "Near-.300 Win Mag performance in a short-action package.",
    },
    # --- Rank 20: 7mm-08 Remington ---
    {
        "name": "7mm-08 Remington",
        "alt_names": ["7mm-08", "7mm-08 Rem"],
        "bullet_diameter_inches": 0.284,
        "case_length_inches": 2.035,
        "coal_inches": 2.800,
        "max_pressure_psi": 61000,
        "rim_type": "rimless",
        "action_length": "short",
        "year_introduced": 1980,
        "is_common_lr": False,
        "lr_popularity_rank": 20,
        "description": "Mild-recoiling short-action 7mm. Good hunting cartridge for recoil-sensitive shooters.",
    },
    # --- Rank 21: 6.5x55mm Swedish ---
    {
        "name": "6.5x55mm Swedish",
        "alt_names": ["6.5x55 Swede", "6.5x55 SE", "6.5 Swede"],
        "bullet_diameter_inches": 0.264,
        "case_length_inches": 2.165,
        "coal_inches": 3.150,
        "max_pressure_psi": 46000,
        "rim_type": "rimless",
        "action_length": "long",
        "year_introduced": 1894,
        "is_common_lr": False,
        "lr_popularity_rank": 21,
        "description": "Venerable Scandinavian cartridge. Low SAAMI pressure due to older rifles in service.",
    },
    # --- Rank 22: .300 AAC Blackout ---
    {
        "name": ".300 AAC Blackout",
        "alt_names": [".300 BLK", "300 Blackout", ".300 Blackout"],
        "bullet_diameter_inches": 0.308,
        "case_length_inches": 1.368,
        "coal_inches": 2.260,
        "max_pressure_psi": 55000,
        "rim_type": "rimless",
        "action_length": "mini",
        "year_introduced": 2011,
        "is_common_lr": False,
        "lr_popularity_rank": 22,
        "description": "Designed for suppressed AR-15s. Subsonic and supersonic loads. Zero LR relevance.",
    },
    # --- Rank 23: .338 Winchester Magnum ---
    {
        "name": ".338 Winchester Magnum",
        "alt_names": [".338 Win Mag"],
        "bullet_diameter_inches": 0.338,
        "case_length_inches": 2.500,
        "coal_inches": 3.340,
        "max_pressure_psi": 64000,
        "rim_type": "belted",
        "action_length": "long",
        "year_introduced": 1958,
        "is_common_lr": False,
        "lr_popularity_rank": 23,
        "description": "Versatile medium-bore magnum. Popular for large game. Being displaced by .338 Lapua.",
    },
    # --- Rank 24: 6mm ARC (NEW — AR-15 precision) ---
    {
        "name": "6mm ARC",
        "alt_names": ["6mm Advanced Rifle Cartridge", "6 ARC"],
        "bullet_diameter_inches": 0.243,
        "case_length_inches": 1.490,
        "coal_inches": 2.260,
        "max_pressure_psi": 52000,
        "rim_type": "rimless",
        "action_length": "mini",
        "year_introduced": 2020,
        "is_common_lr": True,
        "lr_popularity_rank": 24,
        "description": "Hornady's AR-15 precision cartridge. Growing in NRL22/mid-range competition.",
    },
    # --- Rank 25: 6.5-284 Norma ---
    {
        "name": "6.5-284 Norma",
        "alt_names": ["6.5-284", "6.5x284"],
        "bullet_diameter_inches": 0.264,
        "case_length_inches": 2.170,
        "coal_inches": 3.228,
        "max_pressure_psi": 58740,
        "rim_type": "rebated",
        "action_length": "long",
        "year_introduced": 1999,
        "is_common_lr": True,
        "lr_popularity_rank": 25,
        "description": (
            "Legacy precision cartridge still used in F-Class competition. Known for barrel-burning velocities."
        ),
    },
]


# ---------------------------------------------------------------------------
# Chamber seed data
#
# Strategy: most chambers are 1:1 mirrors of their caliber. We generate those
# automatically. Then we manually define the handful that need special curation:
#   - .223 Wylde (chamber-only, no caliber — accepts both .223 and 5.56)
#   - 5.56 NATO (accepts 5.56 and .223)
#   - .308 Win / 7.62x51 NATO (bidirectional — each accepts the other)
#
# The "auto-generated" chambers get a single primary caliber link.
# The manually curated ones get explicit multi-caliber links.
# ---------------------------------------------------------------------------

# Calibers that get a simple 1:1 chamber (chamber name = caliber name)
AUTO_CHAMBER_CALIBERS = [
    "6.5 Creedmoor",
    "6mm Dasher",
    "6mm GT",
    "6mm Creedmoor",
    ".300 Winchester Magnum",
    ".300 PRC",
    "6.5 PRC",
    "7mm PRC",
    ".338 Lapua Magnum",
    ".270 Winchester",
    ".30-06 Springfield",
    "7mm Remington Magnum",
    ".260 Remington",
    ".243 Winchester",
    "6.5x55mm Swedish",
    ".300 Winchester Short Magnum",
    ".300 AAC Blackout",
    ".338 Winchester Magnum",
    "7mm-08 Remington",
    "6mm ARC",
    "6.5-284 Norma",
]

# Manually curated chambers with multi-caliber relationships
MANUAL_CHAMBERS = [
    {
        "name": ".223 Remington",
        "notes": "Commercial .223 chamber. Accepts .223 Rem ONLY — do not fire 5.56 NATO.",
        "source": "SAAMI spec",
        "accepts": [
            {"caliber_name": ".223 Remington", "is_primary": True},
        ],
    },
    {
        "name": "5.56 NATO",
        "alt_names": ["5.56x45mm NATO"],
        "notes": "Military 5.56 chamber with longer throat / leade. Safe to fire both 5.56 and .223 Rem.",
        "source": "NATO STANAG",
        "accepts": [
            {"caliber_name": "5.56x45mm NATO", "is_primary": True},
            {"caliber_name": ".223 Remington", "is_primary": False},
        ],
    },
    {
        "name": ".223 Wylde",
        "notes": (
            "Hybrid chamber designed to safely fire both .223 Rem and 5.56 NATO "
            "while maintaining .223 Rem accuracy. No corresponding cartridge exists — "
            "this is a chamber-only specification. The most popular AR-15 chamber for precision use."
        ),
        "source": "Industry standard (Bill Wylde design)",
        "accepts": [
            {"caliber_name": ".223 Remington", "is_primary": True},
            {"caliber_name": "5.56x45mm NATO", "is_primary": False},
        ],
    },
    {
        "name": ".308 Winchester",
        "notes": (
            "Commercial .308 Win chamber. Universally considered safe to fire 7.62x51 NATO "
            "(lower pressure) in modern rifles. Every major firearms reference treats these as "
            "interchangeable."
        ),
        "source": "SAAMI spec",
        "accepts": [
            {"caliber_name": ".308 Winchester", "is_primary": True},
            {"caliber_name": "7.62x51mm NATO", "is_primary": False},
        ],
    },
    {
        "name": "7.62x51mm NATO",
        "alt_names": ["7.62 NATO"],
        "notes": "Military 7.62 chamber. Accepts both 7.62x51 and .308 Win in modern rifles.",
        "source": "NATO STANAG",
        "accepts": [
            {"caliber_name": "7.62x51mm NATO", "is_primary": True},
            {"caliber_name": ".308 Winchester", "is_primary": False},
        ],
    },
]


# ---------------------------------------------------------------------------
# Platform seed data
# Source: domain expert review (2026-02-27)
# ---------------------------------------------------------------------------

PLATFORMS = [
    {
        "name": "Bolt Action",
        "short_name": "bolt",
        "description": (
            "Traditional bolt-action rifles. Most flexible platform — "
            "can be chambered in virtually any cartridge. Action length "
            "(short, long, magnum) is the main constraint."
        ),
    },
    {
        "name": "AR-15",
        "short_name": "ar15",
        "description": (
            "AR-15 pattern rifles. Limited by the AR-15 magazine well "
            "and bolt face diameter. Typically mini/short-action cartridges "
            "with max OAL ~2.260\"."
        ),
    },
    {
        "name": "AR-10",
        "short_name": "ar10",
        "description": (
            "AR-10 / SR-25 / LR-308 pattern rifles. Larger magwell than AR-15. "
            "Handles .308-class cartridges. Also known as DPMS or ArmaLite pattern."
        ),
    },
]


# Caliber-to-platform mappings with per-platform popularity ranking.
# A row means "this caliber is available on this platform."
# popularity_rank is relative within each platform (1 = most popular).
#
# Source: domain expert review, PRS/NRL competition data, manufacturer
#         offerings, community consensus (2026-02-27)

CALIBER_PLATFORMS = [
    # --- Bolt Action ---
    # Bolt guns can chamber almost anything. Rankings reflect precision/LR
    # community popularity, not overall sales volume.
    {"caliber_name": "6.5 Creedmoor", "platform": "bolt", "rank": 1},
    {"caliber_name": ".308 Winchester", "platform": "bolt", "rank": 2},
    {"caliber_name": "6mm Dasher", "platform": "bolt", "rank": 3},
    {"caliber_name": "6mm GT", "platform": "bolt", "rank": 4},
    {"caliber_name": "6mm Creedmoor", "platform": "bolt", "rank": 5},
    {"caliber_name": ".223 Remington", "platform": "bolt", "rank": 6},
    {"caliber_name": "5.56x45mm NATO", "platform": "bolt", "rank": 7},
    {"caliber_name": ".300 Winchester Magnum", "platform": "bolt", "rank": 8},
    {"caliber_name": ".300 PRC", "platform": "bolt", "rank": 9},
    {"caliber_name": "6.5 PRC", "platform": "bolt", "rank": 10},
    {"caliber_name": "7mm PRC", "platform": "bolt", "rank": 11},
    {"caliber_name": ".338 Lapua Magnum", "platform": "bolt", "rank": 12},
    {"caliber_name": ".270 Winchester", "platform": "bolt", "rank": 13},
    {"caliber_name": ".30-06 Springfield", "platform": "bolt", "rank": 14},
    {"caliber_name": "7mm Remington Magnum", "platform": "bolt", "rank": 15},
    {"caliber_name": ".260 Remington", "platform": "bolt", "rank": 16},
    {"caliber_name": "7.62x51mm NATO", "platform": "bolt", "rank": 17},
    {"caliber_name": ".243 Winchester", "platform": "bolt", "rank": 18},
    {"caliber_name": ".300 Winchester Short Magnum", "platform": "bolt", "rank": 19},
    {"caliber_name": "7mm-08 Remington", "platform": "bolt", "rank": 20},
    {"caliber_name": "6.5x55mm Swedish", "platform": "bolt", "rank": 21},
    {"caliber_name": ".338 Winchester Magnum", "platform": "bolt", "rank": 22},
    {"caliber_name": "6.5-284 Norma", "platform": "bolt", "rank": 23},
    # --- AR-15 ---
    # AR-15 is constrained to cartridges that fit the AR-15 magwell
    # (max OAL ~2.260") and use an AR-15-size bolt face.
    {"caliber_name": ".223 Remington", "platform": "ar15", "rank": 1},
    {"caliber_name": "5.56x45mm NATO", "platform": "ar15", "rank": 2},
    {"caliber_name": ".300 AAC Blackout", "platform": "ar15", "rank": 3},
    {"caliber_name": "6mm ARC", "platform": "ar15", "rank": 4},
    # --- AR-10 ---
    # AR-10 handles .308-class short-action cartridges.
    {"caliber_name": "6.5 Creedmoor", "platform": "ar10", "rank": 1},
    {"caliber_name": ".308 Winchester", "platform": "ar10", "rank": 2},
    {"caliber_name": "7.62x51mm NATO", "platform": "ar10", "rank": 3},
    {"caliber_name": "6mm Creedmoor", "platform": "ar10", "rank": 4},
    {"caliber_name": ".260 Remington", "platform": "ar10", "rank": 5},
    {"caliber_name": ".243 Winchester", "platform": "ar10", "rank": 6},
    {"caliber_name": "6.5 PRC", "platform": "ar10", "rank": 7, "notes": "Requires dedicated large-bolt AR-10 upper (e.g. POF Revolution)."},
]


# ---------------------------------------------------------------------------
# EntityAlias seed data
# Source: design proposal addendum §4 + ammo_db_research_notes.md §5 +
#         domain expert review (2026-02-20)
# ---------------------------------------------------------------------------

ENTITY_ALIASES: list[dict] = [
    # --- Caliber aliases: 6.5 Creedmoor ---
    {"entity_type": "caliber", "entity_name": "6.5 Creedmoor", "alias": "6.5 Creedmore", "alias_type": "misspelling"},
    {"entity_type": "caliber", "entity_name": "6.5 Creedmoor", "alias": "6.5 Crdmr", "alias_type": "abbreviation"},
    {"entity_type": "caliber", "entity_name": "6.5 Creedmoor", "alias": "Creadmoor", "alias_type": "misspelling"},
    # --- Caliber aliases: .308 Winchester ---
    {
        "entity_type": "caliber",
        "entity_name": ".308 Winchester",
        "alias": "7.62x51 NATO",
        "alias_type": "military_designation",
    },
    {"entity_type": "caliber", "entity_name": ".308 Winchester", "alias": ".308", "alias_type": "abbreviation"},
    {
        "entity_type": "caliber",
        "entity_name": ".308 Winchester",
        "alias": "308 Winchestor",
        "alias_type": "misspelling",
    },
    # --- Caliber aliases: 6mm Dasher (new) ---
    {"entity_type": "caliber", "entity_name": "6mm Dasher", "alias": "6 Dasher", "alias_type": "abbreviation"},
    # --- Caliber aliases: 6mm GT (new) ---
    {"entity_type": "caliber", "entity_name": "6mm GT", "alias": "6GT", "alias_type": "abbreviation"},
    # --- Caliber aliases: 6mm Creedmoor ---
    {"entity_type": "caliber", "entity_name": "6mm Creedmoor", "alias": "6CM", "alias_type": "abbreviation"},
    {"entity_type": "caliber", "entity_name": "6mm Creedmoor", "alias": "6 Creed", "alias_type": "nickname"},
    # --- Caliber aliases: .223 Remington ---
    {"entity_type": "caliber", "entity_name": ".223 Remington", "alias": ".223", "alias_type": "abbreviation"},
    # --- Caliber aliases: 5.56x45mm NATO ---
    {"entity_type": "caliber", "entity_name": "5.56x45mm NATO", "alias": "5.56", "alias_type": "abbreviation"},
    # --- Caliber aliases: .300 Winchester Magnum ---
    {
        "entity_type": "caliber",
        "entity_name": ".300 Winchester Magnum",
        "alias": ".300 WinMag",
        "alias_type": "abbreviation",
    },
    {"entity_type": "caliber", "entity_name": ".300 Winchester Magnum", "alias": "300WM", "alias_type": "abbreviation"},
    {
        "entity_type": "caliber",
        "entity_name": ".300 Winchester Magnum",
        "alias": ".300 WM",
        "alias_type": "abbreviation",
    },
    # --- Caliber aliases: .300 PRC ---
    {"entity_type": "caliber", "entity_name": ".300 PRC", "alias": "300 PRC", "alias_type": "alternate_name"},
    # --- Caliber aliases: 6.5 PRC ---
    {"entity_type": "caliber", "entity_name": "6.5 PRC", "alias": "6.5PRC", "alias_type": "abbreviation"},
    # --- Caliber aliases: 7mm PRC ---
    {"entity_type": "caliber", "entity_name": "7mm PRC", "alias": "7PRC", "alias_type": "abbreviation"},
    {"entity_type": "caliber", "entity_name": "7mm PRC", "alias": "7 PRC", "alias_type": "abbreviation"},
    # --- Caliber aliases: .338 Lapua Magnum ---
    {
        "entity_type": "caliber",
        "entity_name": ".338 Lapua Magnum",
        "alias": ".338 Lapua Mag",
        "alias_type": "abbreviation",
    },
    {"entity_type": "caliber", "entity_name": ".338 Lapua Magnum", "alias": "338LM", "alias_type": "abbreviation"},
    {"entity_type": "caliber", "entity_name": ".338 Lapua Magnum", "alias": "Lapua Mag", "alias_type": "nickname"},
    {"entity_type": "caliber", "entity_name": ".338 Lapua Magnum", "alias": "338 Lap", "alias_type": "abbreviation"},
    # --- Caliber aliases: .270 Winchester ---
    {"entity_type": "caliber", "entity_name": ".270 Winchester", "alias": ".270", "alias_type": "abbreviation"},
    # --- Caliber aliases: .30-06 Springfield ---
    {
        "entity_type": "caliber",
        "entity_name": ".30-06 Springfield",
        "alias": "thirty-aught-six",
        "alias_type": "nickname",
    },
    {
        "entity_type": "caliber",
        "entity_name": ".30-06 Springfield",
        "alias": ".30-06 Sprg",
        "alias_type": "abbreviation",
    },
    {"entity_type": "caliber", "entity_name": ".30-06 Springfield", "alias": "30.06", "alias_type": "misspelling"},
    {"entity_type": "caliber", "entity_name": ".30-06 Springfield", "alias": "3006", "alias_type": "abbreviation"},
    # --- Caliber aliases: 7mm Remington Magnum ---
    {"entity_type": "caliber", "entity_name": "7mm Remington Magnum", "alias": "7RM", "alias_type": "abbreviation"},
    {"entity_type": "caliber", "entity_name": "7mm Remington Magnum", "alias": "7mm RM", "alias_type": "abbreviation"},
    # --- Caliber aliases: .243 Winchester ---
    {"entity_type": "caliber", "entity_name": ".243 Winchester", "alias": ".243", "alias_type": "abbreviation"},
    {"entity_type": "caliber", "entity_name": ".243 Winchester", "alias": "243 Win", "alias_type": "abbreviation"},
    # --- Caliber aliases: .300 AAC Blackout ---
    {"entity_type": "caliber", "entity_name": ".300 AAC Blackout", "alias": "300BLK", "alias_type": "abbreviation"},
    {"entity_type": "caliber", "entity_name": ".300 AAC Blackout", "alias": "300 BO", "alias_type": "abbreviation"},
    # --- Caliber aliases: .300 WSM ---
    {
        "entity_type": "caliber",
        "entity_name": ".300 Winchester Short Magnum",
        "alias": "300WSM",
        "alias_type": "abbreviation",
    },
    # --- Caliber aliases: 6.5x55mm Swedish ---
    {"entity_type": "caliber", "entity_name": "6.5x55mm Swedish", "alias": "6.5 Swede", "alias_type": "nickname"},
    # --- Caliber aliases: 6mm ARC (new) ---
    {"entity_type": "caliber", "entity_name": "6mm ARC", "alias": "6ARC", "alias_type": "abbreviation"},
    # --- Caliber aliases: 6.5-284 Norma (new) ---
    {"entity_type": "caliber", "entity_name": "6.5-284 Norma", "alias": "6.5-284", "alias_type": "abbreviation"},
    # --- Manufacturer aliases (misspellings & abbreviations beyond alt_names) ---
    # NOTE: alt_names on the Manufacturer model cover the primary aliases.
    # EntityAlias captures additional pipeline-side aliases (misspellings, abbreviations, nicknames)
    # that help with search/entity-resolution but don't need to be in the bundled DB.
    {"entity_type": "manufacturer", "entity_name": "Hornady", "alias": "Hornaday", "alias_type": "misspelling"},
    {"entity_type": "manufacturer", "entity_name": "Berger Bullets", "alias": "Burger", "alias_type": "misspelling"},
    {"entity_type": "manufacturer", "entity_name": "Berger Bullets", "alias": "Berger", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "Federal Premium", "alias": "Federal", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "Sierra Bullets", "alias": "Sierra", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "Sierra Bullets", "alias": "Seirra", "alias_type": "misspelling"},
    {"entity_type": "manufacturer", "entity_name": "Barnes Bullets", "alias": "Barnes", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "Savage Arms", "alias": "Savage", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "Remington", "alias": "Rem", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "Remington", "alias": "Big Green", "alias_type": "nickname"},
    {"entity_type": "manufacturer", "entity_name": "Lapua", "alias": "Lupua", "alias_type": "misspelling"},
    {"entity_type": "manufacturer", "entity_name": "Nosler", "alias": "Nossler", "alias_type": "misspelling"},
    {"entity_type": "manufacturer", "entity_name": "Masterpiece Arms", "alias": "MPA", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "Seekins Precision", "alias": "Seekins", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "Black Hills Ammunition", "alias": "Black Hills", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "Black Hills Ammunition", "alias": "BHA", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "Black Hills Ammunition", "alias": "Blackhills", "alias_type": "misspelling"},
    {"entity_type": "manufacturer", "entity_name": "Sellier & Bellot", "alias": "S&B", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "IMI Systems", "alias": "IMI", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "Prvi Partizan", "alias": "PPU", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "Prvi Partizan", "alias": "Privi", "alias_type": "misspelling"},
    {"entity_type": "manufacturer", "entity_name": "Daniel Defense", "alias": "DD", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "Knight's Armament", "alias": "KAC", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "JP Enterprises", "alias": "JP", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "LaRue Tactical", "alias": "LaRue", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "Aero Precision", "alias": "Aero", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "Bravo Company", "alias": "BCM", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "Lewis Machine & Tool", "alias": "LMT", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "Palmetto State Armory", "alias": "PSA", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "Geissele Automatics", "alias": "Geissele", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "Geissele Automatics", "alias": "Geisele", "alias_type": "misspelling"},
    {"entity_type": "manufacturer", "entity_name": "Geissele Automatics", "alias": "Giesele", "alias_type": "misspelling"},
    {"entity_type": "manufacturer", "entity_name": "LWRC International", "alias": "LWRC", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "Nightforce Optics", "alias": "Nightforce", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "Nightforce Optics", "alias": "NF", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "Leupold", "alias": "Leopold", "alias_type": "misspelling"},
    {"entity_type": "manufacturer", "entity_name": "Vortex Optics", "alias": "Vortex", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "Vortex Optics", "alias": "Vortx", "alias_type": "misspelling"},
    {"entity_type": "manufacturer", "entity_name": "Zero Compromise Optics", "alias": "ZCO", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "Sig Sauer", "alias": "Sig", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "Ruger", "alias": "Rugar", "alias_type": "misspelling"},
    {"entity_type": "manufacturer", "entity_name": "Bergara", "alias": "Bargara", "alias_type": "misspelling"},
    {"entity_type": "manufacturer", "entity_name": "Tikka", "alias": "Tikka by Sako", "alias_type": "alternate_name"},
    # --- New manufacturer aliases ---
    {"entity_type": "manufacturer", "entity_name": "Cutting Edge Bullets", "alias": "CEB", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "Alpha Munitions", "alias": "Alpha", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "Alpha Munitions", "alias": "ADG", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "Accuracy International", "alias": "AI", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "Christensen Arms", "alias": "Christensen", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "Christensen Arms", "alias": "Christenson Arms", "alias_type": "misspelling"},
    {"entity_type": "manufacturer", "entity_name": "CZ (Česká zbrojovka)", "alias": "CZ", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "CZ (Česká zbrojovka)", "alias": "CZ-USA", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "Cadex Defence", "alias": "Cadex", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "GA Precision", "alias": "GAP", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "Desert Tech", "alias": "DT", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "Proof Research", "alias": "Proof", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "Impact Precision", "alias": "Impact", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "Defiance Machine", "alias": "Defiance", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "Zermatt Arms", "alias": "Bighorn", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "MDT (Modular Driven Technologies)", "alias": "MDT", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "KRG (Kinetic Research Group)", "alias": "KRG", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "Foundation Stocks", "alias": "Foundation", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "McMillan", "alias": "McMillian", "alias_type": "misspelling"},
    {"entity_type": "manufacturer", "entity_name": "McMillan", "alias": "McMillon", "alias_type": "misspelling"},
    {"entity_type": "manufacturer", "entity_name": "Manners Composite Stocks", "alias": "Manners", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "XLR Industries", "alias": "XLR", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "Area 419", "alias": "Area419", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "Area 419", "alias": "A419", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "Tangent Theta", "alias": "TT", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "Schmidt & Bender", "alias": "S&B Optics", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "Bartlein Barrels", "alias": "Bartlein", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "Bartlein Barrels", "alias": "Bartlien", "alias_type": "misspelling"},
    {"entity_type": "manufacturer", "entity_name": "Criterion Barrels", "alias": "Criterion", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "TriggerTech", "alias": "Trigger Tech", "alias_type": "alternate_name"},
    {"entity_type": "manufacturer", "entity_name": "Timney Triggers", "alias": "Timney", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "Kestrel Ballistics", "alias": "Kestrel", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "Applied Ballistics", "alias": "AB", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "Sako", "alias": "Sakko", "alias_type": "misspelling"},
    {"entity_type": "manufacturer", "entity_name": "Weatherby", "alias": "Wby", "alias_type": "abbreviation"},
]


# ---------------------------------------------------------------------------
# Bullet seed data
# Source: manufacturer product pages, Applied Ballistics data
# Focus: 6.5 Creedmoor and .308 Winchester — the two priority calibers
# ---------------------------------------------------------------------------

BULLETS: list[dict] = [
    # --- 6.5 Creedmoor Bullets (0.264" diameter) ---
    {
        "manufacturer_name": "Hornady",
        "name": "ELD Match",
        "alt_names": ["ELDM", "ELD-M"],
        "sku": "26331",
        "caliber_name": "6.5 Creedmoor",
        "weight_grains": 140.0,
        "bc_g1_published": 0.646,
        "bc_g7_published": 0.326,
        "bc_g7_estimated": 0.321,
        "bc_source_notes": "G7 estimated from Applied Ballistics, 2023 edition",
        "length_inches": 1.376,
        "sectional_density": 0.287,
        "type_tags": ["boat-tail", "polymer-tip", "cup-and-core"],
        "used_for": ["match"],
        "base_type": "boat-tail",
        "tip_type": "polymer-tip",
        "construction": "cup-and-core",
        "source_url": "https://www.hornady.com/bullets/eld-match/6.5mm-264-140-gr-eld-match",
    },
    {
        "manufacturer_name": "Hornady",
        "name": "ELD Match",
        "alt_names": ["ELDM 147", "ELD-M 147"],
        "sku": "26333",
        "caliber_name": "6.5 Creedmoor",
        "weight_grains": 147.0,
        "bc_g1_published": 0.697,
        "bc_g7_published": 0.351,
        "bc_source_notes": "Hornady published values",
        "length_inches": 1.445,
        "sectional_density": 0.301,
        "type_tags": ["boat-tail", "polymer-tip", "cup-and-core"],
        "used_for": ["match"],
        "base_type": "boat-tail",
        "tip_type": "polymer-tip",
        "construction": "cup-and-core",
        "source_url": "https://www.hornady.com/bullets/eld-match/6.5mm-264-147-gr-eld-match",
    },
    {
        "manufacturer_name": "Hornady",
        "name": "ELD-X",
        "alt_names": ["ELDX"],
        "sku": "2635",
        "caliber_name": "6.5 Creedmoor",
        "weight_grains": 143.0,
        "bc_g1_published": 0.625,
        "bc_g7_published": 0.315,
        "bc_source_notes": "Hornady published values",
        "sectional_density": 0.293,
        "type_tags": ["boat-tail", "polymer-tip", "cup-and-core"],
        "used_for": ["hunting-big-game"],
        "base_type": "boat-tail",
        "tip_type": "polymer-tip",
        "construction": "cup-and-core",
        "source_url": "https://www.hornady.com/bullets/eld-x/6.5mm-264-143-gr-eld-x",
    },
    {
        "manufacturer_name": "Sierra Bullets",
        "name": "MatchKing HPBT",
        "alt_names": ["SMK 140", "MatchKing 140"],
        "sku": "1740",
        "caliber_name": "6.5 Creedmoor",
        "weight_grains": 140.0,
        "bc_g1_published": 0.535,
        "bc_g7_published": 0.273,
        "bc_g7_estimated": 0.264,
        "bc_source_notes": "G1 is Sierra's stepped average. G7 estimated from Applied Ballistics.",
        "sectional_density": 0.287,
        "type_tags": ["boat-tail", "open-tip", "cup-and-core"],
        "used_for": ["match"],
        "base_type": "boat-tail",
        "tip_type": "open-tip",
        "construction": "cup-and-core",
        "source_url": "https://www.sierrabullets.com/product/6-5mm-140-gr-matchking/",
    },
    {
        "manufacturer_name": "Berger Bullets",
        "name": "Hybrid Target",
        "alt_names": ["Hybrid 140"],
        "sku": "26414",
        "caliber_name": "6.5 Creedmoor",
        "weight_grains": 140.0,
        "bc_g1_published": 0.607,
        "bc_g7_published": 0.311,
        "bc_g7_estimated": 0.307,
        "bc_source_notes": "G7 estimated from Applied Ballistics, 2023 edition",
        "sectional_density": 0.287,
        "type_tags": ["boat-tail", "open-tip", "cup-and-core"],
        "used_for": ["match"],
        "base_type": "boat-tail",
        "tip_type": "open-tip",
        "construction": "cup-and-core",
        "source_url": "https://www.bergerbullets.com/products/6-5mm-140-gr-hybrid-target/",
    },
    {
        "manufacturer_name": "Nosler",
        "name": "RDF",
        "alt_names": ["RDF 140"],
        "sku": "49823",
        "caliber_name": "6.5 Creedmoor",
        "weight_grains": 140.0,
        "bc_g1_published": 0.658,
        "bc_g7_published": 0.334,
        "bc_source_notes": "Nosler published values",
        "sectional_density": 0.287,
        "type_tags": ["boat-tail", "open-tip", "cup-and-core"],
        "used_for": ["match"],
        "base_type": "boat-tail",
        "tip_type": "open-tip",
        "construction": "cup-and-core",
        "source_url": "https://www.nosler.com/rdf-bullets",
    },
    {
        "manufacturer_name": "Lapua",
        "name": "Scenar-L",
        "alt_names": ["Scenar-L 140"],
        "sku": "4PL6050",
        "caliber_name": "6.5 Creedmoor",
        "weight_grains": 140.0,
        "bc_g1_published": 0.607,
        "bc_g7_published": 0.312,
        "bc_source_notes": "Lapua published values",
        "sectional_density": 0.287,
        "type_tags": ["boat-tail", "open-tip", "cup-and-core"],
        "used_for": ["match"],
        "base_type": "boat-tail",
        "tip_type": "open-tip",
        "construction": "cup-and-core",
        "source_url": "https://www.lapua.com/product/6-5mm-scenar-l-gb546-8-10g-140gr/",
    },
    {
        "manufacturer_name": "Barnes Bullets",
        "name": "LRX",
        "alt_names": ["LRX 127"],
        "sku": "30228",
        "caliber_name": "6.5 Creedmoor",
        "weight_grains": 127.0,
        "bc_g1_published": 0.530,
        "bc_g7_published": 0.271,
        "bc_source_notes": "Barnes published values",
        "sectional_density": 0.260,
        "type_tags": ["boat-tail", "polymer-tip", "monolithic", "lead-free"],
        "used_for": ["hunting-big-game"],
        "base_type": "boat-tail",
        "tip_type": "polymer-tip",
        "construction": "monolithic",
        "is_lead_free": True,
        "source_url": "https://www.barnesbullets.com/product/lrx-long-range-x/",
    },
    # --- .308 Winchester Bullets (0.308" diameter) ---
    {
        "manufacturer_name": "Sierra Bullets",
        "name": "MatchKing HPBT",
        "alt_names": ["SMK 175", "MatchKing 175"],
        "sku": "2275",
        "caliber_name": ".308 Winchester",
        "weight_grains": 175.0,
        "bc_g1_published": 0.505,
        "bc_g7_published": 0.259,
        "bc_g7_estimated": 0.253,
        "bc_source_notes": "G7 estimated from Applied Ballistics. The M118LR bullet.",
        "sectional_density": 0.264,
        "type_tags": ["boat-tail", "open-tip", "cup-and-core"],
        "used_for": ["match", "tactical"],
        "base_type": "boat-tail",
        "tip_type": "open-tip",
        "construction": "cup-and-core",
        "source_url": "https://www.sierrabullets.com/product/30-cal-175-gr-matchking/",
    },
    {
        "manufacturer_name": "Sierra Bullets",
        "name": "MatchKing HPBT",
        "alt_names": ["SMK 168", "MatchKing 168"],
        "sku": "2200",
        "caliber_name": ".308 Winchester",
        "weight_grains": 168.0,
        "bc_g1_published": 0.462,
        "bc_g7_published": 0.236,
        "bc_g7_estimated": 0.230,
        "bc_source_notes": "The classic M852 bullet. G7 estimated from Applied Ballistics.",
        "sectional_density": 0.253,
        "type_tags": ["boat-tail", "open-tip", "cup-and-core"],
        "used_for": ["match"],
        "base_type": "boat-tail",
        "tip_type": "open-tip",
        "construction": "cup-and-core",
        "source_url": "https://www.sierrabullets.com/product/30-cal-168-gr-matchking/",
    },
    {
        "manufacturer_name": "Hornady",
        "name": "ELD Match",
        "alt_names": ["ELDM 178", "ELD-M 178"],
        "sku": "30713",
        "caliber_name": ".308 Winchester",
        "weight_grains": 178.0,
        "bc_g1_published": 0.547,
        "bc_g7_published": 0.275,
        "bc_source_notes": "Hornady published values",
        "sectional_density": 0.268,
        "type_tags": ["boat-tail", "polymer-tip", "cup-and-core"],
        "used_for": ["match"],
        "base_type": "boat-tail",
        "tip_type": "polymer-tip",
        "construction": "cup-and-core",
        "source_url": "https://www.hornady.com/bullets/eld-match/30-cal-308-178-gr-eld-match",
    },
    {
        "manufacturer_name": "Hornady",
        "name": "ELD Match",
        "alt_names": ["ELDM 168 .308"],
        "sku": "30506",
        "caliber_name": ".308 Winchester",
        "weight_grains": 168.0,
        "bc_g1_published": 0.523,
        "bc_g7_published": 0.266,
        "bc_source_notes": "Hornady published values",
        "sectional_density": 0.253,
        "type_tags": ["boat-tail", "polymer-tip", "cup-and-core"],
        "used_for": ["match"],
        "base_type": "boat-tail",
        "tip_type": "polymer-tip",
        "construction": "cup-and-core",
        "source_url": "https://www.hornady.com/bullets/eld-match/30-cal-308-168-gr-eld-match",
    },
    {
        "manufacturer_name": "Berger Bullets",
        "name": "Hybrid Target",
        "alt_names": ["Hybrid 185"],
        "sku": "30428",
        "caliber_name": ".308 Winchester",
        "weight_grains": 185.0,
        "bc_g1_published": 0.569,
        "bc_g7_published": 0.292,
        "bc_g7_estimated": 0.283,
        "bc_source_notes": "G7 estimated from Applied Ballistics, 2023 edition",
        "sectional_density": 0.279,
        "type_tags": ["boat-tail", "open-tip", "cup-and-core"],
        "used_for": ["match"],
        "base_type": "boat-tail",
        "tip_type": "open-tip",
        "construction": "cup-and-core",
        "source_url": "https://www.bergerbullets.com/products/30-cal-185-gr-hybrid-target/",
    },
    {
        "manufacturer_name": "Nosler",
        "name": "Custom Competition",
        "alt_names": ["CC 168"],
        "sku": "49824",
        "caliber_name": ".308 Winchester",
        "weight_grains": 168.0,
        "bc_g1_published": 0.462,
        "bc_g7_published": 0.236,
        "bc_source_notes": "Nosler published values",
        "sectional_density": 0.253,
        "type_tags": ["boat-tail", "open-tip", "cup-and-core"],
        "used_for": ["match"],
        "base_type": "boat-tail",
        "tip_type": "open-tip",
        "construction": "cup-and-core",
        "source_url": "https://www.nosler.com/custom-competition-bullets",
    },
    {
        "manufacturer_name": "Hornady",
        "name": "A-Tip Match",
        "alt_names": ["A-Tip 230"],
        "sku": "3091",
        "caliber_name": ".308 Winchester",
        "weight_grains": 230.0,
        "bc_g1_published": 0.823,
        "bc_g7_published": 0.414,
        "bc_source_notes": "Hornady published values. Extremely high BC heavy subsonic/ELR bullet.",
        "sectional_density": 0.346,
        "type_tags": ["boat-tail", "aluminum-tip", "cup-and-core"],
        "used_for": ["match"],
        "base_type": "boat-tail",
        "tip_type": "aluminum-tip",
        "construction": "cup-and-core",
        "source_url": "https://www.hornady.com/bullets/a-tip/30-cal-308-230-gr-a-tip-match",
    },
]


# ---------------------------------------------------------------------------
# BulletBCSource seed data — proves the multi-source pattern
# Source: manufacturer published vs Applied Ballistics measured
# ---------------------------------------------------------------------------

BULLET_BC_SOURCES: list[dict] = [
    # Hornady 140 ELD Match — manufacturer published G7
    {
        "bullet_sku": "26331",
        "bc_type": "g7",
        "bc_value": 0.326,
        "source": "manufacturer",
        "source_url": "https://www.hornady.com/bullets/eld-match/6.5mm-264-140-gr-eld-match",
        "notes": "Hornady published G7 BC",
    },
    # Hornady 140 ELD Match — Applied Ballistics measured G7
    {
        "bullet_sku": "26331",
        "bc_type": "g7",
        "bc_value": 0.321,
        "source": "applied_ballistics",
        "source_url": "https://www.appliedballisticsllc.com",
        "source_quality": 0.95,
        "notes": "Applied Ballistics Doppler-measured G7 BC, 2023 edition",
    },
    # Hornady 140 ELD Match — manufacturer published G1
    {
        "bullet_sku": "26331",
        "bc_type": "g1",
        "bc_value": 0.646,
        "source": "manufacturer",
        "source_url": "https://www.hornady.com/bullets/eld-match/6.5mm-264-140-gr-eld-match",
        "notes": "Hornady published G1 BC",
    },
    # Sierra 175 SMK — manufacturer published G7
    {
        "bullet_sku": "2275",
        "bc_type": "g7",
        "bc_value": 0.259,
        "source": "manufacturer",
        "source_url": "https://www.sierrabullets.com/product/30-cal-175-gr-matchking/",
        "notes": "Sierra published G7 BC (from stepped velocity average)",
    },
    # Sierra 175 SMK — Applied Ballistics measured G7
    {
        "bullet_sku": "2275",
        "bc_type": "g7",
        "bc_value": 0.253,
        "source": "applied_ballistics",
        "source_url": "https://www.appliedballisticsllc.com",
        "source_quality": 0.95,
        "notes": "Applied Ballistics Doppler-measured G7 BC",
    },
    # Berger 140 Hybrid Target — manufacturer published G7
    {
        "bullet_sku": "26414",
        "bc_type": "g7",
        "bc_value": 0.311,
        "source": "manufacturer",
        "source_url": "https://www.bergerbullets.com/products/6-5mm-140-gr-hybrid-target/",
        "notes": "Berger published G7 BC",
    },
    # Berger 140 Hybrid Target — Applied Ballistics measured G7
    {
        "bullet_sku": "26414",
        "bc_type": "g7",
        "bc_value": 0.307,
        "source": "applied_ballistics",
        "source_url": "https://www.appliedballisticsllc.com",
        "source_quality": 0.95,
        "notes": "Applied Ballistics Doppler-measured G7 BC, 2023 edition",
    },
]


# ---------------------------------------------------------------------------
# Cartridge seed data — factory loads referencing the bullets above
# Source: manufacturer product pages
# ---------------------------------------------------------------------------

CARTRIDGES: list[dict] = [
    # --- 6.5 Creedmoor Cartridges ---
    {
        "manufacturer_name": "Hornady",
        "product_line": "Match",
        "name": "Hornady 6.5 Creedmoor 140 gr ELD Match",
        "alt_names": ["Hornady Match 6.5 CM 140 ELDM"],
        "sku": "81500",
        "caliber_name": "6.5 Creedmoor",
        "bullet_sku": "26331",
        "bullet_weight_grains": 140.0,
        "muzzle_velocity_fps": 2710,
        "test_barrel_length_inches": 24.0,
        "round_count": 20,
        "bullet_match_method": "manual",
        "bullet_match_confidence": 1.0,
        "popularity_rank": 1,
        "source_url": "https://www.hornady.com/ammunition/rifle/6.5-creedmoor-140-gr-eld-match",
    },
    {
        "manufacturer_name": "Hornady",
        "product_line": "Match",
        "name": "Hornady 6.5 Creedmoor 147 gr ELD Match",
        "alt_names": ["Hornady Match 6.5 CM 147 ELDM"],
        "sku": "81501",
        "caliber_name": "6.5 Creedmoor",
        "bullet_sku": "26333",
        "bullet_weight_grains": 147.0,
        "muzzle_velocity_fps": 2695,
        "test_barrel_length_inches": 24.0,
        "round_count": 20,
        "bullet_match_method": "manual",
        "bullet_match_confidence": 1.0,
        "popularity_rank": 2,
        "source_url": "https://www.hornady.com/ammunition/rifle/6.5-creedmoor-147-gr-eld-match",
    },
    {
        "manufacturer_name": "Hornady",
        "product_line": "Precision Hunter",
        "name": "Hornady 6.5 Creedmoor 143 gr ELD-X",
        "alt_names": ["Hornady PH 6.5 CM 143 ELDX"],
        "sku": "81499",
        "caliber_name": "6.5 Creedmoor",
        "bullet_sku": "2635",
        "bullet_weight_grains": 143.0,
        "muzzle_velocity_fps": 2700,
        "test_barrel_length_inches": 24.0,
        "round_count": 20,
        "bullet_match_method": "manual",
        "bullet_match_confidence": 1.0,
        "popularity_rank": 3,
        "source_url": "https://www.hornady.com/ammunition/rifle/6.5-creedmoor-143-gr-eld-x",
    },
    {
        "manufacturer_name": "Federal Premium",
        "product_line": "Gold Medal",
        "name": "Federal Gold Medal 6.5 Creedmoor 140 gr SMK",
        "alt_names": ["Federal GMM 6.5 CM 140", "GM65CRD1"],
        "sku": "GM65CRD1",
        "caliber_name": "6.5 Creedmoor",
        "bullet_sku": "1740",
        "bullet_weight_grains": 140.0,
        "muzzle_velocity_fps": 2700,
        "test_barrel_length_inches": 24.0,
        "round_count": 20,
        "bullet_match_method": "manual",
        "bullet_match_confidence": 1.0,
        "popularity_rank": 4,
        "source_url": "https://www.federalpremium.com/rifle/gold-medal/gold-medal-sierra-matchking/11-GM65CRD1.html",
    },
    {
        "manufacturer_name": "Federal Premium",
        "product_line": "Gold Medal",
        "name": "Federal Gold Medal 6.5 Creedmoor 130 gr Berger Hybrid",
        "alt_names": ["Federal GMM 6.5 CM 130 Berger"],
        "sku": "GM65CRDBH130",
        "caliber_name": "6.5 Creedmoor",
        "bullet_sku": "26414",
        "bullet_weight_grains": 130.0,
        "muzzle_velocity_fps": 2875,
        "test_barrel_length_inches": 24.0,
        "round_count": 20,
        "bullet_match_method": "manual",
        "bullet_match_confidence": 0.8,
        "popularity_rank": 5,
        "source_url": "https://www.federalpremium.com/rifle/gold-medal/gold-medal-berger-hybrid/",
        "notes": "Uses 130gr Berger Hybrid OTM, not the 140gr Hybrid Target in our bullet table.",
    },
    {
        "manufacturer_name": "Nosler",
        "product_line": "Match Grade",
        "name": "Nosler Match Grade 6.5 Creedmoor 140 gr RDF",
        "alt_names": ["Nosler MG 6.5 CM 140 RDF"],
        "sku": "43455",
        "caliber_name": "6.5 Creedmoor",
        "bullet_sku": "49823",
        "bullet_weight_grains": 140.0,
        "muzzle_velocity_fps": 2650,
        "test_barrel_length_inches": 24.0,
        "round_count": 20,
        "bullet_match_method": "manual",
        "bullet_match_confidence": 1.0,
        "source_url": "https://www.nosler.com/match-grade-ammunition",
    },
    # --- .308 Winchester Cartridges ---
    {
        "manufacturer_name": "Federal Premium",
        "product_line": "Gold Medal",
        "name": "Federal Gold Medal .308 Win 175 gr SMK",
        "alt_names": ["Federal GMM 308 175", "GM308M2"],
        "sku": "GM308M2",
        "caliber_name": ".308 Winchester",
        "bullet_sku": "2275",
        "bullet_weight_grains": 175.0,
        "muzzle_velocity_fps": 2600,
        "test_barrel_length_inches": 24.0,
        "round_count": 20,
        "bullet_match_method": "manual",
        "bullet_match_confidence": 1.0,
        "popularity_rank": 1,
        "source_url": "https://www.federalpremium.com/rifle/gold-medal/gold-medal-sierra-matchking/11-GM308M2.html",
    },
    {
        "manufacturer_name": "Federal Premium",
        "product_line": "Gold Medal",
        "name": "Federal Gold Medal .308 Win 168 gr SMK",
        "alt_names": ["Federal GMM 308 168", "GM308M"],
        "sku": "GM308M",
        "caliber_name": ".308 Winchester",
        "bullet_sku": "2200",
        "bullet_weight_grains": 168.0,
        "muzzle_velocity_fps": 2650,
        "test_barrel_length_inches": 24.0,
        "round_count": 20,
        "bullet_match_method": "manual",
        "bullet_match_confidence": 1.0,
        "popularity_rank": 2,
        "source_url": "https://www.federalpremium.com/rifle/gold-medal/gold-medal-sierra-matchking/11-GM308M.html",
    },
    {
        "manufacturer_name": "Hornady",
        "product_line": "Match",
        "name": "Hornady .308 Win 178 gr ELD Match",
        "alt_names": ["Hornady Match 308 178 ELDM"],
        "sku": "8105",
        "caliber_name": ".308 Winchester",
        "bullet_sku": "30713",
        "bullet_weight_grains": 178.0,
        "muzzle_velocity_fps": 2600,
        "test_barrel_length_inches": 24.0,
        "round_count": 20,
        "bullet_match_method": "manual",
        "bullet_match_confidence": 1.0,
        "popularity_rank": 3,
        "source_url": "https://www.hornady.com/ammunition/rifle/308-win-178-gr-eld-match",
    },
    {
        "manufacturer_name": "Hornady",
        "product_line": "Match",
        "name": "Hornady .308 Win 168 gr ELD Match",
        "alt_names": ["Hornady Match 308 168 ELDM"],
        "sku": "80966",
        "caliber_name": ".308 Winchester",
        "bullet_sku": "30506",
        "bullet_weight_grains": 168.0,
        "muzzle_velocity_fps": 2700,
        "test_barrel_length_inches": 24.0,
        "round_count": 20,
        "bullet_match_method": "manual",
        "bullet_match_confidence": 1.0,
        "popularity_rank": 4,
        "source_url": "https://www.hornady.com/ammunition/rifle/308-win-168-gr-eld-match",
    },
    {
        "manufacturer_name": "Hornady",
        "product_line": "Precision Hunter",
        "name": "Hornady .308 Win 178 gr ELD-X",
        "alt_names": ["Hornady PH 308 178 ELDX"],
        "sku": "80994",
        "caliber_name": ".308 Winchester",
        "bullet_sku": "30713",
        "bullet_weight_grains": 178.0,
        "muzzle_velocity_fps": 2600,
        "test_barrel_length_inches": 24.0,
        "round_count": 20,
        "bullet_match_method": "manual",
        "bullet_match_confidence": 0.9,
        "source_url": "https://www.hornady.com/ammunition/rifle/308-win-178-gr-eld-x",
        "notes": "Uses ELD-X hunting bullet, not ELD Match. Bullet FK points to 178gr ELD Match as closest match.",
    },
    {
        "manufacturer_name": "Black Hills Ammunition",
        "product_line": "Match",
        "name": "Black Hills .308 Win 175 gr SMK",
        "alt_names": ["BH 308 175 SMK"],
        "sku": "D308N12",
        "caliber_name": ".308 Winchester",
        "bullet_sku": "2275",
        "bullet_weight_grains": 175.0,
        "muzzle_velocity_fps": 2600,
        "test_barrel_length_inches": 24.0,
        "round_count": 20,
        "bullet_match_method": "manual",
        "bullet_match_confidence": 1.0,
        "source_url": "https://www.black-hills.com/product/5-56mm-nato-77-grain-otm/",
    },
    {
        "manufacturer_name": "Berger Bullets",
        "product_line": "Match Grade",
        "name": "Berger .308 Win 185 gr Juggernaut OTM Tactical",
        "alt_names": ["Berger 308 185 Juggernaut"],
        "sku": "60010",
        "caliber_name": ".308 Winchester",
        "bullet_sku": "30428",
        "bullet_weight_grains": 185.0,
        "muzzle_velocity_fps": 2560,
        "test_barrel_length_inches": 24.0,
        "round_count": 20,
        "bullet_match_method": "manual",
        "bullet_match_confidence": 0.9,
        "source_url": "https://www.bergerbullets.com/products/308-win-185gr-juggernaut-otm-tactical/",
        "notes": "Uses 185gr Juggernaut OTM, mapped to closest bullet (185 Hybrid Target).",
    },
    {
        "manufacturer_name": "Lapua",
        "product_line": "Scenar",
        "name": "Lapua .308 Win 167 gr Scenar",
        "alt_names": ["Lapua 308 167 Scenar"],
        "sku": "4317523",
        "caliber_name": ".308 Winchester",
        "bullet_sku": "2200",
        "bullet_weight_grains": 167.0,
        "muzzle_velocity_fps": 2625,
        "test_barrel_length_inches": 24.0,
        "round_count": 50,
        "bullet_match_method": "manual",
        "bullet_match_confidence": 0.8,
        "source_url": "https://www.lapua.com/product/308-win-scenar-gb432-10-85g-167gr/",
        "notes": "Uses Lapua's own 167gr Scenar. Mapped to Sierra 168 SMK as closest equivalent.",
    },
    {
        "manufacturer_name": "Winchester",
        "product_line": "Match",
        "name": "Winchester Match .308 Win 168 gr HPBT",
        "alt_names": ["Winchester Match 308 168"],
        "sku": "S308M",
        "caliber_name": ".308 Winchester",
        "bullet_sku": "2200",
        "bullet_weight_grains": 168.0,
        "muzzle_velocity_fps": 2680,
        "test_barrel_length_inches": 24.0,
        "round_count": 20,
        "bullet_match_method": "manual",
        "bullet_match_confidence": 0.9,
        "source_url": "https://www.winchester.com/Products/Ammunition/Rifle/Match",
        "notes": "Uses Sierra 168 MatchKing per Winchester spec sheet.",
    },
]


# ---------------------------------------------------------------------------
# RifleModel seed data — one row per chambering
# Source: manufacturer websites
# ---------------------------------------------------------------------------

RIFLE_MODELS: list[dict] = [
    # --- 6.5 Creedmoor Rifles ---
    {
        "manufacturer_name": "Bergara",
        "model": "B-14 HMR 6.5 Creedmoor",
        "model_family": "Bergara B-14 HMR",
        "chamber_name": "6.5 Creedmoor",
        "barrel_length_inches": 22.0,
        "twist_rate": "1:8",
        "weight_lbs": 9.7,
        "source_url": "https://www.bergara.online/us/rifles/b14/b-14-hmr/",
    },
    {
        "manufacturer_name": "Tikka",
        "model": "T3x TAC A1 6.5 Creedmoor",
        "model_family": "Tikka T3x TAC A1",
        "chamber_name": "6.5 Creedmoor",
        "barrel_length_inches": 24.0,
        "twist_rate": "1:8",
        "weight_lbs": 10.36,
        "source_url": "https://www.tikka.fi/rifles/tikka-t3x/t3x-tac-a1",
    },
    {
        "manufacturer_name": "Ruger",
        "model": "Precision Rifle 6.5 Creedmoor",
        "model_family": "Ruger Precision Rifle",
        "chamber_name": "6.5 Creedmoor",
        "barrel_length_inches": 24.0,
        "twist_rate": "1:8",
        "weight_lbs": 10.7,
        "source_url": "https://www.ruger.com/products/precisionRifle/overview.html",
    },
    {
        "manufacturer_name": "Howa",
        "model": "1500 HCR 6.5 Creedmoor",
        "model_family": "Howa 1500 HCR",
        "chamber_name": "6.5 Creedmoor",
        "barrel_length_inches": 24.0,
        "twist_rate": "1:8",
        "weight_lbs": 10.0,
        "source_url": "https://www.howamachinery.com",
    },
    {
        "manufacturer_name": "Savage Arms",
        "model": "110 Tactical 6.5 Creedmoor",
        "model_family": "Savage 110 Tactical",
        "chamber_name": "6.5 Creedmoor",
        "barrel_length_inches": 24.0,
        "twist_rate": "1:8",
        "weight_lbs": 8.9,
        "source_url": "https://www.savagearms.com/content?p=firearms&a=product_summary&s=57232",
    },
    {
        "manufacturer_name": "Masterpiece Arms",
        "model": "BA Comp 6.5 Creedmoor",
        "model_family": "MPA BA Comp",
        "chamber_name": "6.5 Creedmoor",
        "barrel_length_inches": 26.0,
        "twist_rate": "1:8",
        "weight_lbs": 12.5,
        "description": "Dominant PRS competition rifle. ~29% of PRS competitors.",
        "source_url": "https://www.masterpiecearms.com/shop/mpa-ba-competition-rifle/",
    },
    {
        "manufacturer_name": "Bergara",
        "model": "B-14 HMR PRO 6.5 Creedmoor",
        "model_family": "Bergara B-14 HMR PRO",
        "chamber_name": "6.5 Creedmoor",
        "barrel_length_inches": 24.0,
        "twist_rate": "1:8",
        "weight_lbs": 9.2,
        "source_url": "https://www.bergara.online/us/rifles/b14/b-14-hmr-pro/",
    },
    # --- .308 Winchester Rifles ---
    {
        "manufacturer_name": "Bergara",
        "model": "B-14 HMR .308 Win",
        "model_family": "Bergara B-14 HMR",
        "chamber_name": ".308 Winchester",
        "barrel_length_inches": 20.0,
        "twist_rate": "1:10",
        "weight_lbs": 9.7,
        "source_url": "https://www.bergara.online/us/rifles/b14/b-14-hmr/",
    },
    {
        "manufacturer_name": "Tikka",
        "model": "T3x TAC A1 .308 Win",
        "model_family": "Tikka T3x TAC A1",
        "chamber_name": ".308 Winchester",
        "barrel_length_inches": 24.0,
        "twist_rate": "1:11",
        "weight_lbs": 10.36,
        "source_url": "https://www.tikka.fi/rifles/tikka-t3x/t3x-tac-a1",
    },
    {
        "manufacturer_name": "Ruger",
        "model": "Precision Rifle .308 Win",
        "model_family": "Ruger Precision Rifle",
        "chamber_name": ".308 Winchester",
        "barrel_length_inches": 20.0,
        "twist_rate": "1:10",
        "weight_lbs": 10.7,
        "source_url": "https://www.ruger.com/products/precisionRifle/overview.html",
    },
    {
        "manufacturer_name": "Savage Arms",
        "model": "110 Tactical .308 Win",
        "model_family": "Savage 110 Tactical",
        "chamber_name": ".308 Winchester",
        "barrel_length_inches": 24.0,
        "twist_rate": "1:10",
        "weight_lbs": 8.9,
        "source_url": "https://www.savagearms.com/content?p=firearms&a=product_summary&s=57232",
    },
    {
        "manufacturer_name": "Remington",
        "model": "700 SPS Tactical .308 Win",
        "model_family": "Remington 700 SPS Tactical",
        "chamber_name": ".308 Winchester",
        "barrel_length_inches": 20.0,
        "twist_rate": "1:10",
        "weight_lbs": 7.5,
        "source_url": "https://www.remington.com/rifles/bolt-action/model-700",
    },
    # --- 6.5 PRC ---
    {
        "manufacturer_name": "Bergara",
        "model": "B-14 HMR 6.5 PRC",
        "model_family": "Bergara B-14 HMR",
        "chamber_name": "6.5 PRC",
        "barrel_length_inches": 24.0,
        "twist_rate": "1:8",
        "weight_lbs": 9.7,
        "source_url": "https://www.bergara.online/us/rifles/b14/b-14-hmr/",
    },
    # --- .300 Win Mag ---
    {
        "manufacturer_name": "Tikka",
        "model": "T3x TAC A1 .300 Win Mag",
        "model_family": "Tikka T3x TAC A1",
        "chamber_name": ".300 Winchester Magnum",
        "barrel_length_inches": 24.0,
        "twist_rate": "1:10",
        "weight_lbs": 10.36,
        "source_url": "https://www.tikka.fi/rifles/tikka-t3x/t3x-tac-a1",
    },
    # --- .300 PRC ---
    {
        "manufacturer_name": "Ruger",
        "model": "Precision Rifle .300 PRC",
        "model_family": "Ruger Precision Rifle",
        "chamber_name": ".300 PRC",
        "barrel_length_inches": 26.0,
        "twist_rate": "1:9",
        "weight_lbs": 12.0,
        "source_url": "https://www.ruger.com/products/precisionRifle/overview.html",
    },
]


# ---------------------------------------------------------------------------
# Reticle seed data
# Source: manufacturer spec sheets and product pages
# ---------------------------------------------------------------------------

RETICLES: list[dict] = [
    # --- Vortex reticles ---
    {
        "name": "EBR-7C MRAD",
        "alt_names": ["EBR-7C", "7C MRAD"],
        "unit": "mil",
        "manufacturer_name": "Vortex Optics",
        "description": "Christmas-tree style mil reticle. Standard on Viper PST Gen II and Razor HD Gen III.",
        "source_url": "https://www.vortexoptics.com",
    },
    {
        "name": "EBR-7C MOA",
        "alt_names": ["7C MOA"],
        "unit": "moa",
        "manufacturer_name": "Vortex Optics",
        "description": "MOA variant of the EBR-7C christmas-tree reticle.",
        "source_url": "https://www.vortexoptics.com",
    },
    {
        "name": "EBR-2C MRAD",
        "alt_names": ["EBR-2C"],
        "unit": "mil",
        "manufacturer_name": "Vortex Optics",
        "description": "Simpler mil reticle. Common on mid-range Vortex models.",
    },
    # --- Nightforce reticles ---
    {
        "name": "Mil-XT",
        "alt_names": ["MIL-XT", "MILXT"],
        "unit": "mil",
        "manufacturer_name": "Nightforce Optics",
        "description": "Nightforce proprietary tree reticle. Standard on ATACR 5-25x56 Mil.",
        "source_url": "https://www.nightforceoptics.com",
    },
    {
        "name": "MOAR-20",
        "alt_names": ["MOAR20"],
        "unit": "moa",
        "manufacturer_name": "Nightforce Optics",
        "description": "Nightforce MOA reticle with 0.5 MOA grid. ATACR and NXS models.",
        "source_url": "https://www.nightforceoptics.com",
    },
    {
        "name": "Mil-C",
        "alt_names": ["MIL-C", "MILC"],
        "unit": "mil",
        "manufacturer_name": "Nightforce Optics",
        "description": "Mil-based reticle for NX8 and ATACR. Clean center crosshair with floating dot.",
    },
    # --- Leupold reticles ---
    {
        "name": "Tremor3",
        "alt_names": ["T3", "Horus Tremor3", "Horus T3"],
        "unit": "mil",
        "manufacturer_name": "Leupold",
        "description": "Horus-designed tree reticle. Complex wind/elevation holds. Licensed to Leupold for Mark 5HD.",
        "source_url": "https://www.leupold.com",
    },
    {
        "name": "H59",
        "alt_names": ["Horus H59"],
        "unit": "mil",
        "manufacturer_name": "Leupold",
        "description": "Horus-designed grid reticle. Dense hashmarks for hold-over shooting. Mark 5HD option.",
    },
    {
        "name": "PR2-MIL",
        "alt_names": ["PR2 MIL"],
        "unit": "mil",
        "manufacturer_name": "Leupold",
        "description": "Leupold's own precision mil reticle for Mark 5HD.",
    },
    {
        "name": "PR2-MOA",
        "alt_names": ["PR2 MOA"],
        "unit": "moa",
        "manufacturer_name": "Leupold",
        "description": "Leupold's own precision MOA reticle for Mark 5HD.",
    },
    # --- Kahles reticles ---
    {
        "name": "SKMR4",
        "alt_names": ["SKMR 4"],
        "unit": "mil",
        "manufacturer_name": "Kahles",
        "description": "Kahles precision mil reticle. Standard on K525i.",
        "source_url": "https://www.kahles.at",
    },
    # --- Sig Sauer reticles ---
    {
        "name": "DEV-L",
        "alt_names": ["DEVL"],
        "unit": "mil",
        "manufacturer_name": "Sig Sauer",
        "description": "Sig's proprietary precision mil reticle for Tango6T.",
        "source_url": "https://www.sigsauer.com",
    },
    # --- ZCO reticles ---
    {
        "name": "MPCT3",
        "alt_names": ["MPCT-3"],
        "unit": "mil",
        "manufacturer_name": "Zero Compromise Optics",
        "description": "ZCO's proprietary christmas-tree mil reticle for the ZC527.",
        "source_url": "https://www.zerocompromiseoptics.com",
    },
]


# ---------------------------------------------------------------------------
# Optic seed data — one row per buyable SKU
# Source: manufacturer spec sheets
# ---------------------------------------------------------------------------

OPTICS: list[dict] = [
    # --- Vortex Viper PST Gen II 5-25x50 ---
    {
        "manufacturer_name": "Vortex Optics",
        "name": "Vortex Viper PST Gen II 5-25x50 EBR-7C MRAD",
        "model_family": "Vortex Viper PST Gen II 5-25x50",
        "product_line": "Viper PST Gen II",
        "sku": "PST-5258",
        "reticle_name": "EBR-7C MRAD",
        "click_unit": "mil",
        "click_value": 0.1,
        "magnification_min": 5.0,
        "magnification_max": 25.0,
        "objective_diameter_mm": 50.0,
        "tube_diameter_mm": 30.0,
        "focal_plane": "ffp",
        "elevation_travel_mils": 29.1,
        "windage_travel_mils": 20.0,
        "weight_oz": 30.2,
        "length_inches": 15.15,
        "source_url": "https://www.vortexoptics.com/vortex-viper-pst-gen-2-5-25x50-riflescope.html",
    },
    {
        "manufacturer_name": "Vortex Optics",
        "name": "Vortex Viper PST Gen II 5-25x50 EBR-7C MOA",
        "model_family": "Vortex Viper PST Gen II 5-25x50",
        "product_line": "Viper PST Gen II",
        "sku": "PST-5259",
        "reticle_name": "EBR-7C MOA",
        "click_unit": "moa",
        "click_value": 0.25,
        "magnification_min": 5.0,
        "magnification_max": 25.0,
        "objective_diameter_mm": 50.0,
        "tube_diameter_mm": 30.0,
        "focal_plane": "ffp",
        "elevation_travel_mils": 29.1,
        "windage_travel_mils": 20.0,
        "weight_oz": 30.2,
        "length_inches": 15.15,
        "source_url": "https://www.vortexoptics.com/vortex-viper-pst-gen-2-5-25x50-riflescope.html",
    },
    # --- Vortex Razor HD Gen III 6-36x56 ---
    {
        "manufacturer_name": "Vortex Optics",
        "name": "Vortex Razor HD Gen III 6-36x56 EBR-7C MRAD",
        "model_family": "Vortex Razor HD Gen III 6-36x56",
        "product_line": "Razor HD Gen III",
        "sku": "RZR-63601",
        "reticle_name": "EBR-7C MRAD",
        "click_unit": "mil",
        "click_value": 0.1,
        "magnification_min": 6.0,
        "magnification_max": 36.0,
        "objective_diameter_mm": 56.0,
        "tube_diameter_mm": 34.0,
        "focal_plane": "ffp",
        "elevation_travel_mils": 37.5,
        "windage_travel_mils": 20.0,
        "weight_oz": 46.5,
        "length_inches": 14.37,
        "source_url": "https://www.vortexoptics.com/vortex-razor-hd-gen-3-6-36x56-riflescope.html",
    },
    # --- Vortex Viper PST Gen II 3-15x44 ---
    {
        "manufacturer_name": "Vortex Optics",
        "name": "Vortex Viper PST Gen II 3-15x44 EBR-2C MRAD",
        "model_family": "Vortex Viper PST Gen II 3-15x44",
        "product_line": "Viper PST Gen II",
        "sku": "PST-3155",
        "reticle_name": "EBR-2C MRAD",
        "click_unit": "mil",
        "click_value": 0.1,
        "magnification_min": 3.0,
        "magnification_max": 15.0,
        "objective_diameter_mm": 44.0,
        "tube_diameter_mm": 30.0,
        "focal_plane": "ffp",
        "elevation_travel_mils": 23.3,
        "windage_travel_mils": 23.3,
        "weight_oz": 23.8,
        "length_inches": 12.63,
        "source_url": "https://www.vortexoptics.com/vortex-viper-pst-gen-2-3-15x44-riflescope.html",
    },
    # --- Nightforce ATACR 5-25x56 ---
    {
        "manufacturer_name": "Nightforce Optics",
        "name": "Nightforce ATACR 5-25x56 F1 Mil-XT",
        "model_family": "Nightforce ATACR 5-25x56",
        "product_line": "ATACR",
        "sku": "C555",
        "reticle_name": "Mil-XT",
        "click_unit": "mil",
        "click_value": 0.1,
        "magnification_min": 5.0,
        "magnification_max": 25.0,
        "objective_diameter_mm": 56.0,
        "tube_diameter_mm": 34.0,
        "focal_plane": "ffp",
        "elevation_travel_mils": 30.0,
        "windage_travel_mils": 17.5,
        "weight_oz": 38.0,
        "length_inches": 14.8,
        "source_url": "https://www.nightforceoptics.com/atacr-5-25x56-f1",
    },
    {
        "manufacturer_name": "Nightforce Optics",
        "name": "Nightforce ATACR 5-25x56 F1 MOAR-20",
        "model_family": "Nightforce ATACR 5-25x56",
        "product_line": "ATACR",
        "sku": "C556",
        "reticle_name": "MOAR-20",
        "click_unit": "moa",
        "click_value": 0.25,
        "magnification_min": 5.0,
        "magnification_max": 25.0,
        "objective_diameter_mm": 56.0,
        "tube_diameter_mm": 34.0,
        "focal_plane": "ffp",
        "elevation_travel_mils": 30.0,
        "windage_travel_mils": 17.5,
        "weight_oz": 38.0,
        "length_inches": 14.8,
        "source_url": "https://www.nightforceoptics.com/atacr-5-25x56-f1",
    },
    # --- Nightforce ATACR 7-35x56 ---
    {
        "manufacturer_name": "Nightforce Optics",
        "name": "Nightforce ATACR 7-35x56 F1 Mil-XT",
        "model_family": "Nightforce ATACR 7-35x56",
        "product_line": "ATACR",
        "sku": "C634",
        "reticle_name": "Mil-XT",
        "click_unit": "mil",
        "click_value": 0.1,
        "magnification_min": 7.0,
        "magnification_max": 35.0,
        "objective_diameter_mm": 56.0,
        "tube_diameter_mm": 34.0,
        "focal_plane": "ffp",
        "elevation_travel_mils": 30.0,
        "windage_travel_mils": 17.5,
        "weight_oz": 38.0,
        "length_inches": 15.1,
        "source_url": "https://www.nightforceoptics.com/atacr-7-35x56-f1",
    },
    # --- Nightforce NX8 2.5-20x50 ---
    {
        "manufacturer_name": "Nightforce Optics",
        "name": "Nightforce NX8 2.5-20x50 F1 Mil-C",
        "model_family": "Nightforce NX8 2.5-20x50",
        "product_line": "NX8",
        "sku": "C624",
        "reticle_name": "Mil-C",
        "click_unit": "mil",
        "click_value": 0.1,
        "magnification_min": 2.5,
        "magnification_max": 20.0,
        "objective_diameter_mm": 50.0,
        "tube_diameter_mm": 30.0,
        "focal_plane": "ffp",
        "elevation_travel_mils": 25.0,
        "windage_travel_mils": 20.0,
        "weight_oz": 26.0,
        "length_inches": 13.54,
        "source_url": "https://www.nightforceoptics.com/nx8-2-5-20x50-f1",
    },
    # --- Leupold Mark 5HD 5-25x56 ---
    {
        "manufacturer_name": "Leupold",
        "name": "Leupold Mark 5HD 5-25x56 FFP Tremor3",
        "model_family": "Leupold Mark 5HD 5-25x56 FFP",
        "product_line": "Mark 5HD",
        "sku": "171772",
        "reticle_name": "Tremor3",
        "click_unit": "mil",
        "click_value": 0.1,
        "magnification_min": 5.0,
        "magnification_max": 25.0,
        "objective_diameter_mm": 56.0,
        "tube_diameter_mm": 35.0,
        "focal_plane": "ffp",
        "elevation_travel_mils": 29.1,
        "windage_travel_mils": 14.5,
        "weight_oz": 30.0,
        "length_inches": 15.67,
        "source_url": "https://www.leupold.com/scopes/rifle-scopes/mark-5hd-5-25x56",
    },
    {
        "manufacturer_name": "Leupold",
        "name": "Leupold Mark 5HD 5-25x56 FFP H59",
        "model_family": "Leupold Mark 5HD 5-25x56 FFP",
        "product_line": "Mark 5HD",
        "sku": "176450",
        "reticle_name": "H59",
        "click_unit": "mil",
        "click_value": 0.1,
        "magnification_min": 5.0,
        "magnification_max": 25.0,
        "objective_diameter_mm": 56.0,
        "tube_diameter_mm": 35.0,
        "focal_plane": "ffp",
        "elevation_travel_mils": 29.1,
        "windage_travel_mils": 14.5,
        "weight_oz": 30.0,
        "length_inches": 15.67,
        "source_url": "https://www.leupold.com/scopes/rifle-scopes/mark-5hd-5-25x56",
    },
    {
        "manufacturer_name": "Leupold",
        "name": "Leupold Mark 5HD 5-25x56 FFP PR2-MIL",
        "model_family": "Leupold Mark 5HD 5-25x56 FFP",
        "product_line": "Mark 5HD",
        "sku": "180616",
        "reticle_name": "PR2-MIL",
        "click_unit": "mil",
        "click_value": 0.1,
        "magnification_min": 5.0,
        "magnification_max": 25.0,
        "objective_diameter_mm": 56.0,
        "tube_diameter_mm": 35.0,
        "focal_plane": "ffp",
        "elevation_travel_mils": 29.1,
        "windage_travel_mils": 14.5,
        "weight_oz": 30.0,
        "length_inches": 15.67,
        "source_url": "https://www.leupold.com/scopes/rifle-scopes/mark-5hd-5-25x56",
    },
    {
        "manufacturer_name": "Leupold",
        "name": "Leupold Mark 5HD 5-25x56 FFP PR2-MOA",
        "model_family": "Leupold Mark 5HD 5-25x56 FFP",
        "product_line": "Mark 5HD",
        "sku": "180617",
        "reticle_name": "PR2-MOA",
        "click_unit": "moa",
        "click_value": 0.25,
        "magnification_min": 5.0,
        "magnification_max": 25.0,
        "objective_diameter_mm": 56.0,
        "tube_diameter_mm": 35.0,
        "focal_plane": "ffp",
        "elevation_travel_mils": 29.1,
        "windage_travel_mils": 14.5,
        "weight_oz": 30.0,
        "length_inches": 15.67,
        "source_url": "https://www.leupold.com/scopes/rifle-scopes/mark-5hd-5-25x56",
    },
    # --- Leupold Mark 5HD 3.6-18x44 ---
    {
        "manufacturer_name": "Leupold",
        "name": "Leupold Mark 5HD 3.6-18x44 FFP Tremor3",
        "model_family": "Leupold Mark 5HD 3.6-18x44 FFP",
        "product_line": "Mark 5HD",
        "sku": "174184",
        "reticle_name": "Tremor3",
        "click_unit": "mil",
        "click_value": 0.1,
        "magnification_min": 3.6,
        "magnification_max": 18.0,
        "objective_diameter_mm": 44.0,
        "tube_diameter_mm": 35.0,
        "focal_plane": "ffp",
        "elevation_travel_mils": 29.1,
        "windage_travel_mils": 14.5,
        "weight_oz": 26.0,
        "length_inches": 12.09,
        "source_url": "https://www.leupold.com/scopes/rifle-scopes/mark-5hd-3-6-18x44",
    },
    # --- Kahles K525i ---
    {
        "manufacturer_name": "Kahles",
        "name": "Kahles K525i 5-25x56 SKMR4",
        "model_family": "Kahles K525i 5-25x56",
        "product_line": "K525i",
        "sku": "10645",
        "reticle_name": "SKMR4",
        "click_unit": "mil",
        "click_value": 0.1,
        "magnification_min": 5.0,
        "magnification_max": 25.0,
        "objective_diameter_mm": 56.0,
        "tube_diameter_mm": 34.0,
        "focal_plane": "ffp",
        "elevation_travel_mils": 26.2,
        "windage_travel_mils": 13.1,
        "weight_oz": 32.3,
        "length_inches": 15.3,
        "source_url": "https://www.kahles.at/com/k525i-5-25x56",
    },
    # --- Sig Sauer Tango6T ---
    {
        "manufacturer_name": "Sig Sauer",
        "name": "Sig Sauer Tango6T 1-6x24 DWLR-556",
        "model_family": "Sig Sauer Tango6T 1-6x24",
        "product_line": "Tango6T",
        "sku": "SOT61134",
        "reticle_name": "DEV-L",
        "click_unit": "mil",
        "click_value": 0.1,
        "magnification_min": 1.0,
        "magnification_max": 6.0,
        "objective_diameter_mm": 24.0,
        "tube_diameter_mm": 30.0,
        "focal_plane": "ffp",
        "elevation_travel_mils": 30.0,
        "windage_travel_mils": 20.0,
        "weight_oz": 22.9,
        "length_inches": 10.6,
        "source_url": "https://www.sigsauer.com/tango6t-1-6x24-mm.html",
    },
    # --- ZCO ZC527 ---
    {
        "manufacturer_name": "Zero Compromise Optics",
        "name": "ZCO ZC527 5-27x56 MPCT3",
        "model_family": "ZCO ZC527 5-27x56",
        "product_line": "ZC527",
        "sku": "ZC527-MPCT3",
        "reticle_name": "MPCT3",
        "click_unit": "mil",
        "click_value": 0.1,
        "magnification_min": 5.0,
        "magnification_max": 27.0,
        "objective_diameter_mm": 56.0,
        "tube_diameter_mm": 36.0,
        "focal_plane": "ffp",
        "elevation_travel_mils": 32.5,
        "windage_travel_mils": 19.0,
        "weight_oz": 43.0,
        "length_inches": 15.3,
        "source_url": "https://www.zerocompromiseoptics.com/product/zc527",
    },
]


# ---------------------------------------------------------------------------
# Extended EntityAlias seed data — aliases for new entities
# ---------------------------------------------------------------------------

EXTENDED_ENTITY_ALIASES: list[dict] = [
    # --- Bullet aliases ---
    {"entity_type": "bullet", "entity_name": "26331", "alias": "ELDM 140", "alias_type": "abbreviation"},
    {"entity_type": "bullet", "entity_name": "26331", "alias": "140 ELD Match", "alias_type": "alternate_name"},
    {"entity_type": "bullet", "entity_name": "26333", "alias": "ELDM 147", "alias_type": "abbreviation"},
    {"entity_type": "bullet", "entity_name": "26333", "alias": "147 ELD Match", "alias_type": "alternate_name"},
    {"entity_type": "bullet", "entity_name": "2275", "alias": "SMK 175", "alias_type": "abbreviation"},
    {"entity_type": "bullet", "entity_name": "2275", "alias": "175 MatchKing", "alias_type": "alternate_name"},
    {"entity_type": "bullet", "entity_name": "2275", "alias": "M118LR bullet", "alias_type": "nickname"},
    {"entity_type": "bullet", "entity_name": "2200", "alias": "SMK 168", "alias_type": "abbreviation"},
    {"entity_type": "bullet", "entity_name": "2200", "alias": "168 MatchKing", "alias_type": "alternate_name"},
    {"entity_type": "bullet", "entity_name": "26414", "alias": "Hybrid 140", "alias_type": "abbreviation"},
    # --- Cartridge aliases ---
    {"entity_type": "cartridge", "entity_name": "81500", "alias": "81500", "alias_type": "sku"},
    {"entity_type": "cartridge", "entity_name": "81500", "alias": "Hornady Match 6.5 CM", "alias_type": "abbreviation"},
    {"entity_type": "cartridge", "entity_name": "GM308M2", "alias": "GM308M2", "alias_type": "sku"},
    {"entity_type": "cartridge", "entity_name": "GM308M2", "alias": "GMM 308 175", "alias_type": "abbreviation"},
    {"entity_type": "cartridge", "entity_name": "GM308M", "alias": "GM308M", "alias_type": "sku"},
    {"entity_type": "cartridge", "entity_name": "GM308M", "alias": "GMM 308 168", "alias_type": "abbreviation"},
    # --- Optic manufacturer aliases (unique entries not in main ENTITY_ALIASES) ---
    {
        "entity_type": "manufacturer",
        "entity_name": "Leupold",
        "alias": "Leupold & Stevens",
        "alias_type": "alternate_name",
    },
    {
        "entity_type": "manufacturer",
        "entity_name": "Sig Sauer",
        "alias": "SIG SAUER",
        "alias_type": "alternate_name",
    },
    # --- Reticle aliases ---
    {"entity_type": "reticle", "entity_name": "EBR-7C MRAD", "alias": "EBR-7C", "alias_type": "abbreviation"},
    {"entity_type": "reticle", "entity_name": "EBR-7C MRAD", "alias": "7C MRAD", "alias_type": "abbreviation"},
    {"entity_type": "reticle", "entity_name": "Mil-XT", "alias": "MIL-XT", "alias_type": "alternate_name"},
    {"entity_type": "reticle", "entity_name": "Tremor3", "alias": "T3", "alias_type": "abbreviation"},
    {"entity_type": "reticle", "entity_name": "Tremor3", "alias": "Horus Tremor3", "alias_type": "alternate_name"},
    # --- Optic aliases ---
    {"entity_type": "optic", "entity_name": "PST-5258", "alias": "Viper PST II 5-25 Mil", "alias_type": "abbreviation"},
    {"entity_type": "optic", "entity_name": "PST-5259", "alias": "Viper PST II 5-25 MOA", "alias_type": "abbreviation"},
    {"entity_type": "optic", "entity_name": "C555", "alias": "ATACR 5-25 Mil-XT", "alias_type": "abbreviation"},
    {
        "entity_type": "optic",
        "entity_name": "ZC527-MPCT3",
        "alias": "ZC527",
        "alias_type": "abbreviation",
    },
]


# ---------------------------------------------------------------------------
# Seeding logic
# ---------------------------------------------------------------------------


def _build_caliber_lookup(session: Session) -> dict[str, str]:
    """Return {caliber.name: caliber.id} for all calibers in the DB."""
    return {c.name: c.id for c in session.query(Caliber).all()}


def _build_manufacturer_lookup(session: Session) -> dict[str, str]:
    """Return {manufacturer.name: manufacturer.id} for all manufacturers in the DB."""
    return {m.name: m.id for m in session.query(Manufacturer).all()}


def _build_chamber_lookup(session: Session) -> dict[str, str]:
    """Return {chamber.name: chamber.id} for all chambers in the DB."""
    return {c.name: c.id for c in session.query(Chamber).all()}


def _build_bullet_sku_lookup(session: Session) -> dict[str, str]:
    """Return {bullet.sku: bullet.id} for all bullets with a SKU."""
    return {b.sku: b.id for b in session.query(Bullet).filter(Bullet.sku.isnot(None)).all()}


def _build_reticle_lookup(session: Session) -> dict[str, str]:
    """Return {reticle.name: reticle.id} for all reticles in the DB."""
    return {r.name: r.id for r in session.query(Reticle).all()}


def _build_entity_lookup(session: Session) -> dict[tuple[str, str], str]:
    """Return {(entity_type, name_or_sku): id} for all entity types.

    For bullets, cartridges, optics: keyed by SKU (since names aren't unique).
    For reticles: keyed by name.
    For manufacturers, calibers: keyed by name.
    """
    lookup: dict[tuple[str, str], str] = {}
    for m in session.query(Manufacturer).all():
        lookup[("manufacturer", m.name)] = m.id
    for c in session.query(Caliber).all():
        lookup[("caliber", c.name)] = c.id
    for b in session.query(Bullet).filter(Bullet.sku.isnot(None)).all():
        lookup[("bullet", b.sku)] = b.id
    for c in session.query(Cartridge).filter(Cartridge.sku.isnot(None)).all():
        lookup[("cartridge", c.sku)] = c.id
    for r in session.query(Reticle).all():
        lookup[("reticle", r.name)] = r.id
    for o in session.query(Optic).filter(Optic.sku.isnot(None)).all():
        lookup[("optic", o.sku)] = o.id
    return lookup


def seed_manufacturers(session: Session) -> None:
    print(f"  Seeding {len(MANUFACTURERS)} manufacturers...")
    for data in MANUFACTURERS:
        session.add(Manufacturer(**data))
    session.flush()


def seed_calibers(session: Session) -> None:
    print(f"  Seeding {len(CALIBERS)} calibers...")
    for data in CALIBERS:
        session.add(Caliber(**data))
    session.flush()


def seed_chambers(session: Session) -> None:
    cal_lookup = _build_caliber_lookup(session)

    # Auto-generated 1:1 chambers
    auto_count = 0
    for cal_name in AUTO_CHAMBER_CALIBERS:
        cal_id = cal_lookup.get(cal_name)
        if not cal_id:
            print(f"  WARNING: caliber {cal_name!r} not found — skipping auto-chamber")
            continue
        chamber = Chamber(name=cal_name)
        session.add(chamber)
        session.flush()
        session.add(ChamberAcceptsCaliber(chamber_id=chamber.id, caliber_id=cal_id, is_primary=True))
        auto_count += 1

    # Manually curated chambers
    manual_count = 0
    for data in MANUAL_CHAMBERS:
        chamber = Chamber(
            name=data["name"],
            alt_names=data.get("alt_names"),
            notes=data.get("notes"),
            source=data.get("source"),
        )
        session.add(chamber)
        session.flush()
        for link in data["accepts"]:
            cal_id = cal_lookup.get(link["caliber_name"])
            if not cal_id:
                print(f"  WARNING: caliber {link['caliber_name']!r} not found — skipping link")
                continue
            session.add(
                ChamberAcceptsCaliber(
                    chamber_id=chamber.id,
                    caliber_id=cal_id,
                    is_primary=link["is_primary"],
                )
            )
        manual_count += 1

    session.flush()
    print(f"  Seeded {auto_count} auto-generated + {manual_count} manually curated chambers")


def seed_bullets(session: Session) -> None:
    mfr_lookup = _build_manufacturer_lookup(session)
    cal_lookup = _build_caliber_lookup(session)
    count = 0
    for data in BULLETS:
        row = {k: v for k, v in data.items() if k not in ("manufacturer_name", "caliber_name")}
        row["manufacturer_id"] = mfr_lookup[data["manufacturer_name"]]
        row["caliber_id"] = cal_lookup[data["caliber_name"]]
        session.add(Bullet(**row))
        count += 1
    session.flush()
    print(f"  Seeded {count} bullets")


def seed_bullet_bc_sources(session: Session) -> None:
    bullet_lookup = _build_bullet_sku_lookup(session)
    count = 0
    for data in BULLET_BC_SOURCES:
        row = {k: v for k, v in data.items() if k != "bullet_sku"}
        row["bullet_id"] = bullet_lookup[data["bullet_sku"]]
        session.add(BulletBCSource(**row))
        count += 1
    session.flush()
    print(f"  Seeded {count} bullet BC sources")


def seed_cartridges(session: Session) -> None:
    mfr_lookup = _build_manufacturer_lookup(session)
    cal_lookup = _build_caliber_lookup(session)
    bullet_lookup = _build_bullet_sku_lookup(session)
    count = 0
    for data in CARTRIDGES:
        row = {k: v for k, v in data.items() if k not in ("manufacturer_name", "caliber_name", "bullet_sku", "notes")}
        row["manufacturer_id"] = mfr_lookup[data["manufacturer_name"]]
        row["caliber_id"] = cal_lookup[data["caliber_name"]]
        row["bullet_id"] = bullet_lookup[data["bullet_sku"]]
        session.add(Cartridge(**row))
        count += 1
    session.flush()
    print(f"  Seeded {count} cartridges")


def seed_rifle_models(session: Session) -> None:
    mfr_lookup = _build_manufacturer_lookup(session)
    chamber_lookup = _build_chamber_lookup(session)
    count = 0
    for data in RIFLE_MODELS:
        row = {k: v for k, v in data.items() if k not in ("manufacturer_name", "chamber_name")}
        row["manufacturer_id"] = mfr_lookup[data["manufacturer_name"]]
        row["chamber_id"] = chamber_lookup[data["chamber_name"]]
        session.add(RifleModel(**row))
        count += 1
    session.flush()
    print(f"  Seeded {count} rifle models")


def seed_reticles(session: Session) -> None:
    mfr_lookup = _build_manufacturer_lookup(session)
    count = 0
    for data in RETICLES:
        row = {k: v for k, v in data.items() if k != "manufacturer_name"}
        row["manufacturer_id"] = mfr_lookup[data["manufacturer_name"]]
        session.add(Reticle(**row))
        count += 1
    session.flush()
    print(f"  Seeded {count} reticles")


def seed_optics(session: Session) -> None:
    mfr_lookup = _build_manufacturer_lookup(session)
    reticle_lookup = _build_reticle_lookup(session)
    count = 0
    for data in OPTICS:
        row = {k: v for k, v in data.items() if k not in ("manufacturer_name", "reticle_name")}
        row["manufacturer_id"] = mfr_lookup[data["manufacturer_name"]]
        row["reticle_id"] = reticle_lookup[data["reticle_name"]]
        session.add(Optic(**row))
        count += 1
    session.flush()
    print(f"  Seeded {count} optics")


def seed_platforms(session: Session) -> None:
    cal_lookup = _build_caliber_lookup(session)
    platform_lookup: dict[str, str] = {}

    # Create platform rows
    print(f"  Seeding {len(PLATFORMS)} platforms...")
    for data in PLATFORMS:
        platform = Platform(**data)
        session.add(platform)
        session.flush()
        platform_lookup[platform.short_name] = platform.id

    # Create caliber↔platform links
    link_count = 0
    for data in CALIBER_PLATFORMS:
        cal_id = cal_lookup.get(data["caliber_name"])
        plat_id = platform_lookup.get(data["platform"])
        if not cal_id:
            print(f"  WARNING: caliber {data['caliber_name']!r} not found — skipping platform link")
            continue
        if not plat_id:
            print(f"  WARNING: platform {data['platform']!r} not found — skipping platform link")
            continue
        session.add(
            CaliberPlatform(
                caliber_id=cal_id,
                platform_id=plat_id,
                popularity_rank=data.get("rank"),
                notes=data.get("notes"),
            )
        )
        link_count += 1

    session.flush()
    print(f"  Seeded {link_count} caliber↔platform links")


def seed_entity_aliases(session: Session) -> None:
    entity_lookup = _build_entity_lookup(session)
    all_aliases = ENTITY_ALIASES + EXTENDED_ENTITY_ALIASES
    count = 0
    for data in all_aliases:
        key = (data["entity_type"], data["entity_name"])
        entity_id = entity_lookup.get(key)
        if not entity_id:
            print(f"  WARNING: entity {key} not found — skipping alias {data['alias']!r}")
            continue
        session.add(
            EntityAlias(
                entity_type=data["entity_type"],
                entity_id=entity_id,
                alias=data["alias"],
                alias_type=data["alias_type"],
            )
        )
        count += 1
    session.flush()
    print(f"  Seeded {count} entity aliases")


def seed_all(session: Session) -> None:
    seed_manufacturers(session)
    seed_calibers(session)
    seed_chambers(session)
    seed_platforms(session)
    seed_bullets(session)
    seed_bullet_bc_sources(session)
    seed_cartridges(session)
    seed_rifle_models(session)
    seed_reticles(session)
    seed_optics(session)
    seed_entity_aliases(session)
    session.commit()
    print("Done.")


def reset_seeded_tables(session: Session) -> None:
    """Delete all rows from seed-data tables (preserves schema)."""
    print("Resetting seed data tables...")
    # Delete in FK-safe order: children before parents
    session.query(EntityAlias).delete()
    session.query(Optic).delete()
    session.query(Reticle).delete()
    session.query(RifleModel).delete()
    session.query(BulletBCSource).delete()
    session.query(Cartridge).delete()
    session.query(Bullet).delete()
    session.query(CaliberPlatform).delete()
    session.query(Platform).delete()
    session.query(ChamberAcceptsCaliber).delete()
    session.query(Chamber).delete()
    session.query(Caliber).delete()
    session.query(Manufacturer).delete()
    session.commit()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the Drift Ballistics backend database.")
    parser.add_argument("--reset", action="store_true", help="Delete existing seed data before re-seeding")
    args = parser.parse_args()

    engine = get_engine()
    Base.metadata.create_all(engine)

    session_factory = get_session_factory()
    session = session_factory()

    try:
        if args.reset:
            reset_seeded_tables(session)
        print("Seeding database...")
        seed_all(session)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
