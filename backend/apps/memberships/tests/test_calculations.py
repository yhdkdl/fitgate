"""
Unit tests for body composition calculations (BMI and US Navy circumference method).
"""

from apps.memberships.calculations import calculate_bmi, calculate_us_navy_body_fat


class TestBMICalculation:
    """Tests for BMI calculation."""

    def test_normal_bmi(self):
        # 75 kg, 180 cm -> 75 / (1.8 ^ 2) = 23.148... -> 23.1
        bmi = calculate_bmi(75, 180)
        assert bmi == 23.1

    def test_overweight_bmi(self):
        # 95 kg, 175 cm -> 95 / (1.75 ^ 2) = 31.02... -> 31.0
        bmi = calculate_bmi(95, 175)
        assert bmi == 31.0

    def test_missing_or_zero_values(self):
        assert calculate_bmi(None, 180) is None
        assert calculate_bmi(75, None) is None
        assert calculate_bmi(0, 180) is None
        assert calculate_bmi(75, 0) is None
        assert calculate_bmi(-5, 180) is None
        assert calculate_bmi(75, -180) is None

    def test_invalid_types(self):
        assert calculate_bmi("invalid", 180) is None
        assert calculate_bmi(75, "invalid") is None


class TestUSNavyBodyFatCalculation:
    """Tests for US Navy circumference body fat percentage calculation."""

    def test_male_normal_body_fat(self):
        # Male: height = 180 cm, waist = 85 cm, neck = 40 cm
        # waist - neck = 45 cm
        # Expected %BF ~ 14.5%
        measurements = {"neck_cm": 40, "waist_cm": 85}
        bf = calculate_us_navy_body_fat("male", 180, measurements)
        assert bf is not None
        assert 14.0 <= bf <= 15.0
        assert bf == 14.5

    def test_male_supports_alternative_key_names(self):
        measurements = {"neck": 40, "waist": 85}
        bf = calculate_us_navy_body_fat("Male", 180, measurements)
        assert bf == 14.5

    def test_male_missing_waist_or_neck_returns_none(self):
        assert calculate_us_navy_body_fat("male", 180, {"neck_cm": 40}) is None
        assert calculate_us_navy_body_fat("male", 180, {"waist_cm": 85}) is None
        assert calculate_us_navy_body_fat("male", 180, {}) is None

    def test_male_waist_less_than_or_equal_neck_returns_none(self):
        # Physically impossible / invalid measurements
        assert (
            calculate_us_navy_body_fat("male", 180, {"neck_cm": 40, "waist_cm": 40})
            is None
        )
        assert (
            calculate_us_navy_body_fat("male", 180, {"neck_cm": 45, "waist_cm": 40})
            is None
        )

    def test_female_normal_body_fat(self):
        # Female: height = 165 cm, neck = 33 cm, waist = 70 cm, hip = 95 cm
        # waist + hip - neck = 70 + 95 - 33 = 132 cm
        # Expected %BF ~ 24.3%
        measurements = {"neck_cm": 33, "waist_cm": 70, "hip_cm": 95}
        bf = calculate_us_navy_body_fat("female", 165, measurements)
        assert bf is not None
        assert 24.0 <= bf <= 25.0
        assert bf == 24.3

    def test_female_missing_hip_returns_none(self):
        # Females require hip measurement
        measurements = {"neck_cm": 33, "waist_cm": 70}
        assert calculate_us_navy_body_fat("female", 165, measurements) is None

    def test_female_missing_neck_or_waist_returns_none(self):
        assert (
            calculate_us_navy_body_fat("female", 165, {"neck_cm": 33, "hip_cm": 95})
            is None
        )
        assert (
            calculate_us_navy_body_fat("female", 165, {"waist_cm": 70, "hip_cm": 95})
            is None
        )

    def test_female_invalid_circumferences_returns_none(self):
        # waist + hip <= neck
        assert (
            calculate_us_navy_body_fat(
                "female", 165, {"neck_cm": 150, "waist_cm": 70, "hip_cm": 70}
            )
            is None
        )

    def test_unsupported_or_missing_gender_returns_none(self):
        measurements = {"neck_cm": 40, "waist_cm": 85, "hip_cm": 95}
        assert calculate_us_navy_body_fat("other", 180, measurements) is None
        assert (
            calculate_us_navy_body_fat("prefer_not_to_say", 180, measurements) is None
        )
        assert calculate_us_navy_body_fat(None, 180, measurements) is None
        assert calculate_us_navy_body_fat("", 180, measurements) is None

    def test_invalid_height_or_measurements_returns_none(self):
        assert (
            calculate_us_navy_body_fat("male", None, {"neck_cm": 40, "waist_cm": 85})
            is None
        )
        assert (
            calculate_us_navy_body_fat("male", 0, {"neck_cm": 40, "waist_cm": 85})
            is None
        )
        assert (
            calculate_us_navy_body_fat("male", -180, {"neck_cm": 40, "waist_cm": 85})
            is None
        )
        assert calculate_us_navy_body_fat("male", 180, None) is None
        assert calculate_us_navy_body_fat("male", 180, "invalid") is None
