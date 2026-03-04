"""
JBM Ballistics Scraper Package

A comprehensive tool for submitting ballistic calculations to the JBM drift calculator,
parsing results, and generating decomposed validation test matrices.
"""

from jbm_scraper import JBMInput, JBMResult, JBMScraper
from validation_matrix import ValidationSuite, CARTRIDGES

__version__ = "1.0.0"
__all__ = ["JBMInput", "JBMResult", "JBMScraper", "ValidationSuite", "CARTRIDGES"]
