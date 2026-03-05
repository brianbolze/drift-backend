"""
Decomposed Validation Test Generator for JBM Ballistics

Generates test matrices that isolate individual physics components.
Each test suite focuses on a specific aspect of ballistic behavior:
- Baseline cases test the core trajectory engine (gravity + drag)
- Atmosphere sweeps isolate atmospheric effects
- Wind sweeps separate wind drift from other effects
- Spin drift sweeps use the ON/OFF toggle to isolate Coriolis effects
- Shooting angle sweeps test cosine corrections
- And more...

This decomposed approach enables validation of each physics component independently.
"""

from dataclasses import dataclass, field
from typing import Dict, List

from jbm_scraper import JBMInput


@dataclass
class TestCartridge:
    """Standard test cartridge specifications"""

    name: str
    bt_wgt_v: float  # Bullet weight in grains
    cal_v: float  # Caliber in inches
    d_f_v: int  # Drag function (0=G1, 4=G7, etc)
    bc_v: float  # Ballistic coefficient
    m_vel_v: float  # Muzzle velocity in ft/s
    b_twt_v: float  # Barrel twist in inches
    blt_len_v: float  # Bullet length in inches


# Standard test cartridges
CARTRIDGES = {
    "6.5_creedmoor": TestCartridge(
        name="6.5 Creedmoor",
        bt_wgt_v=140.0,
        cal_v=0.264,
        d_f_v=4,  # G7
        bc_v=0.326,
        m_vel_v=2710.0,
        b_twt_v=8.0,
        blt_len_v=1.35,
    ),
    "308_win": TestCartridge(
        name=".308 Winchester",
        bt_wgt_v=175.0,
        cal_v=0.308,
        d_f_v=4,  # G7
        bc_v=0.264,
        m_vel_v=2600.0,
        b_twt_v=10.0,
        blt_len_v=1.24,
    ),
    "338_lapua": TestCartridge(
        name=".338 Lapua",
        bt_wgt_v=300.0,
        cal_v=0.338,
        d_f_v=4,  # G7
        bc_v=0.419,
        m_vel_v=2700.0,
        b_twt_v=10.0,
        blt_len_v=1.7,
    ),
    "556_nato": TestCartridge(
        name="5.56 NATO",
        bt_wgt_v=77.0,
        cal_v=0.224,
        d_f_v=0,  # G1
        bc_v=0.372,
        m_vel_v=2750.0,
        b_twt_v=8.0,
        blt_len_v=1.0,
    ),
}


class ValidationSuite:
    """
    Generates decomposed test matrices for ballistic validation.

    Each method returns a list of JBMInput objects configured to test
    a specific physics component in isolation.
    """

    # Standard test ranges: 0-1000 yards in 100-yard increments
    STANDARD_RANGES = {
        "rng_min_v": 0,
        "rng_max_v": 1000,
        "rng_inc_v": 100,
        "rng_zer_v": 100,
    }

    @staticmethod
    def _make_base_input(cartridge: TestCartridge) -> JBMInput:
        """Create a base JBMInput with standard test conditions"""
        return JBMInput(
            bt_wgt_v=cartridge.bt_wgt_v,
            cal_v=cartridge.cal_v,
            d_f_v=cartridge.d_f_v,
            bc_v=cartridge.bc_v,
            m_vel_v=cartridge.m_vel_v,
            b_twt_v=cartridge.b_twt_v,
            blt_len_v=cartridge.blt_len_v,
            # Standard atmosphere conditions
            tmp_v=59.0,  # 59°F
            tmp_u=19,
            prs_v=29.92,  # Standard pressure
            prs_u=22,
            hum_v=0.0,
            # Standard range settings
            rng_min_v=0,
            rng_max_v=1000,
            rng_inc_v=100,
            rng_zer_v=100,
            # Output in both inches and mils
            col1_un_u=8,  # inches
            col2_un_u=2,  # mrad
        )

    def generate_baseline_cases(self) -> List[JBMInput]:
        """
        Core trajectory cases: different cartridges, both drag models, standard conditions, no wind.
        Tests the basic trajectory engine (gravity + drag only).

        Cases include:
        - Each standard cartridge with its configured drag function
        - Alternative drag function for comparison (G1 vs G7)
        """
        cases = []

        # Test each cartridge with its configured drag function
        for cart_key, cartridge in CARTRIDGES.items():
            base = self._make_base_input(cartridge)
            base.spd_wnd_v = 0.0  # No wind
            base.inc_drf_v = False  # No spin drift
            cases.append(base)

        # Alternative drag function variants (G1 for G7 cartridges, etc.)
        # This tests the drag table implementation
        for cart_key, cartridge in CARTRIDGES.items():
            if cartridge.d_f_v == 4:  # G7 cartridges - also test with G1
                base = self._make_base_input(cartridge)
                base.d_f_v = 0  # Switch to G1
                # Adjust BC for G1 (multiply G7 BC by ~1.5 as approximation)
                base.bc_v = cartridge.bc_v * 1.5
                base.spd_wnd_v = 0.0
                base.inc_drf_v = False
                cases.append(base)

        return cases

    def generate_atmosphere_sweep(self) -> List[JBMInput]:
        """
        Vary temperature, pressure, humidity, altitude independently.
        Tests the atmosphere model in isolation.

        Configuration:
        - Temperature: 0°F, 30°F, 59°F (std), 90°F, 110°F
        - Pressure: 25.0, 27.0, 29.92 (std), 31.0, 32.0 inHg
        - Humidity: 0%, 25%, 50%, 75%, 100%
        - Altitude: 0, 2500, 5000, 7500, 10000 ft (with std atmosphere)
        """
        cases = []

        # Use 6.5 Creedmoor as reference
        base = self._make_base_input(CARTRIDGES["6.5_creedmoor"])
        base.spd_wnd_v = 0.0
        base.inc_drf_v = False

        # Temperature sweep (hold pressure, humidity constant)
        for temp_f in [0, 30, 59, 90, 110]:
            case = self._make_base_input(CARTRIDGES["6.5_creedmoor"])
            case.tmp_v = float(temp_f)
            case.tmp_u = 19  # Fahrenheit
            case.prs_v = 29.92
            case.hum_v = 0.0
            case.spd_wnd_v = 0.0
            case.inc_drf_v = False
            cases.append(case)

        # Pressure sweep (hold temperature, humidity constant)
        for prs in [25.0, 27.0, 29.92, 31.0, 32.0]:
            case = self._make_base_input(CARTRIDGES["6.5_creedmoor"])
            case.tmp_v = 59.0
            case.prs_v = prs
            case.prs_u = 22  # inHg
            case.hum_v = 0.0
            case.spd_wnd_v = 0.0
            case.inc_drf_v = False
            cases.append(case)

        # Humidity sweep (hold temperature, pressure constant)
        for hum in [0, 25, 50, 75, 100]:
            case = self._make_base_input(CARTRIDGES["6.5_creedmoor"])
            case.tmp_v = 59.0
            case.prs_v = 29.92
            case.hum_v = float(hum)
            case.spd_wnd_v = 0.0
            case.inc_drf_v = False
            cases.append(case)

        # Altitude sweep with standard atmosphere checkbox enabled
        for alt_ft in [0, 2500, 5000, 7500, 10000]:
            case = self._make_base_input(CARTRIDGES["6.5_creedmoor"])
            case.alt_v = float(alt_ft)
            case.alt_u = 10  # feet
            case.std_alt_v = True  # Enable standard atmosphere at altitude
            case.spd_wnd_v = 0.0
            case.inc_drf_v = False
            cases.append(case)

        return cases

    def generate_wind_sweep(self) -> List[JBMInput]:
        """
        Vary wind speed and angle.
        Tests wind drift calculation isolated from other effects.

        Configuration:
        - Wind speeds: 0, 5, 10, 15, 20 mph
        - Wind angles: 0 (headwind), 45, 90 (full cross), 135, 180 (tailwind), 270
        - Run EACH case WITH and WITHOUT spin drift
          The DIFFERENCE in windage is the wind component isolation

        Returns cases with BOTH spin drift on and off for each wind condition.
        """
        cases = []

        # Use 6.5 Creedmoor as reference
        wind_speeds = [0, 5, 10, 15, 20]
        wind_angles = [0, 45, 90, 135, 180, 270]

        for speed in wind_speeds:
            for angle in wind_angles:
                # Case with spin drift ON
                case_on = self._make_base_input(CARTRIDGES["6.5_creedmoor"])
                case_on.spd_wnd_v = float(speed)
                case_on.spd_wnd_u = 14  # mph
                case_on.ang_wnd_v = float(angle)
                case_on.inc_drf_v = True  # Spin drift ON
                case_on._wind_test_label = f"wind_on_speed{speed}_angle{angle}"
                cases.append(case_on)

                # Case with spin drift OFF
                case_off = self._make_base_input(CARTRIDGES["6.5_creedmoor"])
                case_off.spd_wnd_v = float(speed)
                case_off.spd_wnd_u = 14  # mph
                case_off.ang_wnd_v = float(angle)
                case_off.inc_drf_v = False  # Spin drift OFF
                case_off._wind_test_label = f"wind_off_speed{speed}_angle{angle}"
                cases.append(case_off)

        return cases

    def generate_spin_drift_sweep(self) -> List[JBMInput]:
        """
        Vary twist rate and direction to isolate spin drift (Coriolis effect).

        Configuration:
        - Twist rates: 7, 8, 9, 10, 11, 12, 14 inches
        - Twist direction: Left (0), Right (1)
        - Run EACH case WITH and WITHOUT the spin drift toggle
          The DIFFERENCE in windage is pure spin drift

        Returns cases with BOTH inc_drf ON and OFF for each twist configuration.
        """
        cases = []

        twist_rates = [7, 8, 9, 10, 11, 12, 14]
        twist_dirs = [0, 1]  # Left, Right

        for twist_rate in twist_rates:
            for twist_dir in twist_dirs:
                # Case with spin drift ON
                case_on = self._make_base_input(CARTRIDGES["6.5_creedmoor"])
                case_on.b_twt_v = float(twist_rate)
                case_on.b_twt_u = 8  # inches
                case_on.b_twt_dir_v = twist_dir
                case_on.spd_wnd_v = 0.0  # No wind - isolate spin drift
                case_on.inc_drf_v = True  # Spin drift ON
                case_on._spin_drift_label = f"spin_on_twist{twist_rate}_{['L', 'R'][twist_dir]}"
                cases.append(case_on)

                # Case with spin drift OFF
                case_off = self._make_base_input(CARTRIDGES["6.5_creedmoor"])
                case_off.b_twt_v = float(twist_rate)
                case_off.b_twt_u = 8  # inches
                case_off.b_twt_dir_v = twist_dir
                case_off.spd_wnd_v = 0.0
                case_off.inc_drf_v = False  # Spin drift OFF
                case_off._spin_drift_label = f"spin_off_twist{twist_rate}_{['L', 'R'][twist_dir]}"
                cases.append(case_off)

        return cases

    def generate_shooting_angle_sweep(self) -> List[JBMInput]:
        """
        Vary line-of-sight angle.
        Tests the cosine correction (gravity vector component along LOS).

        Configuration:
        - Line of sight angles: -30, -15, 0, 15, 30 degrees
        """
        cases = []

        los_angles = [-30, -15, 0, 15, 30]

        for los_angle in los_angles:
            case = self._make_base_input(CARTRIDGES["6.5_creedmoor"])
            case.los_v = float(los_angle)
            case.spd_wnd_v = 0.0
            case.inc_drf_v = False
            cases.append(case)

        return cases

    def generate_velocity_sweep(self) -> List[JBMInput]:
        """
        Vary muzzle velocity.
        Tests drag sensitivity and transonic behavior.

        Configuration:
        - Velocities: 2400, 2550, 2710, 2850, 3000 fps (around 6.5CM nominal)
        """
        cases = []

        velocities = [2400, 2550, 2710, 2850, 3000]

        for vel in velocities:
            case = self._make_base_input(CARTRIDGES["6.5_creedmoor"])
            case.m_vel_v = float(vel)
            case.m_vel_u = 16  # ft/s
            case.spd_wnd_v = 0.0
            case.inc_drf_v = False
            cases.append(case)

        return cases

    def generate_bc_sweep(self) -> List[JBMInput]:
        """
        Vary ballistic coefficient for the same bullet.
        Tests drag coefficient scaling and sensitivity.

        Configuration:
        - BC range: ±20% around the nominal BC in 5% steps
        """
        cases = []

        # Use 6.5 Creedmoor (BC = 0.326 G7)
        nominal_bc = CARTRIDGES["6.5_creedmoor"].bc_v

        # Generate BC values from 80% to 120% of nominal
        bc_multipliers = [0.80, 0.90, 1.00, 1.10, 1.20]

        for multiplier in bc_multipliers:
            case = self._make_base_input(CARTRIDGES["6.5_creedmoor"])
            case.bc_v = nominal_bc * multiplier
            case.spd_wnd_v = 0.0
            case.inc_drf_v = False
            cases.append(case)

        return cases

    def generate_drag_model_comparison(self) -> List[JBMInput]:
        """
        Same physical bullet tested with different drag functions.

        For each cartridge that has a G7 BC, also test with G1 (converting BC appropriately).
        Results should be CLOSE but not identical — validates drag table implementation.

        Configuration:
        - 6.5CM: G7 BC=0.326, also test G1 BC≈0.489 (G7*1.5)
        - .308 Win: G7 BC=0.264, also test G1 BC≈0.396
        - .338 Lapua: G7 BC=0.419, also test G1 BC≈0.629
        """
        cases = []

        g7_cartridges = [
            ("6.5_creedmoor", CARTRIDGES["6.5_creedmoor"]),
            ("308_win", CARTRIDGES["308_win"]),
            ("338_lapua", CARTRIDGES["338_lapua"]),
        ]

        for cart_key, cartridge in g7_cartridges:
            # Original G7 case
            case_g7 = self._make_base_input(cartridge)
            case_g7.d_f_v = 4  # G7
            case_g7.spd_wnd_v = 0.0
            case_g7.inc_drf_v = False
            cases.append(case_g7)

            # G1 equivalent case (convert BC)
            case_g1 = self._make_base_input(cartridge)
            case_g1.d_f_v = 0  # G1
            case_g1.bc_v = cartridge.bc_v * 1.5  # Approximate G7->G1 conversion
            case_g1.spd_wnd_v = 0.0
            case_g1.inc_drf_v = False
            cases.append(case_g1)

        return cases

    def generate_full_matrix(self) -> Dict[str, List[JBMInput]]:
        """
        Generate all test suites.

        Returns:
            Dictionary with suite names as keys and lists of JBMInput as values.
            Categories:
            - baseline: Core trajectory engine tests
            - atmosphere: Atmospheric model tests
            - wind: Wind drift calculation tests
            - spin_drift: Spin drift (Coriolis) tests
            - shooting_angle: Gravity vector component tests
            - velocity: Drag sensitivity tests
            - bc: Ballistic coefficient sensitivity tests
            - drag_model: Drag function comparison tests
        """
        return {
            "baseline": self.generate_baseline_cases(),
            "atmosphere": self.generate_atmosphere_sweep(),
            "wind": self.generate_wind_sweep(),
            "spin_drift": self.generate_spin_drift_sweep(),
            "shooting_angle": self.generate_shooting_angle_sweep(),
            "velocity": self.generate_velocity_sweep(),
            "bc": self.generate_bc_sweep(),
            "drag_model": self.generate_drag_model_comparison(),
        }

    def get_suite_summary(self) -> Dict[str, int]:
        """Get count of test cases in each suite"""
        full_matrix = self.generate_full_matrix()
        return {name: len(cases) for name, cases in full_matrix.items()}


if __name__ == "__main__":
    suite = ValidationSuite()

    # Print summary
    summary = suite.get_suite_summary()
    total = sum(summary.values())

    print("Validation Suite Summary")
    print("=" * 50)
    for name, count in summary.items():
        print(f"  {name:20s}: {count:3d} cases")
    print("=" * 50)
    print(f"  {'Total':20s}: {total:3d} cases")
    print()
    print("This will generate ~5 minutes of continuous requests at 1/sec rate limiting")
