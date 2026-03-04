# How the Ballistics iOS Package Works

This document explains what the Ballistics package does and how it does it, assuming no prior knowledge of ballistics.

## What It Does

When a shooter fires a rifle at a distant target, the bullet doesn't travel in a straight line. Gravity pulls it down, air slows it down, and wind pushes it sideways. The farther the target, the more these effects matter.

The Ballistics package takes information about the bullet, the rifle, the weather, and the target distance, and calculates exactly how much the bullet will deviate from where the scope is pointed. It outputs **hold values** — the adjustments a shooter dials into their scope to compensate for all these effects.

A full trajectory calculation from 0 to 2,000 yards runs in under 10 milliseconds.

## The Inputs

The solver takes a single `SolverInput` containing six pieces:

| Input | What it describes |
|---|---|
| **Projectile** | The bullet: weight, diameter, length, ballistic coefficient (how aerodynamic it is), and drag model (G1 or G7) |
| **Firearm** | The rifle: muzzle velocity (how fast the bullet leaves the barrel), sight height (how far the scope is above the barrel), twist rate (how fast the barrel spins the bullet), zero range (the distance where scope and bullet path are aligned), and the weather conditions when the rifle was zeroed |
| **Atmosphere** | Current weather: temperature, station pressure, humidity, altitude — these determine air density, which controls how much drag slows the bullet |
| **Wind** | Wind speed and direction relative to the shooter |
| **Target** | Distance, shooting angle (uphill/downhill), and optionally latitude and compass bearing (for Earth-rotation corrections) |
| **Options** | Which corrections to enable and how fine-grained the output should be |

## Input Sensitivity — What Matters Most

Not all inputs matter equally. A sensitivity analysis (single-variable perturbations of a 6.5 CM baseline against JBM Ballistics) ranks how much each input shifts hold values when varied across its realistic range. Maximum absolute deltas at 1,000 yards:

| Input | Elev Δ (mil) | Wind Δ (mil) | Verdict |
|---|---|---|---|
| Shooting angle | 2.9 | ~0 | Dominant — cosine correction is non-negotiable |
| Wind speed | 0 | 1.9 | Dominates windage; the hardest variable to read |
| Muzzle velocity | 1.3 | 0.2 | True your MV; 50 fps ≈ 0.4 mil at 1 kyd |
| Altitude / pressure | 0.7–1.0 | 0.4–0.6 | Both measure air density; use a Kestrel |
| Ballistic coefficient | 0.6 | 0.3 | Grows fast at ELR; prefer measured G7 values |
| Temperature | 0.5 | 0.3 | Moderate; matters more beyond 1 kyd |
| Zero distance | 1.2 | 0 | Constant offset — shifts the whole table |
| Sight height | 0.2 | 0 | Nearly irrelevant at distance |
| Humidity | 0 | 0 | Negligible — safe to ignore |
| Bullet length | 0 | 0.1 | Only affects spin drift slightly |
| Barrel twist rate | 0 | 0 | Non-factor for holds (matters for stability) |

Full data and methodology: [`docs/sensitivity_analysis.md`](sensitivity_analysis.md)

## What Happens When You Call `solve()`

The solver runs through these steps in order:

### Step 1: Compute Air Density

Using the ICAO atmosphere model, the solver calculates the air density for both the current conditions and the conditions when the rifle was zeroed. Denser air means more drag. The calculation uses temperature, pressure, and humidity (via the Arden Buck equation for water vapor).

### Step 2: Look Up the Drag Table

The solver loads a table of drag coefficients — numbers that describe how much air resistance the bullet experiences at different speeds. There are two standard tables:

- **G1** — based on a flat-base bullet shape. Older standard, but most manufacturers publish G1 values.
- **G7** — based on a modern boat-tail bullet shape. More accurate for long-range bullets.

The table maps Mach number (bullet speed relative to the speed of sound) to a drag coefficient. Between table entries, the solver uses cubic Hermite interpolation for smooth transitions — this is especially important in the transonic region (around Mach 1) where drag changes rapidly.

Drag tables are cached after first load so repeated calculations are fast.

### Step 3: Compute Stability Factor

The solver calculates the bullet's gyroscopic stability factor (Sg) using the Miller formula. This measures whether the barrel's twist rate spins the bullet fast enough for stable flight. An Sg above 1.4 means stable flight; below 1.0, the bullet may tumble. The stability factor is also used later for spin drift calculations.

### Step 4: Find the Zero Angle

This is the key geometric step. The scope sits above the barrel, so the barrel must point slightly upward for the bullet's arcing path to cross the scope's line of sight at the zero range (typically 100 yards).

The solver finds this bore angle using **bisection**: it guesses an angle, simulates the bullet's flight to the zero range, checks if the bullet is above or below the sight line, and adjusts. This converges in about 17 iterations to a precision of 0.02 MOA (about 0.02 inches at 100 yards).

The zero angle is computed using the atmospheric conditions from when the rifle was zeroed — not the current conditions. This is important because air density affects drag.

### Step 5: Simulate the Trajectory

With the bore angle known, the solver simulates the bullet's full flight path using a **4th-order Runge-Kutta (RK4) numerical integrator** with a fixed 0.5-millisecond time step. At each step, it computes:

1. The bullet's current speed
2. The Mach number (speed / speed of sound)
3. The drag coefficient at that Mach number (from the drag table)
4. The deceleration from drag (proportional to speed², drag coefficient, and air density)
5. The deceleration from gravity (constant 32.17 ft/s² downward)
6. New velocity and position

The integrator records the bullet's position, velocity, and time of flight at every yard.

### Step 6: Apply Corrections

For each trajectory point, the solver applies several corrections on top of the basic gravity-and-drag trajectory:

**Shooting angle** — When shooting uphill or downhill, gravity's effect on the bullet is reduced. The solver multiplies the drop by `cos(angle)` (the "rifleman's rule"). This is the single largest sensitivity factor for elevation — a 45° angle shifts the hold by 2.9 mil at 1,000 yards.

**Wind drift** — Uses the McKinley lag-time method: the bullet starts fast and slows down due to drag. The difference between the bullet's actual time of flight and how long it would take at constant muzzle velocity is the "lag time." During this lag, the crosswind pushes the bullet sideways. Formula: `drift = crosswind_speed × lag_time`. Wind speed dominates windage holds — the relationship is nearly linear (~0.95 mil per 5 mph at 1,000 yards).

**Spin drift** — A spinning bullet precesses (wobbles like a gyroscope), which causes it to drift sideways in the direction of the barrel's twist. Right-twist barrels drift the bullet right. The solver uses the Litz formula: `drift = 1.25 × (Sg + 1.2) × time^1.83`. At 1,000 yards this is typically 6–8 inches.

**Coriolis effect** — The Earth is rotating, and over long flight times this creates both horizontal and vertical deflections. The magnitude depends on the shooter's latitude and firing direction. At 1,000 yards this is typically 1–5 inches.

**Aerodynamic jump** — When a spinning bullet encounters a crosswind at the muzzle, the gyroscopic response creates a small one-time angular kick in the vertical plane. For a right-twist barrel, a left-to-right crosswind kicks the bullet slightly upward. This is typically 0.1–0.25 MOA per 10 mph of crosswind.

### Step 7: Convert to Hold Values

The solver combines all corrections into total vertical and horizontal offsets in inches, then converts these to **angular hold values** in both MOA (minutes of angle) and mils (milliradians) — the two unit systems shooters use for scope adjustments. The hold is the negative of the deflection: if the bullet drops, you hold high.

## The Output

The solver returns a `TrajectoryResult` containing:

- **A table of trajectory points** — one per yard (or at whatever interval you requested), each with:
  - Distance, time of flight, velocity, energy, Mach number
  - Total hold values (elevation and windage) in both MOA and mils
  - Individual component breakdowns (drop, wind drift, spin drift, Coriolis, aerodynamic jump) in inches
- **Metadata** — zero angle, density altitude, air densities, spin rate, stability factor

The result also provides convenience methods for looking up holds at specific distances, generating scope click counts, producing DOPE cards (pre-computed hold tables), and finding the transonic range (where accuracy predictions start to degrade).

## Package Structure

```
Ballistics/
├── Sources/Ballistics/
│   ├── Models/          # Input and output types
│   │   ├── SolverInput        — top-level input container
│   │   ├── Projectile         — bullet properties
│   │   ├── Firearm            — rifle and scope configuration
│   │   ├── Atmosphere         — weather conditions and air density
│   │   ├── Wind               — wind speed and direction
│   │   ├── Target             — distance, angle, location
│   │   ├── SolverOptions      — correction toggles
│   │   ├── TrajectoryResult   — full output with convenience methods
│   │   ├── TrajectoryPoint    — one row of the trajectory table
│   │   └── AngularMeasurement — dual MOA/mil representation
│   ├── Solver/
│   │   ├── BallisticSolver    — protocol (one method: solve)
│   │   └── PointMassSolver    — production implementation
│   ├── Internal/              # Physics implementations
│   │   ├── RK4Integrator      — numerical integration engine
│   │   ├── ZeroAngleFinder    — bisection search for bore angle
│   │   ├── DragTable           — drag coefficient lookup with cubic interpolation
│   │   ├── SpinDrift           — gyroscopic drift (Litz formula)
│   │   ├── Coriolis            — Earth-rotation corrections
│   │   └── AerodynamicJump    — crosswind-induced vertical offset
│   ├── Enums/
│   │   ├── DragModel          — G1 or G7
│   │   ├── AngularUnit        — MOA or mil
│   │   └── TwistDirection     — right or left barrel twist
│   └── Data/
│       ├── g1_drag_table.json — G1 standard drag coefficients
│       └── g7_drag_table.json — G7 standard drag coefficients
└── Tests/
    └── BallisticsTests/
        ├── JBMValidationTests  — 8 test cases validated against JBM Ballistics
        ├── AtmosphereTests     — air density and speed of sound
        ├── AngularMeasurementTests — unit conversions
        ├── WindTests           — wind decomposition
        └── PerformanceTests    — solver timing
```

## Quick Usage Example

```swift
import Ballistics

let solver = PointMassSolver()

let result = solver.solve(SolverInput(
    projectile: Projectile(
        weight: 140,
        diameter: 0.264,
        ballisticCoefficient: 0.326,
        dragModel: .g7
    ),
    firearm: Firearm(
        muzzleVelocity: 2710,
        sightHeight: 1.75,
        twistRate: 8.0,
        zeroRange: 100,
        zeroAtmosphere: .standard
    ),
    atmosphere: .standard,
    wind: Wind(speed: 10, directionDeg: 90),
    target: Target(distanceYards: 1000)
))

// What scope adjustment do I need at 500 yards?
if let point = result.pointAt(yards: 500) {
    print("Hold \(point.holdElevation.mils) mils up")
    print("Hold \(point.holdWindage.mils) mils for wind")
}
```

## Validation

The solver is validated against JBM Ballistics (a widely trusted online ballistic calculator) across 8 test cases covering different calibers, velocities, and drag models. All cases match within ±0.1 mil at 1,000 yards. The test suite has 31 total tests covering atmosphere calculations, angular conversions, wind decomposition, and the full solver.
