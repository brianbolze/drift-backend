"""
JBM Ballistics Drift Calculator Scraper

Submits POST requests to JBM drift calculator, parses HTML output into structured data.
Supports all major ballistic parameters for comprehensive trajectory analysis.

Usage:
    scraper = JBMScraper()
    results = scraper.query(JBMInput(bc=0.5, m_vel=3000))
    for result in results:
        print(f"At {result.range_yd}yd: drop={result.drop_in}in, drift={result.windage_in}in")
"""

import requests
from dataclasses import dataclass, field, asdict
from typing import Optional
import re
from html.parser import HTMLParser
import logging

logger = logging.getLogger(__name__)


@dataclass
class JBMInput:
    """
    Complete input specification for JBM drift calculator.
    All defaults match ICAO standard atmosphere and sensible ballistic parameters.
    """

    # Bullet specification
    b_id_v: int = -1  # Bullet library ID (-1 = manual entry)
    bc_v: float = 0.5  # Ballistic coefficient
    d_f_v: int = 0  # Drag function: 0=G1, 1=G2, 2=G5, 3=G6, 4=G7, 5=G8, 6=GI, 7=GL, 8=RA4

    # Bullet weight and caliber
    bt_wgt_v: float = 220.0
    bt_wgt_u: int = 23  # 23=gr, 25=gm

    cal_v: float = 0.308
    cal_u: int = 8  # 8=in

    blt_len_v: float = 1.5
    blt_len_u: int = 8  # 8=in

    tip_len_v: float = 0.0
    tip_len_u: int = 8  # 8=in

    # Velocity and chronograph
    m_vel_v: float = 3000.0
    m_vel_u: int = 16  # 16=ft/s, 17=m/s

    ch_dst_v: float = 10.0
    ch_dst_u: int = 10  # 10=ft

    # Sight geometry
    hgt_sgt_v: float = 1.5
    hgt_sgt_u: int = 8  # 8=in

    ofs_sgt_v: float = 0.0
    ofs_sgt_u: int = 8  # 8=in

    hgt_zer_v: float = 0.0
    hgt_zer_u: int = 8  # 8=in

    ofs_zer_v: float = 0.0
    ofs_zer_u: int = 8  # 8=in

    # Adjustments (MOA by default)
    azm_v: float = 0.0
    azm_u: int = 4  # 4=MOA

    ele_v: float = 0.0
    ele_u: int = 4  # 4=MOA

    # Shooting angles
    los_v: float = 0.0  # Line of sight angle (deg)
    cnt_v: float = 0.0  # Cant angle (deg)

    # Barrel twist
    b_twt_v: float = 12.0
    b_twt_u: int = 8  # 8=in

    b_twt_dir_v: int = 1  # 0=Left, 1=Right

    # Wind specification
    spd_wnd_v: float = 10.0
    spd_wnd_u: int = 14  # 14=mph

    ang_wnd_v: float = 90.0  # Wind angle (deg, 90=full crosswind)

    # Target specification
    spd_tgt_v: float = 10.0
    spd_tgt_u: int = 14  # 14=mph

    ang_tgt_v: float = 90.0  # Target angle (deg)

    siz_tgt_v: float = 12.0
    siz_tgt_u: int = 8  # 8=in

    # Range specification
    rng_min_v: int = 0
    rng_max_v: int = 1000
    rng_inc_v: int = 100
    rng_zer_v: int = 100  # Zero range

    # Atmosphere
    tmp_v: float = 59.0
    tmp_u: int = 19  # 18=°C, 19=°F

    prs_v: float = 29.92
    prs_u: int = 22  # 22=inHg

    hum_v: float = 0.0  # Humidity (%)

    alt_v: float = 0.0
    alt_u: int = 10  # 10=ft

    # Checkboxes (True = send "on", False = omit)
    std_alt_v: bool = False
    cor_prs_v: bool = True  # Pressure is corrected (sea level)
    cor_ele_v: bool = True  # Elevation correction for zero range
    cor_azm_v: bool = False  # Windage correction for zero range
    inc_drf_v: bool = True  # Include Spin Drift (KEY toggle!)
    inc_ds_v: bool = False  # Include danger space
    def_cnt_v: bool = True  # Default count
    rng_un_v: bool = False  # Range in meters
    pbr_zer_v: bool = False  # Point blank range zero
    mrk_trs_v: bool = False  # Mark transonic
    ext_row_v: bool = False  # Extended rows
    rnd_clk_v: bool = False  # Round clicks

    # Display options
    col_eng_v: int = 0  # Energy column formula (0=ft·lbs)

    col1_un_v: float = 1.00
    col1_un_u: int = 8  # 8=in (inches)

    col2_un_v: float = 1.00
    col2_un_u: int = 2  # 2=mrad (mil)

    # Raw HTML response (populated after query)
    _raw_html: Optional[str] = field(default=None, repr=False)

    def to_form_data(self) -> dict:
        """
        Convert JBMInput to HTTP form POST data.
        Handles checkbox serialization (on/omit) and field naming.
        """
        data = {}

        # Numeric fields - always include
        numeric_fields = [
            "b_id_v", "bc_v", "d_f_v",
            "bt_wgt_v", "bt_wgt_u", "cal_v", "cal_u", "blt_len_v", "blt_len_u",
            "tip_len_v", "tip_len_u",
            "m_vel_v", "m_vel_u", "ch_dst_v", "ch_dst_u",
            "hgt_sgt_v", "hgt_sgt_u", "ofs_sgt_v", "ofs_sgt_u",
            "hgt_zer_v", "hgt_zer_u", "ofs_zer_v", "ofs_zer_u",
            "azm_v", "azm_u", "ele_v", "ele_u",
            "los_v", "cnt_v",
            "b_twt_v", "b_twt_u", "b_twt_dir_v",
            "spd_wnd_v", "spd_wnd_u", "ang_wnd_v",
            "spd_tgt_v", "spd_tgt_u", "ang_tgt_v",
            "siz_tgt_v", "siz_tgt_u",
            "rng_min_v", "rng_max_v", "rng_inc_v", "rng_zer_v",
            "tmp_v", "tmp_u", "prs_v", "prs_u", "hum_v", "alt_v", "alt_u",
            "col_eng_v", "col1_un_v", "col1_un_u", "col2_un_v", "col2_un_u",
        ]

        for field_name in numeric_fields:
            value = getattr(self, field_name)
            # Remove the trailing _v or _u for form field names
            form_name = field_name.replace("_v", ".v").replace("_u", ".u")
            data[form_name] = str(value)

        # Checkbox fields - only include if True
        checkbox_fields = [
            "std_alt_v", "cor_prs_v", "cor_ele_v", "cor_azm_v",
            "inc_drf_v", "inc_ds_v", "def_cnt_v", "rng_un_v",
            "pbr_zer_v", "mrk_trs_v", "ext_row_v", "rnd_clk_v",
        ]

        for field_name in checkbox_fields:
            if getattr(self, field_name):
                form_name = field_name.replace("_v", ".v")
                data[form_name] = "on"

        return data


@dataclass
class JBMResult:
    """Single row of trajectory output from JBM"""

    range_yd: float  # Range in yards
    drop_in: float  # Vertical drop in inches
    drop_mil: float  # Vertical drop in mils (milliradians)
    windage_in: float  # Horizontal drift in inches
    windage_mil: float  # Horizontal drift in mils
    velocity_fps: float  # Velocity in feet per second
    mach: float  # Mach number
    energy_ftlbs: float  # Kinetic energy in foot-pounds
    tof_s: float  # Time of flight in seconds
    lead_in: Optional[float] = None  # Lead distance in inches (if present)
    lead_mil: Optional[float] = None  # Lead distance in mils (if present)


class JBMScraper:
    """
    Submits ballistic calculations to JBM and parses the results.
    """

    URL = "https://jbmballistics.com/cgi-bin/jbmtraj_drift-5.1.cgi"
    REFERER = "https://jbmballistics.com/cgi-bin/jbmtraj_drift-5.1.cgi"

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()

    def query(self, input_params: JBMInput) -> list[JBMResult]:
        """
        Submit ballistic parameters and retrieve trajectory table.

        Args:
            input_params: JBMInput object with all ballistic parameters

        Returns:
            List of JBMResult objects, one per range increment

        Raises:
            requests.RequestException: HTTP request failed
            ValueError: Failed to parse HTML response
        """
        form_data = input_params.to_form_data()

        headers = {
            "Referer": self.REFERER,
            "User-Agent": "Mozilla/5.0 (ballistics-scraper)",
        }

        try:
            response = self.session.post(
                self.URL,
                data=form_data,
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Failed to query JBM: {e}")
            raise

        # Store raw HTML for auditability
        input_params._raw_html = response.text

        try:
            results = self._parse_results(response.text)
        except Exception as e:
            logger.error(f"Failed to parse JBM response: {e}")
            raise ValueError(f"HTML parsing failed: {e}") from e

        return results

    def _parse_results(self, html: str) -> list[JBMResult]:
        """
        Parse HTML response table into JBMResult objects.

        The table contains columns:
        Range(yd), Drop(in), Drop(mil), Windage(in), Windage(mil),
        Velocity(ft/s), Mach, Energy(ft·lbs), Time(s), Lead(in), Lead(mil)

        Args:
            html: HTML response from JBM server

        Returns:
            List of JBMResult objects
        """
        results = []

        # Find the results table
        table_match = re.search(r"<table[^>]*>.*?</table>", html, re.DOTALL)
        if not table_match:
            raise ValueError("No results table found in HTML response")

        table_html = table_match.group(0)

        # Extract all table rows
        row_pattern = r"<tr[^>]*>(.*?)</tr>"
        rows = re.findall(row_pattern, table_html, re.DOTALL)

        if not rows:
            raise ValueError("No rows found in results table")

        # Skip header rows (first row is typically the header)
        for row_html in rows[1:]:
            # Extract all cells
            cell_pattern = r"<td[^>]*>(.*?)</td>"
            cells = re.findall(cell_pattern, row_html, re.DOTALL)

            if not cells:
                continue

            # Clean cell content: remove HTML tags, trim whitespace
            cells = [
                re.sub(r"<[^>]+>", "", cell).strip()
                for cell in cells
            ]

            # Filter empty cells
            cells = [c for c in cells if c]

            if len(cells) < 9:
                # Skip malformed rows
                continue

            try:
                # Parse the data - handle optional lead columns
                range_yd = float(cells[0])
                drop_in = float(cells[1])
                drop_mil = float(cells[2])
                windage_in = float(cells[3])
                windage_mil = float(cells[4])
                velocity_fps = float(cells[5])
                mach = float(cells[6])
                energy_ftlbs = float(cells[7])
                tof_s = float(cells[8])

                # Lead columns may be optional
                lead_in = None
                lead_mil = None
                if len(cells) > 9:
                    try:
                        lead_in = float(cells[9])
                    except (ValueError, IndexError):
                        pass
                if len(cells) > 10:
                    try:
                        lead_mil = float(cells[10])
                    except (ValueError, IndexError):
                        pass

                result = JBMResult(
                    range_yd=range_yd,
                    drop_in=drop_in,
                    drop_mil=drop_mil,
                    windage_in=windage_in,
                    windage_mil=windage_mil,
                    velocity_fps=velocity_fps,
                    mach=mach,
                    energy_ftlbs=energy_ftlbs,
                    tof_s=tof_s,
                    lead_in=lead_in,
                    lead_mil=lead_mil,
                )
                results.append(result)

            except (ValueError, IndexError) as e:
                logger.warning(f"Failed to parse row: {cells}, error: {e}")
                continue

        return results


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)

    # Create a scraper and query with default parameters
    scraper = JBMScraper()

    # Test with .308 Win parameters
    test_input = JBMInput(
        bc_v=0.5,
        d_f_v=0,  # G1
        bt_wgt_v=175,
        cal_v=0.308,
        m_vel_v=2600,
        rng_max_v=1000,
        rng_inc_v=100,
    )

    try:
        results = scraper.query(test_input)
        print(f"Retrieved {len(results)} trajectory points")
        for result in results[:5]:
            print(
                f"  {result.range_yd:6.0f}yd: "
                f"drop={result.drop_in:7.2f}in ({result.drop_mil:6.2f}mil), "
                f"drift={result.windage_in:7.2f}in ({result.windage_mil:6.2f}mil), "
                f"vel={result.velocity_fps:7.1f}fps"
            )
    except Exception as e:
        logger.error(f"Query failed: {e}")
