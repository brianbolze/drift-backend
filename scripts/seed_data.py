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
    Cartridge,
    Chamber,
    ChamberAcceptsCaliber,
    EntityAlias,
    Manufacturer,
    Optic,
    Reticle,
    RifleModel,
)

# ---------------------------------------------------------------------------
# Manufacturer seed data
# Source: design proposal MVP scope + domain expert review (2026-02-20)
# ---------------------------------------------------------------------------

MANUFACTURERS = [
    {
        "name": "Hornady",
        "alt_names": ["Hornady Manufacturing", "Hornaday"],
        "website_url": "https://www.hornady.com",
        "type_tags": ["bullet_maker", "ammo_maker"],
        "country": "USA",
    },
    {
        "name": "Federal Premium",
        "alt_names": ["Federal", "Federal Ammunition", "ATK Federal"],
        "website_url": "https://www.federalpremium.com",
        "type_tags": ["ammo_maker", "bullet_maker"],
        "country": "USA",
        "notes": (
            "Parent company Vista Outdoor. Also owns CCI, Speer, Sierra. "
            "Makes own bullets for some lines (Trophy Bonded, Fusion, Terminal Ascent)."
        ),
    },
    {
        "name": "Sierra Bullets",
        "alt_names": ["Sierra"],
        "website_url": "https://www.sierrabullets.com",
        "type_tags": ["bullet_maker"],
        "country": "USA",
        "notes": "Owned by Vista Outdoor / Federal. MatchKing line is the precision standard.",
    },
    {
        "name": "Berger Bullets",
        "alt_names": ["Berger", "Burger"],
        "website_url": "https://www.bergerbullets.com",
        "type_tags": ["bullet_maker"],
        "country": "USA",
        "notes": "Known for Hybrid and VLD designs. Sold to JRS Enterprises in early 2025.",
    },
    {
        "name": "Nosler",
        "alt_names": ["Nosler Inc"],
        "website_url": "https://www.nosler.com",
        "type_tags": ["bullet_maker", "ammo_maker"],
        "country": "USA",
        "notes": "Invented the Partition bullet. Also makes loaded ammo (Trophy Grade).",
    },
    {
        "name": "Barnes Bullets",
        "alt_names": ["Barnes"],
        "website_url": "https://www.barnesbullets.com",
        "type_tags": ["bullet_maker"],
        "country": "USA",
        "notes": "Pioneer of monolithic copper bullets (TSX, TTSX, LRX). Owned by Remington/Vista.",
    },
    {
        "name": "Lapua",
        "alt_names": ["Nammo Lapua"],
        "website_url": "https://www.lapua.com",
        "type_tags": ["bullet_maker", "ammo_maker"],
        "country": "Finland",
        "notes": "Premium brass and Scenar bullet line. Parent company Nammo.",
    },
    {
        "name": "Applied Ballistics",
        "alt_names": ["AB", "Applied Ballistics LLC"],
        "website_url": "https://www.appliedballisticsllc.com",
        "type_tags": ["data_provider"],
        "country": "USA",
        "notes": "Bryan Litz. Doppler-measured BC data and custom drag models. Gold standard for BC values.",
    },
    {
        "name": "Winchester",
        "alt_names": ["Olin Winchester", "Winchester Ammunition"],
        "website_url": "https://www.winchester.com",
        "type_tags": ["ammo_maker"],
        "country": "USA",
        "notes": "Ammo manufactured by Olin Corp. Brand name on many caliber designations (.308 Win, .270 Win, etc.).",
    },
    {
        "name": "Bergara",
        "alt_names": [],
        "website_url": "https://www.bergara.online/us",
        "type_tags": ["rifle_maker"],
        "country": "Spain",
        "notes": "B-14 HMR is a benchmark for precision-for-the-money.",
    },
    {
        "name": "Tikka",
        "alt_names": [],
        "website_url": "https://www.tikka.fi",
        "type_tags": ["rifle_maker"],
        "country": "Finland",
        "notes": "Made by Sako (Beretta group). T3x TAC A1 is a popular precision chassis rifle.",
    },
    {
        "name": "Ruger",
        "alt_names": ["Sturm, Ruger & Co."],
        "website_url": "https://www.ruger.com",
        "type_tags": ["rifle_maker"],
        "country": "USA",
    },
    {
        "name": "Howa",
        "alt_names": ["Howa Machinery"],
        "website_url": "https://www.howamachinery.com",
        "type_tags": ["rifle_maker"],
        "country": "Japan",
        "notes": "Imported/distributed by Legacy Sports International in the US.",
    },
    {
        "name": "Savage Arms",
        "alt_names": ["Savage"],
        "website_url": "https://www.savagearms.com",
        "type_tags": ["rifle_maker"],
        "country": "USA",
    },
    {
        "name": "Remington",
        "alt_names": ["Remington Arms", "Big Green"],
        "website_url": "https://www.remington.com",
        "type_tags": ["rifle_maker", "ammo_maker"],
        "country": "USA",
        "notes": "Historically makes both firearms and ammunition. Post-bankruptcy, split operations.",
    },
    {
        "name": "Masterpiece Arms",
        "alt_names": ["MPA"],
        "website_url": "https://www.masterpiecearms.com",
        "type_tags": ["rifle_maker", "chassis_maker"],
        "country": "USA",
        "notes": (
            "Dominant PRS rifle/chassis brand. BA Comp used by ~29% of PRS competitors, " "44% of top-25 shooters."
        ),
    },
    {
        "name": "Seekins Precision",
        "alt_names": ["Seekins"],
        "website_url": "https://www.seekinsprecision.com",
        "type_tags": ["rifle_maker"],
        "country": "USA",
        "notes": "Havak line well-regarded for factory precision. SP10 is the accuracy ceiling for factory gas guns.",
    },
    {
        "name": "Speer",
        "alt_names": [],
        "website_url": "https://www.speer.com",
        "type_tags": ["bullet_maker", "ammo_maker"],
        "country": "USA",
        "notes": "Gold Dot line for duty/defense. Owned by Vista Outdoor.",
    },
    {
        "name": "Black Hills Ammunition",
        "alt_names": ["Black Hills", "BHA"],
        "website_url": "https://www.black-hills.com",
        "type_tags": ["ammo_maker"],
        "country": "USA",
        "notes": "Premium loaded ammo favored by precision shooters. MK 262 Mod 1 military contract.",
    },
    {
        "name": "Sellier & Bellot",
        "alt_names": ["S&B"],
        "website_url": "https://www.sellier-bellot.com",
        "type_tags": ["ammo_maker"],
        "country": "Czech Republic",
        "notes": "One of the oldest ammo manufacturers (est. 1825). Owned by Colt CZ Group.",
    },
    {
        "name": "IMI Systems",
        "alt_names": ["IMI", "Israeli Military Industries"],
        "website_url": "https://www.imisystems.com",
        "type_tags": ["ammo_maker"],
        "country": "Israel",
        "notes": "Military and commercial ammo. Razorcore line for precision. Imported by various US distributors.",
    },
    {
        "name": "Prvi Partizan",
        "alt_names": ["PPU", "Privi Partizan"],
        "website_url": "https://www.prvipartizan.com",
        "type_tags": ["ammo_maker"],
        "country": "Serbia",
        "notes": "Affordable brass-cased ammo. Popular for practice/training. Good quality for the price.",
    },
    # --- Phase 1.5: AR Rifle Manufacturers — Tier 1 ---
    {
        "name": "Daniel Defense",
        "alt_names": ["DD"],
        "website_url": "https://www.danieldefense.com",
        "type_tags": ["rifle_maker"],
        "country": "USA",
        "notes": (
            "Premium AR-15 and AR-10 maker. DDM4 series is the benchmark for hard-use precision ARs. "
            "Cold hammer-forged barrels, most components made in-house."
        ),
    },
    {
        "name": "Knight's Armament",
        "alt_names": ["KAC", "Knights Armament"],
        "website_url": "https://www.knightarmco.com",
        "type_tags": ["rifle_maker"],
        "country": "USA",
        "notes": (
            "SR-25 is the US military semi-auto precision platform (M110 SASS). "
            "SR-15 for 5.56. Extremely high-end, limited availability, cult following."
        ),
    },
    {
        "name": "JP Enterprises",
        "alt_names": ["JP", "JPE"],
        "website_url": "https://www.jprifles.com",
        "type_tags": ["rifle_maker"],
        "country": "USA",
        "notes": (
            "Purpose-built competition gas guns. LRP-07 and CTR-02 are staples in PRS Gas Gun. "
            "Known for tuned gas systems and match barrels."
        ),
    },
    {
        "name": "LaRue Tactical",
        "alt_names": ["LaRue"],
        "website_url": "https://www.larue.com",
        "type_tags": ["rifle_maker"],
        "country": "USA",
        "notes": (
            "OBR (Optimized Battle Rifle) and PredatAR are legendary for accuracy. "
            "Often described as the most accurate factory AR. Cult following."
        ),
    },
    {
        "name": "Aero Precision",
        "alt_names": ["Aero"],
        "website_url": "https://www.aeroprecisionusa.com",
        "type_tags": ["rifle_maker"],
        "country": "USA",
        "notes": (
            "Major OEM supplier — makes receivers for many other brands. M5 (AR-10) and AR-15 lines "
            "are the go-to for builders. Solus bolt-action line gaining traction in precision circles."
        ),
    },
    # --- Phase 1.5: AR Rifle Manufacturers — Tier 2 ---
    {
        "name": "Bravo Company",
        "alt_names": ["BCM", "Bravo Company Manufacturing", "Bravo Company MFG"],
        "website_url": "https://www.bravocompanymfg.com",
        "type_tags": ["rifle_maker"],
        "country": "USA",
        "notes": (
            "Best value in the duty-grade AR segment. Not competition-focused, "
            "but hugely popular among serious shooters."
        ),
    },
    {
        "name": "Lewis Machine & Tool",
        "alt_names": ["LMT", "Lewis Machine"],
        "website_url": "https://www.lmtdefense.com",
        "type_tags": ["rifle_maker"],
        "country": "USA",
        "notes": (
            "Monolithic upper receiver design (MRP). .308 MWS is a respected precision platform. "
            "Quick-change barrel system. Military contracts worldwide."
        ),
    },
    {
        "name": "Palmetto State Armory",
        "alt_names": ["PSA"],
        "website_url": "https://www.palmettostatearmory.com",
        "type_tags": ["rifle_maker", "ammo_maker"],
        "country": "USA",
        "notes": (
            "Massive volume, aggressive pricing. Gen3 PA-10 in 6.5 CM is surprisingly capable. "
            "Also owns DAGR Arms and other brands. Sheer volume means many users will own one."
        ),
    },
    {
        "name": "Geissele Automatics",
        "alt_names": ["Geissele"],
        "website_url": "https://www.geissele.com",
        "type_tags": ["rifle_maker", "parts_maker"],
        "country": "USA",
        "notes": (
            "Known primarily for triggers (SSA-E is the gold standard AR trigger). "
            "Super Duty rifle is now a benchmark premium AR. Most precision AR shooters have a Geissele trigger."
        ),
    },
    {
        "name": "LWRC International",
        "alt_names": ["LWRC", "LWRCI"],
        "website_url": "https://www.lwrci.com",
        "type_tags": ["rifle_maker"],
        "country": "USA",
        "notes": "Short-stroke piston ARs. REPR in .308 is a legitimate precision platform. Niche but respected.",
    },
    # --- Optic Manufacturers ---
    {
        "name": "Vortex Optics",
        "alt_names": ["Vortex"],
        "website_url": "https://www.vortexoptics.com",
        "type_tags": ["optic_maker"],
        "country": "USA",
        "notes": "Dominant precision optics brand. Viper PST Gen II and Razor HD Gen III are PRS staples.",
    },
    {
        "name": "Nightforce Optics",
        "alt_names": ["Nightforce", "NF"],
        "website_url": "https://www.nightforceoptics.com",
        "type_tags": ["optic_maker"],
        "country": "USA",
        "notes": "Premium precision optics. ATACR and NX8 lines dominate competitive and military use.",
    },
    {
        "name": "Leupold",
        "alt_names": ["Leupold & Stevens"],
        "website_url": "https://www.leupold.com",
        "type_tags": ["optic_maker"],
        "country": "USA",
        "notes": "Mark 5HD is the precision line. Long heritage in American optics.",
    },
    {
        "name": "Kahles",
        "alt_names": [],
        "website_url": "https://www.kahles.at",
        "type_tags": ["optic_maker"],
        "country": "Austria",
        "notes": "Oldest riflescope manufacturer (est. 1898). K525i is highly regarded in PRS.",
    },
    {
        "name": "Sig Sauer",
        "alt_names": ["Sig", "SIG SAUER"],
        "website_url": "https://www.sigsauer.com",
        "type_tags": ["optic_maker", "rifle_maker"],
        "country": "USA",
        "notes": "Tango6T adopted by US Army (SDMR). Also makes Cross bolt-action rifle.",
    },
    {
        "name": "Zero Compromise Optics",
        "alt_names": ["ZCO"],
        "website_url": "https://www.zerocompromiseoptics.com",
        "type_tags": ["optic_maker"],
        "country": "Austria",
        "notes": "Ultra-premium optics. ZC527 is considered the best precision scope available. Small batch.",
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
        "popularity_rank": 1,
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
        "popularity_rank": 2,
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
        "popularity_rank": 3,
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
        "popularity_rank": 4,
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
        "popularity_rank": 5,
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
        "popularity_rank": 6,
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
        "popularity_rank": 7,
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
        "popularity_rank": 8,
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
        "popularity_rank": 9,
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
        "popularity_rank": 10,
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
        "popularity_rank": 11,
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
        "popularity_rank": 12,
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
        "popularity_rank": 13,
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
        "popularity_rank": 14,
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
        "popularity_rank": 15,
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
        "popularity_rank": 16,
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
        "popularity_rank": 17,
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
        "popularity_rank": 18,
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
        "popularity_rank": 19,
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
        "popularity_rank": 20,
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
        "popularity_rank": 21,
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
        "popularity_rank": 22,
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
        "popularity_rank": 23,
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
        "popularity_rank": 24,
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
        "popularity_rank": 25,
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
    # --- Manufacturer aliases ---
    {"entity_type": "manufacturer", "entity_name": "Hornady", "alias": "Hornaday", "alias_type": "misspelling"},
    {"entity_type": "manufacturer", "entity_name": "Berger Bullets", "alias": "Burger", "alias_type": "misspelling"},
    {"entity_type": "manufacturer", "entity_name": "Berger Bullets", "alias": "Berger", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "Federal Premium", "alias": "Federal", "alias_type": "abbreviation"},
    {
        "entity_type": "manufacturer",
        "entity_name": "Federal Premium",
        "alias": "Federal Ammunition",
        "alias_type": "alternate_name",
    },
    {"entity_type": "manufacturer", "entity_name": "Sierra Bullets", "alias": "Sierra", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "Sierra Bullets", "alias": "Seirra", "alias_type": "misspelling"},
    {"entity_type": "manufacturer", "entity_name": "Barnes Bullets", "alias": "Barnes", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "Savage Arms", "alias": "Savage", "alias_type": "abbreviation"},
    {
        "entity_type": "manufacturer",
        "entity_name": "Remington",
        "alias": "Remington Arms",
        "alias_type": "alternate_name",
    },
    {"entity_type": "manufacturer", "entity_name": "Remington", "alias": "Big Green", "alias_type": "nickname"},
    {"entity_type": "manufacturer", "entity_name": "Lapua", "alias": "Lupua", "alias_type": "misspelling"},
    {"entity_type": "manufacturer", "entity_name": "Nosler", "alias": "Nossler", "alias_type": "misspelling"},
    {
        "entity_type": "manufacturer",
        "entity_name": "Winchester",
        "alias": "Winchester Ammunition",
        "alias_type": "alternate_name",
    },
    {
        "entity_type": "manufacturer",
        "entity_name": "Masterpiece Arms",
        "alias": "MPA",
        "alias_type": "abbreviation",
    },
    {
        "entity_type": "manufacturer",
        "entity_name": "Seekins Precision",
        "alias": "Seekins",
        "alias_type": "abbreviation",
    },
    # --- Manufacturer aliases: Black Hills Ammunition ---
    {
        "entity_type": "manufacturer",
        "entity_name": "Black Hills Ammunition",
        "alias": "Black Hills",
        "alias_type": "abbreviation",
    },
    {
        "entity_type": "manufacturer",
        "entity_name": "Black Hills Ammunition",
        "alias": "BHA",
        "alias_type": "abbreviation",
    },
    {
        "entity_type": "manufacturer",
        "entity_name": "Black Hills Ammunition",
        "alias": "BH Ammo",
        "alias_type": "abbreviation",
    },
    # --- Manufacturer aliases: Sellier & Bellot ---
    {
        "entity_type": "manufacturer",
        "entity_name": "Sellier & Bellot",
        "alias": "S&B",
        "alias_type": "abbreviation",
    },
    {
        "entity_type": "manufacturer",
        "entity_name": "Sellier & Bellot",
        "alias": "Sellier and Bellot",
        "alias_type": "alternate_name",
    },
    # --- Manufacturer aliases: IMI Systems ---
    {
        "entity_type": "manufacturer",
        "entity_name": "IMI Systems",
        "alias": "IMI",
        "alias_type": "abbreviation",
    },
    {
        "entity_type": "manufacturer",
        "entity_name": "IMI Systems",
        "alias": "IMI Ammunition",
        "alias_type": "alternate_name",
    },
    {
        "entity_type": "manufacturer",
        "entity_name": "IMI Systems",
        "alias": "Israeli Military Industries",
        "alias_type": "alternate_name",
    },
    # --- Manufacturer aliases: Prvi Partizan ---
    {
        "entity_type": "manufacturer",
        "entity_name": "Prvi Partizan",
        "alias": "PPU",
        "alias_type": "abbreviation",
    },
    {
        "entity_type": "manufacturer",
        "entity_name": "Prvi Partizan",
        "alias": "Privi Partizan",
        "alias_type": "misspelling",
    },
    {
        "entity_type": "manufacturer",
        "entity_name": "Prvi Partizan",
        "alias": "Privi",
        "alias_type": "misspelling",
    },
    # --- Manufacturer aliases: Daniel Defense ---
    {"entity_type": "manufacturer", "entity_name": "Daniel Defense", "alias": "DD", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "Daniel Defense", "alias": "Dan Def", "alias_type": "abbreviation"},
    # --- Manufacturer aliases: Knight's Armament ---
    {
        "entity_type": "manufacturer",
        "entity_name": "Knight's Armament",
        "alias": "KAC",
        "alias_type": "abbreviation",
    },
    {
        "entity_type": "manufacturer",
        "entity_name": "Knight's Armament",
        "alias": "Knight's",
        "alias_type": "abbreviation",
    },
    {
        "entity_type": "manufacturer",
        "entity_name": "Knight's Armament",
        "alias": "Knights Armament",
        "alias_type": "alternate_name",
    },
    # --- Manufacturer aliases: JP Enterprises ---
    {"entity_type": "manufacturer", "entity_name": "JP Enterprises", "alias": "JP", "alias_type": "abbreviation"},
    {"entity_type": "manufacturer", "entity_name": "JP Enterprises", "alias": "JPE", "alias_type": "abbreviation"},
    # --- Manufacturer aliases: LaRue Tactical ---
    {"entity_type": "manufacturer", "entity_name": "LaRue Tactical", "alias": "LaRue", "alias_type": "abbreviation"},
    # --- Manufacturer aliases: Aero Precision ---
    {"entity_type": "manufacturer", "entity_name": "Aero Precision", "alias": "Aero", "alias_type": "abbreviation"},
    # --- Manufacturer aliases: Bravo Company ---
    {"entity_type": "manufacturer", "entity_name": "Bravo Company", "alias": "BCM", "alias_type": "abbreviation"},
    {
        "entity_type": "manufacturer",
        "entity_name": "Bravo Company",
        "alias": "Bravo Company Manufacturing",
        "alias_type": "alternate_name",
    },
    {
        "entity_type": "manufacturer",
        "entity_name": "Bravo Company",
        "alias": "Bravo Company MFG",
        "alias_type": "abbreviation",
    },
    # --- Manufacturer aliases: Lewis Machine & Tool ---
    {
        "entity_type": "manufacturer",
        "entity_name": "Lewis Machine & Tool",
        "alias": "LMT",
        "alias_type": "abbreviation",
    },
    {
        "entity_type": "manufacturer",
        "entity_name": "Lewis Machine & Tool",
        "alias": "Lewis Machine",
        "alias_type": "abbreviation",
    },
    # --- Manufacturer aliases: Palmetto State Armory ---
    {
        "entity_type": "manufacturer",
        "entity_name": "Palmetto State Armory",
        "alias": "PSA",
        "alias_type": "abbreviation",
    },
    # --- Manufacturer aliases: Geissele Automatics ---
    {
        "entity_type": "manufacturer",
        "entity_name": "Geissele Automatics",
        "alias": "Geissele",
        "alias_type": "abbreviation",
    },
    # --- Manufacturer aliases: LWRC International ---
    {
        "entity_type": "manufacturer",
        "entity_name": "LWRC International",
        "alias": "LWRC",
        "alias_type": "abbreviation",
    },
    {
        "entity_type": "manufacturer",
        "entity_name": "LWRC International",
        "alias": "LWRCI",
        "alias_type": "abbreviation",
    },
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
    # --- Optic manufacturer aliases ---
    {
        "entity_type": "manufacturer",
        "entity_name": "Vortex Optics",
        "alias": "Vortex",
        "alias_type": "abbreviation",
    },
    {
        "entity_type": "manufacturer",
        "entity_name": "Nightforce Optics",
        "alias": "Nightforce",
        "alias_type": "abbreviation",
    },
    {
        "entity_type": "manufacturer",
        "entity_name": "Nightforce Optics",
        "alias": "NF",
        "alias_type": "abbreviation",
    },
    {
        "entity_type": "manufacturer",
        "entity_name": "Leupold",
        "alias": "Leupold & Stevens",
        "alias_type": "alternate_name",
    },
    {
        "entity_type": "manufacturer",
        "entity_name": "Sig Sauer",
        "alias": "Sig",
        "alias_type": "abbreviation",
    },
    {
        "entity_type": "manufacturer",
        "entity_name": "Sig Sauer",
        "alias": "SIG SAUER",
        "alias_type": "alternate_name",
    },
    {
        "entity_type": "manufacturer",
        "entity_name": "Zero Compromise Optics",
        "alias": "ZCO",
        "alias_type": "abbreviation",
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
