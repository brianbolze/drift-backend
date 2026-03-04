# Quick Start Guide

## Installation

```bash
pip install -r requirements.txt
```

## 30-Second Example

```python
from jbm_scraper import JBMScraper, JBMInput

scraper = JBMScraper()
results = scraper.query(JBMInput(bc_v=0.5, m_vel_v=3000))

for r in results:
    print(f"{r.range_yd}yd: {r.drop_in}in drop, {r.windage_in}in drift")
```

## Run Validation Suite

```bash
# Full suite (~5 minutes, 280 test cases)
python run_validation.py --output results.json

# Specific suites only
python run_validation.py --suites baseline,wind

# Dry run (generate test cases, don't submit)
python run_validation.py --dry-run
```

## Common Patterns

### Standard Load: .308 Win 175gr
```python
from jbm_scraper import JBMScraper, JBMInput

scraper = JBMScraper()
params = JBMInput(
    bc_v=0.264,           # G7 BC
    d_f_v=4,              # G7 drag function
    bt_wgt_v=175,
    cal_v=0.308,
    m_vel_v=2600,
)
results = scraper.query(params)
```

### Test Different Conditions
```python
# Cold weather
cold = JBMInput(tmp_v=0)

# Altitude
altitude = JBMInput(alt_v=5000, std_alt_v=True)

# Windy
windy = JBMInput(spd_wnd_v=15, ang_wnd_v=90)
```

### Isolate Wind Drift (Key Technique)
```python
# With spin drift ON
with_spin = JBMInput(spd_wnd_v=10, ang_wnd_v=90, inc_drf_v=True)
# With spin drift OFF
without_spin = JBMInput(spd_wnd_v=10, ang_wnd_v=90, inc_drf_v=False)

r_with = scraper.query(with_spin)
r_without = scraper.query(without_spin)

# Difference in windage = pure wind drift
wind_drift_only = r_with[5].windage_in - r_without[5].windage_in
```

## Available Cartridges

The validation suite includes:
- **6.5 Creedmoor**: 140gr, G7 BC=0.326, 2710 ft/s
- **.308 Win**: 175gr, G7 BC=0.264, 2600 ft/s
- **.338 Lapua**: 300gr, G7 BC=0.419, 2700 ft/s
- **5.56 NATO**: 77gr, G1 BC=0.372, 2750 ft/s

## Key Parameters

| What | Parameter | Example |
|------|-----------|---------|
| BC | `bc_v` | `0.5` |
| Drag function | `d_f_v` | `0` (G1), `4` (G7) |
| Muzzle velocity | `m_vel_v` | `2700` |
| Wind speed | `spd_wnd_v` | `10.0` |
| Wind angle | `ang_wnd_v` | `90` (crosswind) |
| Temperature | `tmp_v` | `59` (°F) |
| **Include spin drift** | `inc_drf_v` | `True` |
| Barrel twist | `b_twt_v` | `10.0` |
| Bullet length | `blt_len_v` | `1.24` |

## Understanding Output

Each point has:
- `range_yd`: Distance in yards
- `drop_in`: Vertical drop in inches
- `drop_mil`: Vertical drop in mils (milliradians)
- `windage_in`: Horizontal drift in inches
- `windage_mil`: Horizontal drift in mils
- `velocity_fps`: Remaining velocity
- `mach`: Mach number
- `energy_ftlbs`: Kinetic energy
- `tof_s`: Time of flight in seconds

## Validation Philosophy

The validation suite isolates physics components:

1. **Baseline**: Gravity + drag only
2. **Atmosphere**: Temperature, pressure, humidity effects
3. **Wind**: Wind drift (test with spin drift ON/OFF to isolate)
4. **Spin Drift**: Coriolis effect (test with toggle ON/OFF)
5. **Shooting Angle**: Gravity along line-of-sight
6. **Velocity**: Drag sensitivity
7. **BC**: Ballistic coefficient scaling
8. **Drag Model**: G1 vs G7 comparison

## Rate Limiting

Default is 1 request per second (respectful to JBM's free service).

Full suite: ~280 cases × 1 sec = ~5 minutes

Change with: `--rate-limit 0.5` (requests per second)

## Troubleshooting

**"No results table found"**
- HTML parsing failed
- Check that JBM accepted the parameters
- May be invalid parameter combination

**Request timeout**
- JBM server slow or unresponsive
- Try again in a few moments
- Increase timeout: `JBMScraper(timeout=60)`

**Rate limit exceeded**
- Too many requests
- Default 1/sec is respectful
- Don't decrease below 0.5/sec

## Next Steps

See `examples.py` for detailed usage patterns and `README.md` for complete documentation.

Run the validation suite to generate test vectors for comparing against your own ballistics solver.
