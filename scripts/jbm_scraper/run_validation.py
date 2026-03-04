"""
Run the full validation suite against JBM ballistics calculator.

This script:
1. Generates decomposed test cases from validation_matrix
2. Submits each case to JBM with 1 request/second rate limiting (respectful)
3. Captures results and raw HTML for auditability
4. Exports to JSON for comparison against our own solver

Usage:
    python run_validation.py [--suite baseline,wind,spin_drift] [--output results.json] [--dry-run]

Typical execution time: ~5 minutes for full suite (281 test cases)
"""

import json
import time
import logging
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

from jbm_scraper import JBMScraper, JBMInput, JBMResult
from validation_matrix import ValidationSuite

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class ValidationRunner:
    """Executes validation suite against JBM with rate limiting and result capture"""

    REQUEST_DELAY = 1.0  # 1 request per second - respectful to JBM's free service
    DEFAULT_OUTPUT = "jbm_validation_results.json"

    def __init__(self, rate_limit: float = REQUEST_DELAY, dry_run: bool = False):
        self.scraper = JBMScraper()
        self.rate_limit = rate_limit
        self.dry_run = dry_run
        self.results = {}
        self.errors = {}

    def run_suite(
        self,
        suite_name: str,
        test_cases: List[JBMInput],
        verbose: bool = True,
    ) -> tuple[Dict, List[str]]:
        """
        Execute a single validation suite.

        Args:
            suite_name: Name of the test suite
            test_cases: List of JBMInput objects to test
            verbose: Print progress

        Returns:
            Tuple of (results_dict, errors_list)
        """
        suite_results = {}
        suite_errors = []

        for idx, test_case in enumerate(test_cases, 1):
            case_name = f"{suite_name}_{idx:03d}"

            if verbose:
                print(f"  [{idx:3d}/{len(test_cases)}] {case_name}...", end=" ", flush=True)

            if self.dry_run:
                # Dry run: skip actual submission
                suite_results[case_name] = {
                    "status": "skipped (dry-run)",
                    "input": self._serialize_input(test_case),
                }
                print("skipped (dry-run)")
                time.sleep(0.1)  # Small delay even in dry-run
                continue

            try:
                # Submit to JBM
                start_time = time.time()
                trajectory = self.scraper.query(test_case)
                elapsed = time.time() - start_time

                # Serialize results
                suite_results[case_name] = {
                    "status": "success",
                    "input": self._serialize_input(test_case),
                    "trajectory": self._serialize_trajectory(trajectory),
                    "point_count": len(trajectory),
                    "elapsed_sec": round(elapsed, 2),
                    "html_length": len(test_case._raw_html) if test_case._raw_html else 0,
                }

                if verbose:
                    print(f"OK ({len(trajectory)} points, {elapsed:.2f}s)")

            except Exception as e:
                error_msg = str(e)
                suite_results[case_name] = {
                    "status": "error",
                    "error": error_msg,
                    "input": self._serialize_input(test_case),
                }
                suite_errors.append(f"{case_name}: {error_msg}")

                if verbose:
                    print(f"ERROR: {error_msg}")

            # Rate limiting: 1 request per second
            if idx < len(test_cases):
                time.sleep(self.rate_limit)

        return suite_results, suite_errors

    def run_full_validation(
        self,
        requested_suites: Optional[List[str]] = None,
        verbose: bool = True,
    ) -> tuple[Dict, Dict[str, List[str]]]:
        """
        Execute full validation suite.

        Args:
            requested_suites: List of suite names to run (None = all)
            verbose: Print progress

        Returns:
            Tuple of (all_results, all_errors)
        """
        # Generate all test suites
        validator = ValidationSuite()
        all_suites = validator.generate_full_matrix()

        # Filter to requested suites
        if requested_suites:
            suites_to_run = {
                name: cases
                for name, cases in all_suites.items()
                if name in requested_suites
            }
        else:
            suites_to_run = all_suites

        total_cases = sum(len(cases) for cases in suites_to_run.values())

        print(f"\nRunning validation suite ({total_cases} total cases)")
        print("=" * 70)

        all_results = {}
        all_errors = {}

        for suite_name, test_cases in suites_to_run.items():
            print(f"\n{suite_name:20s} ({len(test_cases):3d} cases)")
            print("-" * 70)

            suite_results, suite_errors = self.run_suite(
                suite_name, test_cases, verbose=verbose
            )

            all_results[suite_name] = suite_results
            all_errors[suite_name] = suite_errors

            # Print suite summary
            success_count = sum(
                1 for r in suite_results.values() if r.get("status") == "success"
            )
            error_count = sum(
                1 for r in suite_results.values() if r.get("status") == "error"
            )
            skip_count = sum(
                1 for r in suite_results.values() if "skipped" in r.get("status", "")
            )

            print(
                f"\nSuite summary: {success_count} success, "
                f"{error_count} error, {skip_count} skipped"
            )

        print("\n" + "=" * 70)
        print("Validation complete")

        return all_results, all_errors

    def export_json(self, results: Dict, errors: Dict[str, List[str]], output_file: str):
        """
        Export results to JSON file for analysis.

        Args:
            results: Results dictionary from run_full_validation
            errors: Errors dictionary from run_full_validation
            output_file: Path to output JSON file
        """
        export_data = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "jbm_url": self.scraper.URL,
                "rate_limit_sec": self.rate_limit,
                "dry_run": self.dry_run,
            },
            "results": results,
            "error_summary": {
                suite: len(errs) for suite, errs in errors.items()
            },
            "errors": errors,
        }

        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(export_data, f, indent=2)

        logger.info(f"Exported results to {output_path}")
        print(f"\nResults exported to: {output_path}")

    @staticmethod
    def _serialize_input(input_obj: JBMInput) -> Dict:
        """Serialize JBMInput for JSON storage"""
        return {
            "bc": input_obj.bc_v,
            "drag_function": input_obj.d_f_v,
            "bullet_weight_gr": input_obj.bt_wgt_v,
            "caliber_in": input_obj.cal_v,
            "bullet_length_in": input_obj.blt_len_v,
            "muzzle_velocity_fps": input_obj.m_vel_v,
            "barrel_twist_in": input_obj.b_twt_v,
            "twist_direction": ["left", "right"][input_obj.b_twt_dir_v],
            "wind_speed_mph": input_obj.spd_wnd_v,
            "wind_angle_deg": input_obj.ang_wnd_v,
            "los_angle_deg": input_obj.los_v,
            "cant_angle_deg": input_obj.cnt_v,
            "temperature_f": input_obj.tmp_v,
            "pressure_inhg": input_obj.prs_v,
            "humidity_pct": input_obj.hum_v,
            "altitude_ft": input_obj.alt_v,
            "include_spin_drift": input_obj.inc_drf_v,
            "range_settings": {
                "min_yd": input_obj.rng_min_v,
                "max_yd": input_obj.rng_max_v,
                "increment_yd": input_obj.rng_inc_v,
                "zero_range_yd": input_obj.rng_zer_v,
            },
        }

    @staticmethod
    def _serialize_trajectory(trajectory: List[JBMResult]) -> List[Dict]:
        """Serialize trajectory results for JSON storage"""
        return [
            {
                "range_yd": r.range_yd,
                "drop_in": r.drop_in,
                "drop_mil": r.drop_mil,
                "windage_in": r.windage_in,
                "windage_mil": r.windage_mil,
                "velocity_fps": r.velocity_fps,
                "mach": r.mach,
                "energy_ftlbs": r.energy_ftlbs,
                "time_of_flight_s": r.tof_s,
                "lead_in": r.lead_in,
                "lead_mil": r.lead_mil,
            }
            for r in trajectory
        ]


def main():
    parser = argparse.ArgumentParser(
        description="Run validation suite against JBM ballistics calculator"
    )
    parser.add_argument(
        "--suites",
        default=None,
        help=(
            "Comma-separated list of suites to run "
            "(baseline,atmosphere,wind,spin_drift,shooting_angle,velocity,bc,drag_model). "
            "Default: all"
        ),
    )
    parser.add_argument(
        "--output",
        default=ValidationRunner.DEFAULT_OUTPUT,
        help=f"Output JSON file (default: {ValidationRunner.DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run: generate test cases but don't submit to JBM",
    )
    parser.add_argument(
        "--rate-limit",
        type=float,
        default=ValidationRunner.REQUEST_DELAY,
        help="Request delay in seconds (default: 1.0)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output",
    )

    args = parser.parse_args()

    # Parse requested suites
    requested_suites = None
    if args.suites:
        requested_suites = [s.strip() for s in args.suites.split(",")]

    # Create and run validator
    runner = ValidationRunner(rate_limit=args.rate_limit, dry_run=args.dry_run)

    try:
        results, errors = runner.run_full_validation(
            requested_suites=requested_suites,
            verbose=not args.quiet,
        )

        # Export results
        runner.export_json(results, errors, args.output)

        # Print error summary
        total_errors = sum(len(errs) for errs in errors.values())
        if total_errors > 0:
            logger.warning(f"Validation completed with {total_errors} errors")
            return 1
        else:
            logger.info("Validation completed successfully")
            return 0

    except KeyboardInterrupt:
        logger.info("Validation interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Validation failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit(main())
