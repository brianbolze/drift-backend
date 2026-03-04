# Architecture Overview

## Module Hierarchy

```
jbm_scraper/
├── jbm_scraper.py              # Core scraper module
│   ├── JBMInput (dataclass)     # All 80+ ballistic parameters
│   ├── JBMResult (dataclass)    # Single trajectory point
│   └── JBMScraper (class)       # HTTP client + HTML parser
│
├── validation_matrix.py         # Test generation
│   ├── TestCartridge (dataclass) # Standard reference loads
│   ├── CARTRIDGES (dict)        # 4 standard cartridges
│   └── ValidationSuite (class)  # Test matrix generator
│
├── run_validation.py            # Runner script
│   └── ValidationRunner (class) # Executor + JSON export
│
├── examples.py                  # Usage examples
├── __init__.py                  # Package exports
├── requirements.txt             # Dependencies
├── README.md                    # Full documentation
├── QUICKSTART.md                # Quick reference
└── ARCHITECTURE.md              # This file
```

## Core Components

### 1. JBMScraper.py

The core module with three main classes:

#### JBMInput (Dataclass)
- **Purpose**: Represent all JBM ballistic parameters
- **Design**: Flat structure with explicit field names matching JBM's form field names
- **Key Features**:
  - 80+ fields covering bullets, atmosphere, wind, geometry, output options
  - Sensible defaults matching ICAO standard atmosphere
  - Checkbox fields as booleans (True = send "on", False = omit)
  - Unit codes embedded in field names (e.g., `tmp_u=19` for Fahrenheit)
  - `to_form_data()` method converts to HTTP POST form data
  - `_raw_html` field stores response for auditability

#### JBMResult (Dataclass)
- **Purpose**: Represent a single trajectory point
- **Fields**: Range, drop (inches + mils), windage (inches + mils), velocity, mach, energy, time-of-flight, optional lead
- **Design**: Immutable value object, serializable to JSON

#### JBMScraper (Class)
- **Purpose**: HTTP client for JBM drift calculator
- **Key Methods**:
  - `query(input: JBMInput) -> list[JBMResult]`: Main entry point
  - `_build_form_data(input: JBMInput) -> dict`: Converts JBMInput to form POST data
  - `_parse_results(html: str) -> list[JBMResult]`: Parses HTML table with regex
- **Features**:
  - Automatic Referer header (required by JBM)
  - Session management with requests library
  - Comprehensive error handling and logging
  - HTML response stored in input for auditability
  - Regex-based HTML table parsing (robust to formatting variations)

### 2. validation_matrix.py

Test generation module for decomposed validation:

#### TestCartridge (Dataclass)
- **Purpose**: Standard reference ballistic specifications
- **Fields**: Bullet weight, caliber, drag function, BC, muzzle velocity, barrel twist, bullet length
- **Usage**: Used to instantiate base JBMInput for each test suite

#### CARTRIDGES Dictionary
Four standard test cartridges:
- 6.5 Creedmoor: 140gr G7
- .308 Winchester: 175gr G7
- .338 Lapua Magnum: 300gr G7
- 5.56 NATO: 77gr G1

#### ValidationSuite (Class)
Generates decomposed test matrices:

**Core Methods**:
- `generate_baseline_cases()`: Core trajectory (gravity + drag only)
- `generate_atmosphere_sweep()`: Temperature, pressure, humidity, altitude
- `generate_wind_sweep()`: Wind speeds/angles with spin drift ON/OFF
- `generate_spin_drift_sweep()`: Twist rates/directions with toggle ON/OFF
- `generate_shooting_angle_sweep()`: LOS angles (-30 to +30°)
- `generate_velocity_sweep()`: Muzzle velocity sensitivity (2400-3000 fps)
- `generate_bc_sweep()`: BC scaling (±20% around nominal)
- `generate_drag_model_comparison()`: G1 vs G7 for same bullet
- `generate_full_matrix()`: All suites at once
- `get_suite_summary()`: Case count by suite

**Design Philosophy**:
- Each suite isolates ONE physics component
- Wind and spin drift use ON/OFF toggle technique for component isolation
- Standard ranges: 0-1000 yards in 100-yard increments
- Output in both inches and mils for absolute + angular measurements
- ~280 total test cases across all suites

### 3. run_validation.py

Execution script with rate limiting and result export:

#### ValidationRunner (Class)
- **Purpose**: Execute validation suite with rate limiting and result capture
- **Key Methods**:
  - `run_suite(suite_name, test_cases)`: Execute single suite
  - `run_full_validation(requested_suites)`: Run all or selected suites
  - `export_json(results, errors, output_file)`: Export to JSON
- **Features**:
  - 1 request/second rate limiting (configurable)
  - Progress reporting per case
  - Comprehensive error capture
  - Dry-run mode for testing without submitting
  - JSON export with metadata, results, and error summary

#### Main Script
- Command-line interface with argparse
- Suite filtering (--suites baseline,wind)
- Output file specification (--output results.json)
- Rate limit control (--rate-limit 0.5)
- Quiet mode (--quiet)
- Dry-run mode (--dry-run)
- Returns exit code (0 = success, 1 = errors)

## Data Flow

### Query Flow
```
User Code
    ↓
JBMInput (dataclass)
    ↓
JBMScraper.query()
    ↓
to_form_data() → POST to JBM
    ↓
HTTP Response (HTML)
    ↓
_parse_results() → regex extraction
    ↓
list[JBMResult]
    ↓
User receives trajectory data
```

### Validation Flow
```
ValidationSuite.generate_*_sweep()
    ↓
list[JBMInput] for one suite
    ↓
ValidationRunner.run_suite()
    ↓
loop: scraper.query() for each input
    ↓
capture success/error for each case
    ↓
Dict[case_name → result]
    ↓
export_json() → jbm_validation_results.json
    ↓
User can analyze with custom scripts
```

## Key Design Decisions

### 1. Form Field Naming
Field names match JBM's form field naming pattern exactly:
- `tmp_v` → form field `tmp.v`
- `tmp_u` → form field `tmp.u`

This 1:1 mapping prevents errors and makes form field lookup trivial.

### 2. Output Units: Always Both
Always request output in **both inches and mils**:
- `col1_un_u=8` (inches, absolute measurements)
- `col2_un_u=2` (mils/milliradians, angular measurements)

This allows validation against both absolute and angular error budgets.

### 3. Spin Drift Toggle for Component Isolation
The key insight for decomposed validation:

Run EACH test case TWICE:
- With `inc_drf_v=True` (spin drift ON)
- With `inc_drf_v=False` (spin drift OFF)

The DIFFERENCE in windage = pure spin drift component
This is applied to both wind and spin drift test suites.

### 4. Rate Limiting Philosophy
1 request/second is respectful to JBM (free service, one-person operation).

This means ~5 minutes for full suite (~280 cases), which is acceptable.
Configurable but not aggressive (no sub-0.5/sec encouragement).

### 5. HTML Parsing: Regex, Not BeautifulSoup
Used regex instead of BeautifulSoup to:
- Minimize dependencies (only `requests`)
- Handle malformed HTML robustly
- Make parsing logic transparent
- Avoid heavy XML parsing overhead

Row and cell patterns:
```python
row_pattern = r"<tr[^>]*>(.*?)</tr>"
cell_pattern = r"<td[^>]*>(.*?)</td>"
```

### 6. Auditability
Raw HTML responses stored in `JBMInput._raw_html` for:
- Debugging parsing failures
- Reproducibility
- Validation of results
- Offline analysis

### 7. Dataclass-Based Design
- Immutable (mostly) value objects
- JSON-serializable
- Type hints for IDE support
- Flat structure (no nested objects) for simplicity
- `asdict()` support built-in

## Validation Strategy

The validation suite uses **component-level isolation**:

| Component | Suite | Technique |
|-----------|-------|-----------|
| Gravity + Drag | baseline | No wind, no spin drift, standard conditions |
| Atmosphere | atmosphere_sweep | Vary temp/pres/hum/alt independently |
| Wind Drift | wind_sweep | Run with inc_drf ON/OFF, measure difference |
| Spin Drift | spin_drift_sweep | Vary twist rate, run with toggle ON/OFF |
| Gravity Projection | shooting_angle_sweep | Vary line-of-sight angle |
| Drag Sensitivity | velocity_sweep | Vary muzzle velocity |
| BC Scaling | bc_sweep | Vary BC ±20% around nominal |
| Drag Model | drag_model_comparison | Same bullet with G1 vs G7 |

Each suite has ~10-40 test cases, totaling ~280 cases.

Execution time: ~5 minutes at 1 request/second.

## Dependencies

**Only one runtime dependency**: `requests>=2.28.0`

- Python 3.7+ (dataclasses, type hints)
- Standard library: `json`, `re`, `time`, `logging`, `argparse`, `pathlib`, `datetime`
- No external parsers, no GUI, no async complexity

## Error Handling

### HTTP Errors
- `requests.RequestException`: Connection failures, timeouts
- Logged with full context
- Propagated to caller

### HTML Parsing Errors
- `ValueError`: Table not found or rows empty
- Regex extraction failures: Logged as warnings per-row
- Invalid data types: Skip malformed rows, continue processing

### Parameter Validation
- JBMInput accepts values as-is (JBM validates on server)
- Form data conversion handles type coercion
- No pre-flight validation (let JBM respond with errors)

## Testing Strategy

No unit tests included (this is a tool, not a library).

Instead:
- Examples test basic functionality
- Dry-run mode tests case generation without HTTP
- Full validation run tests complete flow
- Manual spot-checking against JBM web interface

## Performance

**Single Query**: <2 seconds (mostly network latency)
**Full Suite**: ~5 minutes at 1 request/second
**Memory**: Minimal (results kept in memory, could stream if needed)
**Disk**: JSON output ~50-100 MB for full suite

## Security Considerations

- No authentication (JBM is public)
- No sensitive data in requests (ballistics only)
- Respectful rate limiting
- No automated mass submissions
- Proper User-Agent header
- Required Referer header (JBM security check)

## Future Extensions

Potential improvements:

1. **Streaming Results**: Handle very large validation runs
2. **Database Backend**: Store results in SQLite instead of JSON
3. **Comparison Tools**: Automated diff against own solver
4. **Visualization**: Plot drop/drift curves
5. **Async Requests**: Faster execution (if rate limits permit)
6. **Caching**: Local cache of previous queries
7. **CLI Enhancements**: Interactive mode, progress bars
8. **Export Formats**: CSV, Excel, HDF5 for analysis tools

None of these are necessary for current use case.

## Code Quality

- **Type Hints**: Complete for all public APIs
- **Docstrings**: Module, class, and method level
- **Logging**: Structured logging with context
- **Error Messages**: Descriptive with actionable guidance
- **Code Style**: PEP 8 compliant
- **Naming**: Clear, unambiguous names matching domain terminology

## Summary

This is a **production-quality tool** for ballistic validation:
- Clean architecture with clear separation of concerns
- Minimal dependencies
- Comprehensive documentation
- Respectful rate limiting
- Robust error handling
- Designed for both interactive use and batch processing
- Suitable for comparing custom ballistics solvers against JBM
