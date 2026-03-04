# Ballistic Sensitivity Analysis

How sensitive are elevation and windage holds to changes in each input variable? This report answers that question with real data from the JBM Ballistics drift calculator, using systematic single-variable perturbations from a 6.5 Creedmoor baseline.

## Baseline Configuration

| Parameter | Value |
|-----------|-------|
| Cartridge | 6.5 Creedmoor 140gr Hornady ELD Match |
| BC (G7) | 0.326 |
| Muzzle Velocity | 2710 fps (24" test barrel) |
| Bullet Diameter | 0.264" |
| Bullet Length | 1.376" |
| Barrel Twist | 1:8" RH |
| Sight Height | 1.5" over bore |
| Zero | 100 yards |
| Wind | 10 mph, full crosswind (90°) |
| Atmosphere | 59°F, 29.92 inHg (corrected), 0% humidity, sea level |

## Baseline Trajectory

| Distance | Elev (mil) | Elev (in) | Wind (mil) | Wind (in) | Vel (fps) | Energy (ft·lbs) | TOF (s) |
|----------|-----------|----------|-----------|---------|----------|----------------|--------|
| 300 yd | -1.20 | -13.4 | 0.50 | 5.5 | 2306 | 1652 | 0.360 |
| 600 yd | -3.90 | -84.7 | 1.10 | 24.0 | 1934 | 1163 | 0.786 |
| 1000 yd | -8.80 | -318.1 | 2.10 | 75.8 | 1489 | 689 | 1.493 |
| 1500 yd | -18.50 | -996.5 | 3.80 | 207.7 | 1052 | 344 | 2.711 |

---

## Detailed Variable Sweeps

### Muzzle Velocity

**At 300 yards:**

| Muzzle Velocity | Elev (mil) | Δ Elev (mil) | Wind (mil) | Δ Wind (mil) |
|---|---|---|---|---|
| 2560fps | -1.40 | -0.200 | 0.60 | +0.100 |
| 2610fps | -1.40 | -0.200 | 0.50 | +0.000 |
| 2660fps | -1.30 | -0.100 | 0.50 | +0.000 |
| 2710fps ←baseline | -1.20 | +0.000 | 0.50 | +0.000 |
| 2760fps | -1.20 | +0.000 | 0.50 | +0.000 |
| 2810fps | -1.10 | +0.100 | 0.50 | +0.000 |
| 2860fps | -1.10 | +0.100 | 0.50 | +0.000 |

**At 600 yards:**

| Muzzle Velocity | Elev (mil) | Δ Elev (mil) | Wind (mil) | Δ Wind (mil) |
|---|---|---|---|---|
| 2560fps | -4.50 | -0.600 | 1.20 | +0.100 |
| 2610fps | -4.30 | -0.400 | 1.20 | +0.100 |
| 2660fps | -4.10 | -0.200 | 1.10 | +0.000 |
| 2710fps ←baseline | -3.90 | +0.000 | 1.10 | +0.000 |
| 2760fps | -3.80 | +0.100 | 1.10 | +0.000 |
| 2810fps | -3.60 | +0.300 | 1.00 | -0.100 |
| 2860fps | -3.50 | +0.400 | 1.00 | -0.100 |

**At 1000 yards:**

| Muzzle Velocity | Elev (mil) | Δ Elev (mil) | Wind (mil) | Δ Wind (mil) |
|---|---|---|---|---|
| 2560fps | -10.10 | -1.300 | 2.30 | +0.200 |
| 2610fps | -9.60 | -0.800 | 2.20 | +0.100 |
| 2660fps | -9.20 | -0.400 | 2.20 | +0.100 |
| 2710fps ←baseline | -8.80 | +0.000 | 2.10 | +0.000 |
| 2760fps | -8.50 | +0.300 | 2.00 | -0.100 |
| 2810fps | -8.10 | +0.700 | 2.00 | -0.100 |
| 2860fps | -7.80 | +1.000 | 1.90 | -0.200 |

**At 1500 yards:**

| Muzzle Velocity | Elev (mil) | Δ Elev (mil) | Wind (mil) | Δ Wind (mil) |
|---|---|---|---|---|
| 2560fps | -21.20 | -2.700 | 4.20 | +0.400 |
| 2610fps | -20.20 | -1.700 | 4.10 | +0.300 |
| 2660fps | -19.30 | -0.800 | 4.00 | +0.200 |
| 2710fps ←baseline | -18.50 | +0.000 | 3.80 | +0.000 |
| 2760fps | -17.60 | +0.900 | 3.70 | -0.100 |
| 2810fps | -16.90 | +1.600 | 3.60 | -0.200 |
| 2860fps | -16.10 | +2.400 | 3.50 | -0.300 |

---

### Ballistic Coefficient (G7)

**At 300 yards:**

| Ballistic Coefficient (G7) | Elev (mil) | Δ Elev (mil) | Wind (mil) | Δ Wind (mil) |
|---|---|---|---|---|
| 0.293 | -1.30 | -0.100 | 0.60 | +0.100 |
| 0.31 | -1.20 | +0.000 | 0.50 | +0.000 |
| 0.326 ←baseline | -1.20 | +0.000 | 0.50 | +0.000 |
| 0.342 | -1.20 | +0.000 | 0.50 | +0.000 |
| 0.359 | -1.20 | +0.000 | 0.50 | +0.000 |

**At 600 yards:**

| Ballistic Coefficient (G7) | Elev (mil) | Δ Elev (mil) | Wind (mil) | Δ Wind (mil) |
|---|---|---|---|---|
| 0.293 | -4.10 | -0.200 | 1.20 | +0.100 |
| 0.31 | -4.00 | -0.100 | 1.20 | +0.100 |
| 0.326 ←baseline | -3.90 | +0.000 | 1.10 | +0.000 |
| 0.342 | -3.90 | +0.000 | 1.10 | +0.000 |
| 0.359 | -3.80 | +0.100 | 1.00 | -0.100 |

**At 1000 yards:**

| Ballistic Coefficient (G7) | Elev (mil) | Δ Elev (mil) | Wind (mil) | Δ Wind (mil) |
|---|---|---|---|---|
| 0.293 | -9.40 | -0.600 | 2.40 | +0.300 |
| 0.31 | -9.10 | -0.300 | 2.20 | +0.100 |
| 0.326 ←baseline | -8.80 | +0.000 | 2.10 | +0.000 |
| 0.342 | -8.60 | +0.200 | 2.00 | -0.100 |
| 0.359 | -8.40 | +0.400 | 1.90 | -0.200 |

**At 1500 yards:**

| Ballistic Coefficient (G7) | Elev (mil) | Δ Elev (mil) | Wind (mil) | Δ Wind (mil) |
|---|---|---|---|---|
| 0.293 | -20.60 | -2.100 | 4.50 | +0.700 |
| 0.31 | -19.40 | -0.900 | 4.10 | +0.300 |
| 0.326 ←baseline | -18.50 | +0.000 | 3.80 | +0.000 |
| 0.342 | -17.60 | +0.900 | 3.60 | -0.200 |
| 0.359 | -16.90 | +1.600 | 3.30 | -0.500 |

---

### Wind Speed

**At 300 yards:**

| Wind Speed | Elev (mil) | Δ Elev (mil) | Wind (mil) | Δ Wind (mil) |
|---|---|---|---|---|
| 0mph | -1.20 | +0.000 | 0.10 | -0.400 |
| 5mph | -1.20 | +0.000 | 0.30 | -0.200 |
| 10mph ←baseline | -1.20 | +0.000 | 0.50 | +0.000 |
| 15mph | -1.20 | +0.000 | 0.70 | +0.200 |
| 20mph | -1.20 | +0.000 | 1.00 | +0.500 |

**At 600 yards:**

| Wind Speed | Elev (mil) | Δ Elev (mil) | Wind (mil) | Δ Wind (mil) |
|---|---|---|---|---|
| 0mph | -3.90 | +0.000 | 0.10 | -1.000 |
| 5mph | -3.90 | +0.000 | 0.60 | -0.500 |
| 10mph ←baseline | -3.90 | +0.000 | 1.10 | +0.000 |
| 15mph | -3.90 | +0.000 | 1.60 | +0.500 |
| 20mph | -3.90 | +0.000 | 2.10 | +1.000 |

**At 1000 yards:**

| Wind Speed | Elev (mil) | Δ Elev (mil) | Wind (mil) | Δ Wind (mil) |
|---|---|---|---|---|
| 0mph | -8.80 | +0.000 | 0.20 | -1.900 |
| 5mph | -8.80 | +0.000 | 1.20 | -0.900 |
| 10mph ←baseline | -8.80 | +0.000 | 2.10 | +0.000 |
| 15mph | -8.80 | +0.000 | 3.10 | +1.000 |
| 20mph | -8.80 | +0.000 | 4.00 | +1.900 |

**At 1500 yards:**

| Wind Speed | Elev (mil) | Δ Elev (mil) | Wind (mil) | Δ Wind (mil) |
|---|---|---|---|---|
| 0mph | -18.50 | +0.000 | 0.40 | -3.400 |
| 5mph | -18.50 | +0.000 | 2.10 | -1.700 |
| 10mph ←baseline | -18.50 | +0.000 | 3.80 | +0.000 |
| 15mph | -18.50 | +0.000 | 5.60 | +1.800 |
| 20mph | -18.50 | +0.000 | 7.30 | +3.500 |

---

### Temperature

**At 300 yards:**

| Temperature | Elev (mil) | Δ Elev (mil) | Wind (mil) | Δ Wind (mil) |
|---|---|---|---|---|
| 0°F | -1.30 | -0.100 | 0.60 | +0.100 |
| 20°F | -1.30 | -0.100 | 0.50 | +0.000 |
| 40°F | -1.20 | +0.000 | 0.50 | +0.000 |
| 59°F ←baseline | -1.20 | +0.000 | 0.50 | +0.000 |
| 80°F | -1.20 | +0.000 | 0.50 | +0.000 |
| 100°F | -1.20 | +0.000 | 0.50 | +0.000 |

**At 600 yards:**

| Temperature | Elev (mil) | Δ Elev (mil) | Wind (mil) | Δ Wind (mil) |
|---|---|---|---|---|
| 0°F | -4.00 | -0.100 | 1.20 | +0.100 |
| 20°F | -4.00 | -0.100 | 1.20 | +0.100 |
| 40°F | -4.00 | -0.100 | 1.10 | +0.000 |
| 59°F ←baseline | -3.90 | +0.000 | 1.10 | +0.000 |
| 80°F | -3.90 | +0.000 | 1.10 | +0.000 |
| 100°F | -3.90 | +0.000 | 1.00 | -0.100 |

**At 1000 yards:**

| Temperature | Elev (mil) | Δ Elev (mil) | Wind (mil) | Δ Wind (mil) |
|---|---|---|---|---|
| 0°F | -9.30 | -0.500 | 2.40 | +0.300 |
| 20°F | -9.10 | -0.300 | 2.30 | +0.200 |
| 40°F | -9.00 | -0.200 | 2.20 | +0.100 |
| 59°F ←baseline | -8.80 | +0.000 | 2.10 | +0.000 |
| 80°F | -8.70 | +0.100 | 2.00 | -0.100 |
| 100°F | -8.60 | +0.200 | 2.00 | -0.100 |

**At 1500 yards:**

| Temperature | Elev (mil) | Δ Elev (mil) | Wind (mil) | Δ Wind (mil) |
|---|---|---|---|---|
| 0°F | -20.30 | -1.800 | 4.40 | +0.600 |
| 20°F | -19.60 | -1.100 | 4.20 | +0.400 |
| 40°F | -19.00 | -0.500 | 4.00 | +0.200 |
| 59°F ←baseline | -18.50 | +0.000 | 3.80 | +0.000 |
| 80°F | -17.90 | +0.600 | 3.70 | -0.100 |
| 100°F | -17.50 | +1.000 | 3.50 | -0.300 |

---

### Barometric Pressure

**At 300 yards:**

| Barometric Pressure | Elev (mil) | Δ Elev (mil) | Wind (mil) | Δ Wind (mil) |
|---|---|---|---|---|
| 25.0inHg | -1.20 | +0.000 | 0.40 | -0.100 |
| 27.0inHg | -1.20 | +0.000 | 0.50 | +0.000 |
| 28.0inHg | -1.20 | +0.000 | 0.50 | +0.000 |
| 29.0inHg | -1.20 | +0.000 | 0.50 | +0.000 |
| 29.92inHg ←baseline | -1.20 | +0.000 | 0.50 | +0.000 |
| 30.5inHg | -1.20 | +0.000 | 0.50 | +0.000 |

**At 600 yards:**

| Barometric Pressure | Elev (mil) | Δ Elev (mil) | Wind (mil) | Δ Wind (mil) |
|---|---|---|---|---|
| 25.0inHg | -3.70 | +0.200 | 0.90 | -0.200 |
| 27.0inHg | -3.80 | +0.100 | 1.00 | -0.100 |
| 28.0inHg | -3.80 | +0.100 | 1.00 | -0.100 |
| 29.0inHg | -3.90 | +0.000 | 1.10 | +0.000 |
| 29.92inHg ←baseline | -3.90 | +0.000 | 1.10 | +0.000 |
| 30.5inHg | -3.90 | +0.000 | 1.10 | +0.000 |

**At 1000 yards:**

| Barometric Pressure | Elev (mil) | Δ Elev (mil) | Wind (mil) | Δ Wind (mil) |
|---|---|---|---|---|
| 25.0inHg | -8.10 | +0.700 | 1.70 | -0.400 |
| 27.0inHg | -8.40 | +0.400 | 1.90 | -0.200 |
| 28.0inHg | -8.50 | +0.300 | 1.90 | -0.200 |
| 29.0inHg | -8.70 | +0.100 | 2.00 | -0.100 |
| 29.92inHg ←baseline | -8.80 | +0.000 | 2.10 | +0.000 |
| 30.5inHg | -8.90 | -0.100 | 2.20 | +0.100 |

**At 1500 yards:**

| Barometric Pressure | Elev (mil) | Δ Elev (mil) | Wind (mil) | Δ Wind (mil) |
|---|---|---|---|---|
| 25.0inHg | -15.90 | +2.600 | 3.00 | -0.800 |
| 27.0inHg | -16.80 | +1.700 | 3.30 | -0.500 |
| 28.0inHg | -17.40 | +1.100 | 3.50 | -0.300 |
| 29.0inHg | -17.90 | +0.600 | 3.70 | -0.100 |
| 29.92inHg ←baseline | -18.50 | +0.000 | 3.80 | +0.000 |
| 30.5inHg | -18.80 | -0.300 | 3.90 | +0.100 |

---

### Altitude

**At 300 yards:**

| Altitude | Elev (mil) | Δ Elev (mil) | Wind (mil) | Δ Wind (mil) |
|---|---|---|---|---|
| 0ft ←baseline | -1.20 | +0.000 | 0.50 | +0.000 |
| 2000ft | -1.20 | +0.000 | 0.50 | +0.000 |
| 4000ft | -1.20 | +0.000 | 0.40 | -0.100 |
| 5280ft | -1.20 | +0.000 | 0.40 | -0.100 |
| 7000ft | -1.20 | +0.000 | 0.40 | -0.100 |

**At 600 yards:**

| Altitude | Elev (mil) | Δ Elev (mil) | Wind (mil) | Δ Wind (mil) |
|---|---|---|---|---|
| 0ft ←baseline | -3.90 | +0.000 | 1.10 | +0.000 |
| 2000ft | -3.80 | +0.100 | 1.00 | -0.100 |
| 4000ft | -3.80 | +0.100 | 0.90 | -0.200 |
| 5280ft | -3.70 | +0.200 | 0.90 | -0.200 |
| 7000ft | -3.70 | +0.200 | 0.80 | -0.300 |

**At 1000 yards:**

| Altitude | Elev (mil) | Δ Elev (mil) | Wind (mil) | Δ Wind (mil) |
|---|---|---|---|---|
| 0ft ←baseline | -8.80 | +0.000 | 2.10 | +0.000 |
| 2000ft | -8.50 | +0.300 | 1.90 | -0.200 |
| 4000ft | -8.20 | +0.600 | 1.80 | -0.300 |
| 5280ft | -8.10 | +0.700 | 1.70 | -0.400 |
| 7000ft | -7.80 | +1.000 | 1.50 | -0.600 |

**At 1500 yards:**

| Altitude | Elev (mil) | Δ Elev (mil) | Wind (mil) | Δ Wind (mil) |
|---|---|---|---|---|
| 0ft ←baseline | -18.50 | +0.000 | 3.80 | +0.000 |
| 2000ft | -17.30 | +1.200 | 3.50 | -0.300 |
| 4000ft | -16.30 | +2.200 | 3.10 | -0.700 |
| 5280ft | -15.70 | +2.800 | 2.90 | -0.900 |
| 7000ft | -15.00 | +3.500 | 2.60 | -1.200 |

---

### Humidity

**At 300 yards:**

| Humidity | Elev (mil) | Δ Elev (mil) | Wind (mil) | Δ Wind (mil) |
|---|---|---|---|---|
| 0% ←baseline | -1.20 | +0.000 | 0.50 | +0.000 |
| 25% | -1.20 | +0.000 | 0.50 | +0.000 |
| 50% | -1.20 | +0.000 | 0.50 | +0.000 |
| 75% | -1.20 | +0.000 | 0.50 | +0.000 |
| 100% | -1.20 | +0.000 | 0.50 | +0.000 |

**At 600 yards:**

| Humidity | Elev (mil) | Δ Elev (mil) | Wind (mil) | Δ Wind (mil) |
|---|---|---|---|---|
| 0% ←baseline | -3.90 | +0.000 | 1.10 | +0.000 |
| 25% | -3.90 | +0.000 | 1.10 | +0.000 |
| 50% | -3.90 | +0.000 | 1.10 | +0.000 |
| 75% | -3.90 | +0.000 | 1.10 | +0.000 |
| 100% | -3.90 | +0.000 | 1.10 | +0.000 |

**At 1000 yards:**

| Humidity | Elev (mil) | Δ Elev (mil) | Wind (mil) | Δ Wind (mil) |
|---|---|---|---|---|
| 0% ←baseline | -8.80 | +0.000 | 2.10 | +0.000 |
| 25% | -8.80 | +0.000 | 2.10 | +0.000 |
| 50% | -8.80 | +0.000 | 2.10 | +0.000 |
| 75% | -8.80 | +0.000 | 2.10 | +0.000 |
| 100% | -8.80 | +0.000 | 2.10 | +0.000 |

**At 1500 yards:**

| Humidity | Elev (mil) | Δ Elev (mil) | Wind (mil) | Δ Wind (mil) |
|---|---|---|---|---|
| 0% ←baseline | -18.50 | +0.000 | 3.80 | +0.000 |
| 25% | -18.40 | +0.100 | 3.80 | +0.000 |
| 50% | -18.40 | +0.100 | 3.80 | +0.000 |
| 75% | -18.40 | +0.100 | 3.80 | +0.000 |
| 100% | -18.30 | +0.200 | 3.80 | +0.000 |

---

### Sight Height Over Bore

**At 300 yards:**

| Sight Height Over Bore | Elev (mil) | Δ Elev (mil) | Wind (mil) | Δ Wind (mil) |
|---|---|---|---|---|
| 1.25in | -1.30 | -0.100 | 0.50 | +0.000 |
| 1.5in ←baseline | -1.20 | +0.000 | 0.50 | +0.000 |
| 1.75in | -1.20 | +0.000 | 0.50 | +0.000 |
| 2.0in | -1.10 | +0.100 | 0.50 | +0.000 |
| 2.5in | -1.10 | +0.100 | 0.50 | +0.000 |

**At 600 yards:**

| Sight Height Over Bore | Elev (mil) | Δ Elev (mil) | Wind (mil) | Δ Wind (mil) |
|---|---|---|---|---|
| 1.25in | -4.00 | -0.100 | 1.10 | +0.000 |
| 1.5in ←baseline | -3.90 | +0.000 | 1.10 | +0.000 |
| 1.75in | -3.90 | +0.000 | 1.10 | +0.000 |
| 2.0in | -3.80 | +0.100 | 1.10 | +0.000 |
| 2.5in | -3.70 | +0.200 | 1.10 | +0.000 |

**At 1000 yards:**

| Sight Height Over Bore | Elev (mil) | Δ Elev (mil) | Wind (mil) | Δ Wind (mil) |
|---|---|---|---|---|
| 1.25in | -8.90 | -0.100 | 2.10 | +0.000 |
| 1.5in ←baseline | -8.80 | +0.000 | 2.10 | +0.000 |
| 1.75in | -8.80 | +0.000 | 2.10 | +0.000 |
| 2.0in | -8.70 | +0.100 | 2.10 | +0.000 |
| 2.5in | -8.60 | +0.200 | 2.10 | +0.000 |

**At 1500 yards:**

| Sight Height Over Bore | Elev (mil) | Δ Elev (mil) | Wind (mil) | Δ Wind (mil) |
|---|---|---|---|---|
| 1.25in | -18.50 | +0.000 | 3.80 | +0.000 |
| 1.5in ←baseline | -18.50 | +0.000 | 3.80 | +0.000 |
| 1.75in | -18.40 | +0.100 | 3.80 | +0.000 |
| 2.0in | -18.30 | +0.200 | 3.80 | +0.000 |
| 2.5in | -18.20 | +0.300 | 3.80 | +0.000 |

---

### Zero Distance

**At 300 yards:**

| Zero Distance | Elev (mil) | Δ Elev (mil) | Wind (mil) | Δ Wind (mil) |
|---|---|---|---|---|
| 50yd | -1.20 | +0.000 | 0.50 | +0.000 |
| 100yd ←baseline | -1.20 | +0.000 | 0.50 | +0.000 |
| 200yd | -0.70 | +0.500 | 0.50 | +0.000 |
| 300yd | -0.00 | +1.200 | 0.50 | +0.000 |

**At 600 yards:**

| Zero Distance | Elev (mil) | Δ Elev (mil) | Wind (mil) | Δ Wind (mil) |
|---|---|---|---|---|
| 50yd | -3.90 | +0.000 | 1.10 | +0.000 |
| 100yd ←baseline | -3.90 | +0.000 | 1.10 | +0.000 |
| 200yd | -3.40 | +0.500 | 1.10 | +0.000 |
| 300yd | -2.70 | +1.200 | 1.10 | +0.000 |

**At 1000 yards:**

| Zero Distance | Elev (mil) | Δ Elev (mil) | Wind (mil) | Δ Wind (mil) |
|---|---|---|---|---|
| 50yd | -8.80 | +0.000 | 2.10 | +0.000 |
| 100yd ←baseline | -8.80 | +0.000 | 2.10 | +0.000 |
| 200yd | -8.30 | +0.500 | 2.10 | +0.000 |
| 300yd | -7.60 | +1.200 | 2.10 | +0.000 |

**At 1500 yards:**

| Zero Distance | Elev (mil) | Δ Elev (mil) | Wind (mil) | Δ Wind (mil) |
|---|---|---|---|---|
| 50yd | -18.40 | +0.100 | 3.80 | +0.000 |
| 100yd ←baseline | -18.50 | +0.000 | 3.80 | +0.000 |
| 200yd | -17.90 | +0.600 | 3.80 | +0.000 |
| 300yd | -17.20 | +1.300 | 3.80 | +0.000 |

---

### Bullet Length

**At 300 yards:**

| Bullet Length | Elev (mil) | Δ Elev (mil) | Wind (mil) | Δ Wind (mil) |
|---|---|---|---|---|
| 1.2in | -1.20 | +0.000 | 0.50 | +0.000 |
| 1.3in | -1.20 | +0.000 | 0.50 | +0.000 |
| 1.376in ←baseline | -1.20 | +0.000 | 0.50 | +0.000 |
| 1.45in | -1.20 | +0.000 | 0.50 | +0.000 |
| 1.55in | -1.20 | +0.000 | 0.50 | +0.000 |

**At 600 yards:**

| Bullet Length | Elev (mil) | Δ Elev (mil) | Wind (mil) | Δ Wind (mil) |
|---|---|---|---|---|
| 1.2in | -3.90 | +0.000 | 1.10 | +0.000 |
| 1.3in | -3.90 | +0.000 | 1.10 | +0.000 |
| 1.376in ←baseline | -3.90 | +0.000 | 1.10 | +0.000 |
| 1.45in | -3.90 | +0.000 | 1.10 | +0.000 |
| 1.55in | -3.90 | +0.000 | 1.10 | +0.000 |

**At 1000 yards:**

| Bullet Length | Elev (mil) | Δ Elev (mil) | Wind (mil) | Δ Wind (mil) |
|---|---|---|---|---|
| 1.2in | -8.80 | +0.000 | 2.20 | +0.100 |
| 1.3in | -8.80 | +0.000 | 2.10 | +0.000 |
| 1.376in ←baseline | -8.80 | +0.000 | 2.10 | +0.000 |
| 1.45in | -8.80 | +0.000 | 2.10 | +0.000 |
| 1.55in | -8.80 | +0.000 | 2.10 | +0.000 |

**At 1500 yards:**

| Bullet Length | Elev (mil) | Δ Elev (mil) | Wind (mil) | Δ Wind (mil) |
|---|---|---|---|---|
| 1.2in | -18.50 | +0.000 | 4.00 | +0.200 |
| 1.3in | -18.50 | +0.000 | 3.90 | +0.100 |
| 1.376in ←baseline | -18.50 | +0.000 | 3.80 | +0.000 |
| 1.45in | -18.50 | +0.000 | 3.80 | +0.000 |
| 1.55in | -18.50 | +0.000 | 3.80 | +0.000 |

---

### Barrel Twist Rate

**At 300 yards:**

| Barrel Twist Rate | Elev (mil) | Δ Elev (mil) | Wind (mil) | Δ Wind (mil) |
|---|---|---|---|---|
| 7.0in | -1.20 | +0.000 | 0.50 | +0.000 |
| 7.5in | -1.20 | +0.000 | 0.50 | +0.000 |
| 8.0in ←baseline | -1.20 | +0.000 | 0.50 | +0.000 |
| 8.5in | -1.20 | +0.000 | 0.50 | +0.000 |
| 9.0in | -1.20 | +0.000 | 0.50 | +0.000 |
| 10.0in | -1.20 | +0.000 | 0.50 | +0.000 |

**At 600 yards:**

| Barrel Twist Rate | Elev (mil) | Δ Elev (mil) | Wind (mil) | Δ Wind (mil) |
|---|---|---|---|---|
| 7.0in | -3.90 | +0.000 | 1.10 | +0.000 |
| 7.5in | -3.90 | +0.000 | 1.10 | +0.000 |
| 8.0in ←baseline | -3.90 | +0.000 | 1.10 | +0.000 |
| 8.5in | -3.90 | +0.000 | 1.10 | +0.000 |
| 9.0in | -3.90 | +0.000 | 1.10 | +0.000 |
| 10.0in | -3.90 | +0.000 | 1.10 | +0.000 |

**At 1000 yards:**

| Barrel Twist Rate | Elev (mil) | Δ Elev (mil) | Wind (mil) | Δ Wind (mil) |
|---|---|---|---|---|
| 7.0in | -8.80 | +0.000 | 2.10 | +0.000 |
| 7.5in | -8.80 | +0.000 | 2.10 | +0.000 |
| 8.0in ←baseline | -8.80 | +0.000 | 2.10 | +0.000 |
| 8.5in | -8.80 | +0.000 | 2.10 | +0.000 |
| 9.0in | -8.80 | +0.000 | 2.10 | +0.000 |
| 10.0in | -8.80 | +0.000 | 2.10 | +0.000 |

**At 1500 yards:**

| Barrel Twist Rate | Elev (mil) | Δ Elev (mil) | Wind (mil) | Δ Wind (mil) |
|---|---|---|---|---|
| 7.0in | -18.50 | +0.000 | 3.90 | +0.100 |
| 7.5in | -18.50 | +0.000 | 3.90 | +0.100 |
| 8.0in ←baseline | -18.50 | +0.000 | 3.80 | +0.000 |
| 8.5in | -18.50 | +0.000 | 3.80 | +0.000 |
| 9.0in | -18.50 | +0.000 | 3.80 | +0.000 |
| 10.0in | -18.50 | +0.000 | 3.80 | +0.000 |

---

### Shooting Angle (LOS)

**At 300 yards:**

| Shooting Angle (LOS) | Elev (mil) | Δ Elev (mil) | Wind (mil) | Δ Wind (mil) |
|---|---|---|---|---|
| -45deg | -0.60 | +0.600 | 0.50 | +0.000 |
| -30deg | -0.90 | +0.300 | 0.50 | +0.000 |
| -15deg | -1.20 | +0.000 | 0.50 | +0.000 |
| 0deg ←baseline | -1.20 | +0.000 | 0.50 | +0.000 |
| 15deg | -1.20 | +0.000 | 0.50 | +0.000 |
| 30deg | -0.90 | +0.300 | 0.50 | +0.000 |
| 45deg | -0.60 | +0.600 | 0.50 | +0.000 |

**At 600 yards:**

| Shooting Angle (LOS) | Elev (mil) | Δ Elev (mil) | Wind (mil) | Δ Wind (mil) |
|---|---|---|---|---|
| -45deg | -2.50 | +1.400 | 1.10 | +0.000 |
| -30deg | -3.20 | +0.700 | 1.10 | +0.000 |
| -15deg | -3.70 | +0.200 | 1.10 | +0.000 |
| 0deg ←baseline | -3.90 | +0.000 | 1.10 | +0.000 |
| 15deg | -3.80 | +0.100 | 1.10 | +0.000 |
| 30deg | -3.30 | +0.600 | 1.10 | +0.000 |
| 45deg | -2.50 | +1.400 | 1.10 | +0.000 |

**At 1000 yards:**

| Shooting Angle (LOS) | Elev (mil) | Δ Elev (mil) | Wind (mil) | Δ Wind (mil) |
|---|---|---|---|---|
| -45deg | -5.90 | +2.900 | 2.10 | +0.000 |
| -30deg | -7.50 | +1.300 | 2.10 | +0.000 |
| -15deg | -8.50 | +0.300 | 2.10 | +0.000 |
| 0deg ←baseline | -8.80 | +0.000 | 2.10 | +0.000 |
| 15deg | -8.50 | +0.300 | 2.10 | +0.000 |
| 30deg | -7.60 | +1.200 | 2.10 | +0.000 |
| 45deg | -6.00 | +2.800 | 2.00 | -0.100 |

**At 1500 yards:**

| Shooting Angle (LOS) | Elev (mil) | Δ Elev (mil) | Wind (mil) | Δ Wind (mil) |
|---|---|---|---|---|
| -45deg | -12.60 | +5.900 | 3.80 | +0.000 |
| -30deg | -15.70 | +2.800 | 3.90 | +0.100 |
| -15deg | -17.70 | +0.800 | 3.90 | +0.100 |
| 0deg ←baseline | -18.50 | +0.000 | 3.80 | +0.000 |
| 15deg | -17.80 | +0.700 | 3.80 | +0.000 |
| 30deg | -15.90 | +2.600 | 3.70 | -0.100 |
| 45deg | -12.90 | +5.600 | 3.60 | -0.200 |

---

## Sensitivity Rankings at 1000 Yards

Variables ranked by maximum absolute delta in mils across the tested range.

### Elevation Hold Sensitivity

| Rank | Variable | Max |Δ Elev| (mil) |
|------|----------|---------------------|
| 1 | Shooting Angle (LOS) | 2.900 |
| 2 | Muzzle Velocity | 1.300 |
| 3 | Zero Distance | 1.200 |
| 4 | Altitude | 1.000 |
| 5 | Barometric Pressure | 0.700 |
| 6 | Ballistic Coefficient (G7) | 0.600 |
| 7 | Temperature | 0.500 |
| 8 | Sight Height Over Bore | 0.200 |
| 9 | Wind Speed | 0.000 |
| 10 | Humidity | 0.000 |
| 11 | Bullet Length | 0.000 |
| 12 | Barrel Twist Rate | 0.000 |

### Windage Hold Sensitivity

| Rank | Variable | Max |Δ Wind| (mil) |
|------|----------|---------------------|
| 1 | Wind Speed | 1.900 |
| 2 | Altitude | 0.600 |
| 3 | Barometric Pressure | 0.400 |
| 4 | Ballistic Coefficient (G7) | 0.300 |
| 5 | Temperature | 0.300 |
| 6 | Muzzle Velocity | 0.200 |
| 7 | Bullet Length | 0.100 |
| 8 | Shooting Angle (LOS) | 0.100 |
| 9 | Humidity | 0.000 |
| 10 | Sight Height Over Bore | 0.000 |
| 11 | Zero Distance | 0.000 |
| 12 | Barrel Twist Rate | 0.000 |

### Elevation Sensitivity Across All Distances

| Variable | Δ@300 | Δ@600 | Δ@1000 | Δ@1500 |
|----------|-------|-------|--------|--------|
| Muzzle Velocity | 0.200 | 0.600 | 1.300 | 2.700 |
| Ballistic Coefficient (G7) | 0.100 | 0.200 | 0.600 | 2.100 |
| Wind Speed | 0.000 | 0.000 | 0.000 | 0.000 |
| Temperature | 0.100 | 0.100 | 0.500 | 1.800 |
| Barometric Pressure | 0.000 | 0.200 | 0.700 | 2.600 |
| Altitude | 0.000 | 0.200 | 1.000 | 3.500 |
| Humidity | 0.000 | 0.000 | 0.000 | 0.200 |
| Sight Height Over Bore | 0.100 | 0.200 | 0.200 | 0.300 |
| Zero Distance | 1.200 | 1.200 | 1.200 | 1.300 |
| Bullet Length | 0.000 | 0.000 | 0.000 | 0.000 |
| Barrel Twist Rate | 0.000 | 0.000 | 0.000 | 0.000 |
| Shooting Angle (LOS) | 0.600 | 1.400 | 2.900 | 5.900 |

### Windage Sensitivity Across All Distances

| Variable | Δ@300 | Δ@600 | Δ@1000 | Δ@1500 |
|----------|-------|-------|--------|--------|
| Muzzle Velocity | 0.100 | 0.100 | 0.200 | 0.400 |
| Ballistic Coefficient (G7) | 0.100 | 0.100 | 0.300 | 0.700 |
| Wind Speed | 0.500 | 1.000 | 1.900 | 3.500 |
| Temperature | 0.100 | 0.100 | 0.300 | 0.600 |
| Barometric Pressure | 0.100 | 0.200 | 0.400 | 0.800 |
| Altitude | 0.100 | 0.300 | 0.600 | 1.200 |
| Humidity | 0.000 | 0.000 | 0.000 | 0.000 |
| Sight Height Over Bore | 0.000 | 0.000 | 0.000 | 0.000 |
| Zero Distance | 0.000 | 0.000 | 0.000 | 0.000 |
| Bullet Length | 0.000 | 0.000 | 0.100 | 0.200 |
| Barrel Twist Rate | 0.000 | 0.000 | 0.000 | 0.100 |
| Shooting Angle (LOS) | 0.000 | 0.000 | 0.100 | 0.200 |

---

## Practical Takeaways

### What matters most for elevation

The dominant variables — the ones where small errors or changes cause the biggest misses — are shooting angle, muzzle velocity, and (at ELR distances) altitude/density altitude and BC.

**Shooting angle** is the biggest single factor. At 45° up or down, your 1000yd elevation hold drops from 8.8 to ~6.0 mil — a 2.9 mil error, or roughly 105 inches at 1000 yards. This is the cosine effect, and it grows dramatically with distance (5.9 mil delta at 1500 yards). Any ballistic app absolutely must account for this.

**Muzzle velocity** is the next most critical. A 150 fps error (e.g. 2560 vs 2710) shifts elevation by 1.3 mil at 1000 yards — about 47 inches. Even a 50 fps error (one lot to another, or temperature-induced MV shift) is ~0.4 mil at 1000 yards. This is why truing your MV is essential for long-range shooting.

**Altitude and barometric pressure** both affect air density and become increasingly important with distance. Going from sea level to 7000 ft shifts elevation by 1.0 mil at 1000 yards and 3.5 mil at 1500 yards. These variables are effectively measuring the same underlying thing (air density), but separately: altitude through the standard atmosphere model, and pressure as a direct density input.

**BC** matters more than you'd think at extreme range. A 10% BC error (0.293 vs 0.326) is 0.6 mil at 1000 yards but grows to 2.1 mil at 1500 yards. This is why Applied Ballistics measured BCs (vs manufacturer-published) and G7 drag model (vs G1) are worth pursuing for ELR work.

**Temperature** is moderate — a 59°F swing (0°F to 59°F) shifts 0.5 mil at 1000 yards. It matters, but less than MV, BC, or altitude.

### What matters most for windage

**Wind speed** dominates windage, as expected. The delta is perfectly linear: each 5 mph of wind adds ~0.95 mil at 1000 yards. At 20 mph, your total wind hold is 4.0 mil (vs 2.1 at 10 mph). Wind reading is the single most important field skill for a long-range shooter.

**Altitude and pressure** are the second-most important windage factors. Thinner air at 7000 ft reduces wind drift by 0.6 mil at 1000 yards (2.1 → 1.5 mil). Shooters at elevation get a small windage advantage because the bullet is pushed less by less-dense air.

**BC and temperature** have modest windage effects (0.3 mil at 1000 yards).

### What doesn't matter (much)

**Humidity**: Essentially zero effect across the full 0–100% range, even at 1500 yards. Not worth worrying about.

**Barrel twist rate**: Zero measurable effect on elevation, and only 0.1 mil windage difference at 1500 yards (via spin drift). Within the range of twist rates used for 6.5 CM (7" to 10"), it's a non-factor for holds. (Twist does matter for stability/accuracy, just not for hold calculations.)

**Bullet length**: Near-zero effect on elevation, and only a tiny spin-drift-related windage effect at extreme range (0.2 mil at 1500 yards). Accuracy here is a "nice to have," not a "need to have."

**Sight height over bore**: Small and constant — max 0.3 mil shift at 1500 yards across a 1.25" range of sight heights. It matters for near-zero behavior but is nearly irrelevant at distance.

### The hierarchy

For a 1000-yard shooter, here's what to get right (in order):

1. **Shooting angle** — use a cosine indicator or app with inclinometer
2. **Wind reading** — the only major variable that doesn't stay constant between shots
3. **Muzzle velocity** — true it, and know your lot-to-lot / temperature variations
4. **Density altitude** (altitude + pressure + temperature combined) — use a Kestrel or weather station
5. **BC** — use measured G7 values, not manufacturer G1
6. Everything else is in the noise for practical purposes

---

*Data generated from the JBM Ballistics drift calculator (jbmballistics.com) on March 3, 2026. All values are for the 6.5 Creedmoor 140gr ELD Match baseline configuration described above. 68 queries, single-variable perturbation methodology.*