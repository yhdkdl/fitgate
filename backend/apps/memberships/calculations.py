"""Body composition calculations: BMI and US Navy circumference method body-fat percentage."""

import math
from typing import Any, Dict, Optional


def calculate_bmi(
    weight_kg: Optional[float | int],
    height_cm: Optional[float | int],
) -> Optional[float]:
    """
    Calculate Body Mass Index (BMI):
    BMI = weight_kg / (height_cm / 100) ^ 2

    Returns BMI rounded to 1 decimal place, or None if inputs are invalid or missing.
    """
    if weight_kg is None or height_cm is None:
        return None

    try:
        w = float(weight_kg)
        h = float(height_cm)
    except (TypeError, ValueError):
        return None

    if w <= 0 or h <= 0:
        return None

    h_m = h / 100.0
    bmi = w / (h_m**2)
    return round(bmi, 1)


def calculate_us_navy_body_fat(
    gender: Optional[str],
    height_cm: Optional[float | int],
    measurements: Optional[Dict[str, Any]],
) -> Optional[float]:
    """
    Estimate body fat percentage using the US Navy circumference method (metric):

    For males:
        %BF = 495 / (1.0324 - 0.19077 * log10(waist - neck) + 0.15456 * log10(height)) - 450
        Required: height_cm, neck, waist (in cm).

    For females:
        %BF = 495 / (1.29579 - 0.35004 * log10(waist + hip - neck) + 0.22100 * log10(height)) - 450
        Required: height_cm, neck, waist, hip (in cm).

    Returns estimated body fat percentage rounded to 1 decimal place,
    or None when required measurements are missing, invalid, or gender is unspecified.
    """
    if (
        not gender
        or height_cm is None
        or not measurements
        or not isinstance(measurements, dict)
    ):
        return None

    try:
        h = float(height_cm)
    except (TypeError, ValueError):
        return None

    if h <= 0:
        return None

    gender_norm = gender.strip().lower()

    def get_measure(keys: list[str]) -> Optional[float]:
        for k in keys:
            if k in measurements and measurements[k] is not None:
                try:
                    val = float(measurements[k])
                    if val > 0:
                        return val
                except (TypeError, ValueError):
                    pass
        return None

    neck = get_measure(["neck_cm", "neck"])
    waist = get_measure(["waist_cm", "waist"])

    if gender_norm == "male":
        if neck is None or waist is None:
            return None
        diff = waist - neck
        if diff <= 0:
            return None
        denom = 1.0324 - 0.19077 * math.log10(diff) + 0.15456 * math.log10(h)
        if denom <= 0:
            return None
        bf = (495.0 / denom) - 450.0
        return round(max(0.0, bf), 1)

    elif gender_norm == "female":
        hip = get_measure(["hip_cm", "hip"])
        if neck is None or waist is None or hip is None:
            return None
        combined = waist + hip - neck
        if combined <= 0:
            return None
        denom = 1.29579 - 0.35004 * math.log10(combined) + 0.22100 * math.log10(h)
        if denom <= 0:
            return None
        bf = (495.0 / denom) - 450.0
        return round(max(0.0, bf), 1)

    return None


def calculate_waist_to_hip_ratio(
    measurements: Optional[Dict[str, Any]],
) -> Optional[float]:
    """
    Calculate waist-to-hip ratio: waist_cm / hip_cm.
    Shown only when both exist, as a plain number. No high-risk flag or health verdict.
    Returns float rounded to 2 decimals or None.
    """
    if not measurements or not isinstance(measurements, dict):
        return None

    def get_val(keys: list[str]) -> Optional[float]:
        for k in keys:
            if k in measurements and measurements[k] is not None:
                try:
                    v = float(measurements[k])
                    if v > 0:
                        return v
                except (TypeError, ValueError):
                    pass
        return None

    waist = get_val(["waist_cm", "waist"])
    hip = get_val(["hip_cm", "hip"])

    if waist is None or hip is None or hip <= 0:
        return None

    return round(waist / hip, 2)


def calculate_lean_body_mass(
    weight_kg: Optional[float | int],
    body_fat_percentage: Optional[float | int],
) -> Optional[float]:
    """
    Calculate lean body mass (kg):
    LBM = weight_kg * (1 - body_fat_percentage / 100)
    Returns float rounded to 1 decimal place or None.
    """
    if weight_kg is None or body_fat_percentage is None:
        return None
    try:
        w = float(weight_kg)
        bf = float(body_fat_percentage)
    except (TypeError, ValueError):
        return None

    if w <= 0 or bf < 0 or bf > 100:
        return None

    lbm = w * (1.0 - (bf / 100.0))
    return round(max(0.0, lbm), 1)
