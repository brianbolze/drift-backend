# JBM Ballistics Scraper & Validation Suite

A comprehensive Python tool for submitting ballistic calculations to the JBM drift calculator, parsing results, and generating decomposed validation test matrices.

## Overview

This tool:

1. **Submits POST requests** to JBM drift calculator with full control over ballistic parameters
2. **Parses HTML output** into structured trajectory data
3. **Supports all important parameters**: bullet specs, velocity, atmospheric conditions, wind, spin drift, shooting angles, etc.
4. **Generates test vectors** for decomposed validation of physics components in isolation

## Architecture

### Core Modules

#### `jbm_scraper.py`
Main scraper module with three core classes:

- **`JBMInput`**: Dataclass representing all 80+ ballistic parameters with sensible defaults
- **`JBMResult`**: Single trajectory point with range, drop, windage, velocity, etc.
- **`JBMScraper`**: HTTP client that submits queries and parses results

```python
from jbm_scraper import JBMScraper, JBMInput

scraper = JBMScraper()

# Create input with custom parameters
params = JBMInput(
    bc_v=0.5,
    d_f_v=0,  # G1 drag function
    m_vel_v=3000,
    rng_max_v=1000,
)

# Submit and get trajectory
results = scraper.query(params)

# Results contain drop, windage, velocity, time-of-flight, etc.
for r in results:
    print(f"{r.range_yd}yd: drop={r.drop_in}in, wind={r.windage_in}in")
```

#### `validation_matrix.py`
Generates decomposed test suites for validating individual physics components:

```python
from validation_matrix import ValidationSuite

suite = ValidationSuite()

# Each method generates test cases for a specific physics component
baseline_cases = suite.generate_baseline_cases()      # Gravity + drag
atmosphere_cases = suite.generate_atmosphere_sweep()  # Temperature, pressure, humidity, altitude
wind_cases = suite.generate_wind_sweep()              # Wind drift (with ON/OFF spin drift)
spin_drift_cases = suite.generate_spin_drift_sweep()  # Coriolis effect
angle_cases = suite.generate_shooting_angle_sweep()   # Gravity vector projection
velocity_cases = suite.generate_velocity_sweep()      # Drag sensitivity
bc_cases = suite.generate_bc_sweep()                  # BC scaling
drag_model_cases = suite.generate_drag_model_comparison()  # G1 vs G7

# Get all at once
all_suites = suite.generate_full_matrix()  # Dict with ~280 total test cases
summary = suite.get_suite_summary()        # Count by category
```

#### `run_validation.py`
Runner script that:
- Generates full validation suite
- Submits to JBM with **1 request/sec rate limiting** (respectful)
- Captures results and raw HTML
- Exports to JSON for analysis

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Basic Query

```python
from jbm_scraper import JBMScraper, JBMInput

scraper = JBMScraper()

# Standard .308 Win load
params = JBMInput(
    bc_v=0.264,           # G7 BC
    d_f_v=4,              # G7 drag function
    bt_wgt_v=175,         # 175 grain
    cal_v=0.308,          # .308 caliber
    m_vel_v=2600,         # 2600 ft/s
    b_twt_v=10,           # 10" twist
    blt_len_v=1.24,       # 1.24" bullet
)

results = scraper.query(params)

# Print trajectory table
print("Range(yd)  Drop(in)  Drop(mil)  Wind(in)  Wind(mil)  Vel(fps)  Time(s)")
for r in results:
    print(f"{r.range_yd:8.0f}  {r.drop_in:7.2f}   {r.drop_mil:7.2f}   "
          f"{r.windage_in:7.2f}   {r.windage_mil:7.2f}    {r.velocity_fps:7.1f}   {r.tof_s:6.3f}")
```

### Atmospheric Variations

```python
from jbm_scraper import JBMScraper, JBMInput

scraper = JBMScraper()
base = JBMInput()

# Test in cold conditions
cold = JBMInput(tmp_v=0, tmp_u=19)  # 0°F
results_cold = scraper.query(cold)

# Test at altitude
altitude = JBMInput(alt_v=5000, alt_u=10, std_alt_v=True)  # 5000 ft, standard atmosphere
results_alt = scraper.query(altitude)

# Test in humid conditions
humid = JBMInput(hum_v=100)  # 100% humidity
results_humid = scraper.query(humid)
```

### Wind & Spin Drift Isolation

The key validation trick: run each wind condition TWICE, with `inc_drf_v` ON and OFF:

```python
from jbm_scraper import JBMScraper, JBMInput

scraper = JBMScraper()

# Case 1: 10 mph wind, spin drift ON
with_spin = JBMInput(
    spd_wnd_v=10,
    ang_wnd_v=90,       # Crosswind
    inc_drf_v=True      # Spin drift ON
)

# Case 2: Same wind, spin drift OFF
without_spin = JBMInput(
    spd_wnd_v=10,
    ang_wnd_v=90,       # Crosswind
    inc_drf_v=False     # Spin drift OFF
)

results_with = scraper.query(with_spin)
results_without = scraper.query(without_spin)

# The DIFFERENCE in windage column is pure wind drift
# Add a bit of time.sleep between requests for rate limiting
```

### Spin Drift Isolation

Similar pattern: vary twist rate with `inc_drf` ON vs OFF:

```python
from jbm_scraper import JBMScraper, JBMInput

scraper = JBMScraper()

# Twist rate sensitivity with spin drift ON
for twist in [8, 9, 10, 11, 12]:
    case = JBMInput(
        b_twt_v=float(twist),
        inc_drf_v=True,     # Spin drift ON
        spd_wnd_v=0         # No wind
    )
    results = scraper.query(case)
    # Analyze windage trend vs twist rate
```

### Run Full Validation Suite

```bash
# Run all suites, export to JSON
python run_validation.py --output results.json

# Run specific suites only
python run_validation.py --suites baseline,wind,spin_drift

# Dry run (generate test cases, don't submit)
python run_validation.py --dry-run

# Custom rate limit (default 1 req/sec)
python run_validation.py --rate-limit 0.5

# Suppress progress output
python run_validation.py --quiet
```

This takes ~5 minutes for the full suite (280+ test cases) at 1 request/second.

### Parse Results from JSON

```python
import json

with open("jbm_validation_results.json") as f:
    data = json.load(f)

# Access results by suite
baseline_results = data["results"]["baseline"]

for test_name, test_result in baseline_results.items():
    if test_result["status"] == "success":
        trajectory = test_result["trajectory"]
        # Analyze...
```

## Parameters Reference

### Bullet Specification

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `b_id_v` | int | -1 | Bullet library ID (-1 = manual entry) |
| `bc_v` | float | 0.5 | Ballistic coefficient |
| `d_f_v` | int | 0 | Drag function (0=G1, 4=G7, etc) |
| `bt_wgt_v` | float | 220 | Bullet weight (grains) |
| `cal_v` | float | 0.308 | Caliber (inches) |
| `blt_len_v` | float | 1.5 | Bullet length (inches) |
| `b_twt_v` | float | 12 | Barrel twist rate (inches) |
| `b_twt_dir_v` | int | 1 | Twist direction (0=Left, 1=Right) |

### Velocity & Range

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `m_vel_v` | float | 3000 | Muzzle velocity (ft/s) |
| `rng_min_v` | int | 0 | Minimum range (yards) |
| `rng_max_v` | int | 1000 | Maximum range (yards) |
| `rng_inc_v` | int | 100 | Range increment (yards) |
| `rng_zer_v` | int | 100 | Zero range (yards) |

### Atmosphere

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `tmp_v` | float | 59 | Temperature (°F by default) |
| `prs_v` | float | 29.92 | Pressure (inHg by default) |
| `hum_v` | float | 0 | Humidity (%) |
| `alt_v` | float | 0 | Altitude (ft by default) |
| `std_alt_v` | bool | False | Use standard atmosphere at altitude |

### Wind

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `spd_wnd_v` | float | 10 | Wind speed (mph by default) |
| `ang_wnd_v` | float | 90 | Wind angle (degrees, 90=full crosswind) |
| `inc_drf_v` | bool | True | Include spin drift (CRITICAL TOGGLE) |

### Shooting Geometry

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `hgt_sgt_v` | float | 1.5 | Sight height (inches) |
| `los_v` | float | 0 | Line of sight angle (degrees) |
| `cnt_v` | float | 0 | Cant angle (degrees) |
| `azm_v` / `ele_v` | float | 0 | Windage/elevation adjustments (MOA) |

## Test Cartridges

The validation suite uses these standard test loads:

### 6.5 Creedmoor
- Bullet: 140 gr, 0.264" cal
- BC: 0.326 (G7)
- MV: 2710 ft/s
- Twist: 8 inches
- Length: 1.35 inches

### .308 Winchester
- Bullet: 175 gr, 0.308" cal
- BC: 0.264 (G7)
- MV: 2600 ft/s
- Twist: 10 inches
- Length: 1.24 inches

### .338 Lapua Magnum
- Bullet: 300 gr, 0.338" cal
- BC: 0.419 (G7)
- MV: 2700 ft/s
- Twist: 10 inches
- Length: 1.7 inches

### 5.56 NATO
- Bullet: 77 gr, 0.224" cal
- BC: 0.372 (G1)
- MV: 2750 ft/s
- Twist: 8 inches
- Length: 1.0 inches

## Validation Approach

The validation suite uses **decomposed testing** to isolate each physics component:

### 1. Baseline Cases
Core trajectory engine (gravity + drag only):
- Each cartridge with configured drag function
- No wind, no spin drift, standard atmosphere
- Tests: drag table implementation, velocity scaling

### 2. Atmosphere Sweep
Temperature, pressure, humidity, altitude independently:
- Temperature: -30°F to +110°F
- Pressure: 25.0 to 32.0 inHg
- Humidity: 0% to 100%
- Altitude: 0 to 10,000 ft (with standard atmosphere flag)

### 3. Wind Sweep
Wind drift with ON/OFF spin drift toggle:
- Speeds: 0, 5, 10, 15, 20 mph
- Angles: 0°, 45°, 90°, 135°, 180°, 270°
- Each condition tested TWICE: `inc_drf_v=True` and `inc_drf_v=False`
- Difference = pure wind drift component

### 4. Spin Drift Sweep
Coriolis effect with twist rate variation:
- Twist rates: 7, 8, 9, 10, 11, 12, 14 inches
- Directions: Left (0), Right (1)
- Each condition tested TWICE: `inc_drf_v=True` and `inc_drf_v=False`
- Difference = pure spin drift component

### 5. Shooting Angle Sweep
Gravity vector projection along line of sight:
- Angles: -30°, -15°, 0°, +15°, +30°
- Tests: cosine correction for uphill/downhill

### 6. Velocity Sweep
Drag sensitivity across speed range:
- Velocities: 2400, 2550, 2710, 2850, 3000 fps
- Tests: transonic behavior, drag scaling

### 7. BC Sweep
Ballistic coefficient sensitivity:
- BC range: ±20% around nominal in 5% steps
- Tests: drag coefficient scaling linearity

### 8. Drag Model Comparison
Same bullet with different drag functions:
- G7 BC vs G1 BC (converted)
- Results should be CLOSE but not identical
- Tests: drag table implementation differences

## Output Format

Each trajectory point includes:

```python
@dataclass
class JBMResult:
    range_yd: float         # Range in yards
    drop_in: float          # Vertical drop in inches (absolute)
    drop_mil: float         # Vertical drop in mils (angular)
    windage_in: float       # Horizontal drift in inches (absolute)
    windage_mil: float      # Horizontal drift in mils (angular)
    velocity_fps: float     # Remaining velocity in ft/s
    mach: float             # Mach number
    energy_ftlbs: float     # Kinetic energy in ft-lbs
    tof_s: float            # Time of flight in seconds
    lead_in: Optional[float]    # Target lead in inches (if applicable)
    lead_mil: Optional[float]   # Target lead in mils (if applicable)
```

JSON export includes full input parameters and trajectory for each test case.

## Rate Limiting

The runner respects JBM's free service with **1 request per second** delay.
This is configurable via the `--rate-limit` parameter.

Typical execution times:
- Single case: <2 seconds
- Baseline suite (8 cases): ~10 seconds
- Full suite (280 cases): ~5 minutes

## Error Handling

The scraper handles:
- HTTP connection failures (auto-retries with exponential backoff)
- Malformed HTML responses (detailed error logging)
- Invalid parameter values (validation before submission)
- Rate limiting (automatic delays)

Errors are captured in the JSON export with full context.

## Example: Custom Analysis

```python
import json
from pathlib import Path
from jbm_scraper import JBMScraper, JBMInput

# Load previous validation results
with open("jbm_validation_results.json") as f:
    results = json.load(f)

# Extract atmosphere sweep results
atm_results = results["results"]["atmosphere"]

# Analyze temperature sensitivity
temps = {}
for test_name, test_result in atm_results.items():
    if "speed0_angle0" in test_name and test_result["status"] == "success":
        # Extract temperature from input
        temp = test_result["input"]["temperature_f"]
        trajectory = test_result["trajectory"]
        
        # Get drop at 500 yards
        for point in trajectory:
            if point["range_yd"] == 500:
                if temp not in temps:
                    temps[temp] = []
                temps[temp].append(point["drop_in"])
                break

# Print temperature sensitivity
print("Temperature Sensitivity at 500 yards")
for temp in sorted(temps.keys()):
    drop = temps[temp][0]
    print(f"  {temp:6.1f}°F: {drop:7.2f} inches")
```

## Notes

1. **Referer Header Required**: JBM requires a specific Referer header. This is handled automatically.

2. **Output Units**: Always request output in both **inches** and **mils** (set `col1_un_u=8` and `col2_un_u=2`). This gives both absolute and angular measurements.

3. **Spin Drift Toggle Critical**: The `inc_drf_v` parameter is the key to decomposed validation. Run cases with both ON and OFF to isolate wind from spin drift.

4. **Respectful Rate Limiting**: 1 request/second is polite. JBM is a one-person operation.

5. **Auditability**: Raw HTML responses are captured in the output for reproducibility and debugging.

## License & Attribution

This tool interfaces with JBM Ballistics, run by Jim Brockwell.
Respect the free service; don't hammer the server.

For inquiries or contributions, see the original repository.
