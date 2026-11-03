"""
Equipment choices and constants shared between rules engine, API, and frontend.
"""

EQUIPMENT_CATEGORY_CHOICES = [
    ("barbell", "Barbell & Plates"),
    ("dumbbells", "Dumbbells"),
    ("cable_machine", "Cable Machine"),
    ("resistance_bands", "Resistance Bands"),
    ("kettlebells", "Kettlebells"),
    ("pull_up_bar", "Pull-up Bar"),
    ("bench", "Bench"),
    ("leg_press", "Leg Press"),
    ("squat_rack", "Squat Rack"),
    ("cardio_machines", "Cardio Machines"),
    ("bodyweight", "Bodyweight / Calisthenics Station"),
    ("other", "Other"),
]

EQUIPMENT_CATEGORY_CODES = {code for code, _ in EQUIPMENT_CATEGORY_CHOICES}

CONDITION_GOOD = "good"
CONDITION_NEEDS_MAINTENANCE = "needs_maintenance"
CONDITION_UNDER_MAINTENANCE = "under_maintenance"
CONDITION_OUT_OF_SERVICE = "out_of_service"

CONDITION_CHOICES = [
    (CONDITION_GOOD, "Good"),
    (CONDITION_NEEDS_MAINTENANCE, "Needs Maintenance"),
    (CONDITION_UNDER_MAINTENANCE, "Under Maintenance"),
    (CONDITION_OUT_OF_SERVICE, "Out of Service"),
]

CONDITION_CODES = {code for code, _ in CONDITION_CHOICES}

ISSUE_REASON_BROKEN = "broken"
ISSUE_REASON_WORN_OUT = "worn_out"
ISSUE_REASON_NOISY_UNSAFE = "noisy_unsafe"
ISSUE_REASON_OTHER = "other"

ISSUE_REASON_CHOICES = [
    (ISSUE_REASON_BROKEN, "Broken"),
    (ISSUE_REASON_WORN_OUT, "Worn out"),
    (ISSUE_REASON_NOISY_UNSAFE, "Noisy or unsafe"),
    (ISSUE_REASON_OTHER, "Other"),
]

ISSUE_REASON_CODES = {code for code, _ in ISSUE_REASON_CHOICES}
