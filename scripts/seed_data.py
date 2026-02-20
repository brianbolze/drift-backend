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

from rangefinder.database import get_engine, get_session_factory  # noqa: E402
from rangefinder.models import (  # noqa: E402
    Base,
    Caliber,
    Chamber,
    ChamberAcceptsCaliber,
    EntityAlias,
    Manufacturer,
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
# Seeding logic
# ---------------------------------------------------------------------------


def _build_caliber_lookup(session: Session) -> dict[str, str]:
    """Return {caliber.name: caliber.id} for all calibers in the DB."""
    return {c.name: c.id for c in session.query(Caliber).all()}


def _build_entity_lookup(session: Session) -> dict[tuple[str, str], str]:
    """Return {(entity_type, name): id} for manufacturers and calibers."""
    lookup: dict[tuple[str, str], str] = {}
    for m in session.query(Manufacturer).all():
        lookup[("manufacturer", m.name)] = m.id
    for c in session.query(Caliber).all():
        lookup[("caliber", c.name)] = c.id
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


def seed_entity_aliases(session: Session) -> None:
    entity_lookup = _build_entity_lookup(session)
    count = 0
    for data in ENTITY_ALIASES:
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
    seed_entity_aliases(session)
    session.commit()
    print("Done.")


def reset_seeded_tables(session: Session) -> None:
    """Delete all rows from seed-data tables (preserves schema)."""
    print("Resetting seed data tables...")
    session.query(EntityAlias).delete()
    session.query(ChamberAcceptsCaliber).delete()
    session.query(Chamber).delete()
    session.query(Caliber).delete()
    session.query(Manufacturer).delete()
    session.commit()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the RangeFinder backend database.")
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
