"""
Examples of using the JBM Ballistics Scraper

Demonstrates:
1. Basic queries with default parameters
2. Customizing ballistic parameters
3. Atmospheric variations
4. Wind and spin drift isolation
5. Analyzing validation results
"""

import time
from jbm_scraper import JBMScraper, JBMInput
from validation_matrix import ValidationSuite, CARTRIDGES


def example_1_basic_query():
    """
    Example 1: Basic query with default parameters
    """
    print("\n" + "=" * 70)
    print("Example 1: Basic Query")
    print("=" * 70)

    scraper = JBMScraper()

    # Create input with just BC and velocity
    params = JBMInput(
        bc_v=0.5,
        m_vel_v=3000,
    )

    print(f"Submitting query with BC={params.bc_v}, MV={params.m_vel_v} ft/s...")
    results = scraper.query(params)

    print(f"\nTrajectory Table ({len(results)} points):")
    print("Range(yd)  Drop(in)  Drop(mil)  Wind(in)  Wind(mil)  Vel(fps)   Mach  Time(s)")
    print("-" * 77)

    for r in results[:6]:  # Show first 6 points
        print(
            f"{r.range_yd:7.0f}    "
            f"{r.drop_in:7.2f}   {r.drop_mil:8.2f}   "
            f"{r.windage_in:7.2f}   {r.windage_mil:8.2f}   "
            f"{r.velocity_fps:7.1f}   {r.mach:5.2f}  {r.tof_s:6.3f}"
        )

    print("\n... (additional points omitted)")


def example_2_standard_load():
    """
    Example 2: Query with standard .308 Winchester load
    """
    print("\n" + "=" * 70)
    print("Example 2: Standard .308 Winchester Load")
    print("=" * 70)

    scraper = JBMScraper()

    # .308 Winchester: 175gr, G7 BC=0.264, MV=2600
    params = JBMInput(
        bc_v=0.264,
        d_f_v=4,  # G7
        bt_wgt_v=175.0,
        cal_v=0.308,
        m_vel_v=2600.0,
        b_twt_v=10.0,
        blt_len_v=1.24,
    )

    print(".308 Winchester 175gr, G7 BC=0.264, MV=2600 ft/s")
    results = scraper.query(params)

    print(f"\nDrop and Wind at Common Ranges:")
    print("Range    Drop      Windage   Energy")
    print("(yd)     (in)      (in)      (ft-lb)")
    print("-" * 40)

    for r in [results[1], results[3], results[5], results[7], results[9]]:  # 100-500yd
        print(f"{r.range_yd:4.0f}     {r.drop_in:6.2f}    {r.windage_in:6.2f}    {r.energy_ftlbs:7.0f}")


def example_3_atmosphere_variation():
    """
    Example 3: Test at different atmospheric conditions
    """
    print("\n" + "=" * 70)
    print("Example 3: Atmospheric Variations")
    print("=" * 70)

    scraper = JBMScraper()

    # Base parameters
    base_params = JBMInput(
        bc_v=0.326,
        d_f_v=4,  # G7
        m_vel_v=2710,
    )

    atmospheres = [
        ("Cold", {"tmp_v": 0, "tmp_u": 19}),
        ("Standard", {"tmp_v": 59, "tmp_u": 19}),
        ("Hot", {"tmp_v": 100, "tmp_u": 19}),
    ]

    results_by_condition = {}

    print("Testing at different temperatures...")
    for name, atm_params in atmospheres:
        params = JBMInput(
            bc_v=base_params.bc_v,
            d_f_v=base_params.d_f_v,
            m_vel_v=base_params.m_vel_v,
            tmp_v=atm_params["tmp_v"],
            tmp_u=atm_params["tmp_u"],
        )

        print(f"  {name} ({atm_params['tmp_v']}°F)...", end=" ", flush=True)
        results = scraper.query(params)
        results_by_condition[name] = results
        print(f"OK ({len(results)} points)")

        # Rate limit between requests
        time.sleep(1.0)

    # Compare drop at 500 yards
    print(f"\nDrop at 500 yards:")
    for name in ["Cold", "Standard", "Hot"]:
        result_500 = next((r for r in results_by_condition[name] if r.range_yd == 500), None)
        if result_500:
            print(f"  {name:12s}: {result_500.drop_in:7.2f} in")


def example_4_wind_spin_drift_isolation():
    """
    Example 4: Isolate wind drift from spin drift using ON/OFF toggle
    """
    print("\n" + "=" * 70)
    print("Example 4: Wind vs Spin Drift Isolation")
    print("=" * 70)

    scraper = JBMScraper()

    # 6.5 Creedmoor parameters
    base_params = JBMInput(
        bc_v=0.326,
        d_f_v=4,  # G7
        bt_wgt_v=140,
        cal_v=0.264,
        m_vel_v=2710,
        b_twt_v=8,
        blt_len_v=1.35,
        spd_wnd_v=10.0,  # 10 mph crosswind
        ang_wnd_v=90.0,  # 90 degrees = full crosswind
    )

    # Case 1: With spin drift
    print("Submitting Case 1: 10 mph crosswind WITH spin drift...", end=" ", flush=True)
    params_with_spin = JBMInput(
        bc_v=base_params.bc_v,
        d_f_v=base_params.d_f_v,
        bt_wgt_v=base_params.bt_wgt_v,
        cal_v=base_params.cal_v,
        m_vel_v=base_params.m_vel_v,
        b_twt_v=base_params.b_twt_v,
        blt_len_v=base_params.blt_len_v,
        spd_wnd_v=base_params.spd_wnd_v,
        ang_wnd_v=base_params.ang_wnd_v,
        inc_drf_v=True,  # SPIN DRIFT ON
    )

    results_with_spin = scraper.query(params_with_spin)
    print("OK")

    time.sleep(1.0)

    # Case 2: Without spin drift
    print("Submitting Case 2: 10 mph crosswind WITHOUT spin drift...", end=" ", flush=True)
    params_no_spin = JBMInput(
        bc_v=base_params.bc_v,
        d_f_v=base_params.d_f_v,
        bt_wgt_v=base_params.bt_wgt_v,
        cal_v=base_params.cal_v,
        m_vel_v=base_params.m_vel_v,
        b_twt_v=base_params.b_twt_v,
        blt_len_v=base_params.blt_len_v,
        spd_wnd_v=base_params.spd_wnd_v,
        ang_wnd_v=base_params.ang_wnd_v,
        inc_drf_v=False,  # SPIN DRIFT OFF
    )

    results_no_spin = scraper.query(params_no_spin)
    print("OK")

    # Compare
    print(f"\nWindage Comparison (10 mph crosswind):")
    print("Range    With Spin    Without Spin    Spin Drift Only")
    print("(yd)     Drift (in)   Drift (in)      (in)")
    print("-" * 55)

    for r_with, r_without in zip(results_with_spin, results_no_spin):
        spin_drift_component = r_with.windage_in - r_without.windage_in
        print(
            f"{r_with.range_yd:4.0f}     "
            f"{r_with.windage_in:8.2f}     "
            f"{r_without.windage_in:8.2f}      "
            f"{spin_drift_component:8.2f}"
        )


def example_5_validation_suite_summary():
    """
    Example 5: Generate and summarize validation test suite
    """
    print("\n" + "=" * 70)
    print("Example 5: Validation Suite Summary")
    print("=" * 70)

    suite = ValidationSuite()

    # Get summary
    summary = suite.get_suite_summary()
    total = sum(summary.values())

    print("\nTest Suite Breakdown:")
    print("-" * 50)
    for name, count in sorted(summary.items()):
        print(f"  {name:20s}: {count:3d} test cases")
    print("-" * 50)
    print(f"  {'TOTAL':20s}: {total:3d} test cases")

    print(f"\nEstimated execution time: ~{total // 60} minutes at 1 request/sec")

    # Show sample baseline case
    print("\nSample Baseline Test Cases:")
    print("-" * 50)

    baseline = suite.generate_baseline_cases()
    for i, case in enumerate(baseline[:3], 1):
        print(f"\nCase {i}:")
        print(f"  BC: {case.bc_v}")
        print(f"  Drag Function: {case.d_f_v} ({'G1' if case.d_f_v == 0 else f'G{case.d_f_v}'})")
        print(f"  Bullet Weight: {case.bt_wgt_v} gr")
        print(f"  Caliber: {case.cal_v}")
        print(f"  Muzzle Velocity: {case.m_vel_v} ft/s")


def example_6_bc_sensitivity():
    """
    Example 6: Test BC sensitivity
    """
    print("\n" + "=" * 70)
    print("Example 6: Ballistic Coefficient Sensitivity")
    print("=" * 70)

    scraper = JBMScraper()

    # 6.5 Creedmoor nominal BC = 0.326
    nominal_bc = 0.326

    bc_values = [
        nominal_bc * 0.8,
        nominal_bc * 0.9,
        nominal_bc * 1.0,
        nominal_bc * 1.1,
        nominal_bc * 1.2,
    ]

    results_by_bc = {}

    print("Testing BC sensitivity (6.5 Creedmoor)...")
    for bc in bc_values:
        params = JBMInput(
            bc_v=bc,
            d_f_v=4,  # G7
            bt_wgt_v=140,
            cal_v=0.264,
            m_vel_v=2710,
            b_twt_v=8,
            blt_len_v=1.35,
        )

        pct = (bc / nominal_bc - 1) * 100
        print(f"  BC {bc:.3f} ({pct:+.0f}%)...", end=" ", flush=True)
        results = scraper.query(params)
        results_by_bc[f"{pct:+.0f}%"] = results
        print("OK")

        time.sleep(1.0)

    # Compare drop at 800 yards
    print(f"\nDrop at 800 yards vs nominal BC:")
    print("BC Adjustment    Drop (in)    Difference")
    print("-" * 45)

    nominal_drop_800 = next((r for r in results_by_bc["0%"] if r.range_yd == 800), None)
    if nominal_drop_800:
        nominal_value = nominal_drop_800.drop_in

        for pct in ["-20%", "-10%", "0%", "+10%", "+20%"]:
            result = next((r for r in results_by_bc[pct] if r.range_yd == 800), None)
            if result:
                diff = result.drop_in - nominal_value
                print(f"  {pct:>5s}             {result.drop_in:7.2f}    {diff:+7.2f}")


def example_7_list_cartridges():
    """
    Example 7: Show available test cartridges
    """
    print("\n" + "=" * 70)
    print("Example 7: Available Test Cartridges")
    print("=" * 70)

    print("\nStandard test cartridges in validation suite:")
    print("-" * 70)
    print(f"{'Cartridge':20s} {'Bullet':15s} {'BC':8s} {'MV':8s} {'Twist':8s}")
    print("-" * 70)

    for key, cart in CARTRIDGES.items():
        df_name = {0: "G1", 4: "G7", 1: "G2", 2: "G5", 3: "G6"}.get(cart.d_f_v, f"G{cart.d_f_v}")
        print(
            f"{cart.name:20s} "
            f"{cart.bt_wgt_v:5.0f}gr/{cart.cal_v:5.3f}\"  "
            f"{cart.bc_v:6.3f}({df_name:2s}) "
            f"{cart.m_vel_v:6.0f}ft/s "
            f"{cart.b_twt_v:5.1f}\""
        )

    print("-" * 70)


def main():
    """Run all examples"""
    print("\nJBM Ballistics Scraper - Examples")
    print("=" * 70)

    # Note: Examples 1-4 make real HTTP requests
    # Examples 5-7 are informational only

    try:
        example_1_basic_query()
        time.sleep(1)

        example_2_standard_load()
        time.sleep(1)

        example_3_atmosphere_variation()
        time.sleep(1)

        example_4_wind_spin_drift_isolation()

        example_5_validation_suite_summary()
        example_6_bc_sensitivity()
        example_7_list_cartridges()

        print("\n" + "=" * 70)
        print("Examples completed successfully!")
        print("=" * 70)

    except Exception as e:
        print(f"\nError during examples: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
