"""
Shared constants and choice lists for Fitness Profiles, AI Plan Focus, and Plan Review.
The server is authoritative for these definitions.
"""

HEALTH_LIMITATION_CHOICES = [
    ("none", "None"),
    ("lower_back", "Lower back"),
    ("knee", "Knee"),
    ("shoulder", "Shoulder"),
    ("neck", "Neck"),
    ("hip", "Hip"),
    ("ankle_foot", "Ankle or foot"),
    ("wrist_elbow", "Wrist or elbow"),
    ("high_blood_pressure", "High blood pressure"),
    ("heart_condition", "Heart condition"),
    ("diabetes", "Diabetes"),
    ("asthma", "Asthma"),
    ("pregnancy_postpartum", "Pregnancy or postpartum"),
    ("recent_surgery", "Recent surgery"),
    ("other", "Other"),
]

HEALTH_LIMITATION_CODES = {code for code, _ in HEALTH_LIMITATION_CHOICES}

# Conditions requiring doctor confirmation & extra careful plan review
MEDICAL_CAUTION_CODES = {
    "heart_condition",
    "high_blood_pressure",
    "diabetes",
    "asthma",
    "pregnancy_postpartum",
    "recent_surgery",
}

EQUIPMENT_ACCESS_CHOICES = [
    ("full_gym", "Full gym equipment"),
    ("free_weights", "Free weights (dumbbells and barbells)"),
    ("machines", "Machines"),
    ("cables", "Cables"),
    ("kettlebells", "Kettlebells"),
    ("resistance_bands", "Resistance bands"),
    ("cardio_machines", "Cardio machines"),
    ("bodyweight_only", "Bodyweight only"),
    ("other", "Other"),
]

EQUIPMENT_ACCESS_CODES = {code for code, _ in EQUIPMENT_ACCESS_CHOICES}

DIETARY_NOTE_CHOICES = [
    ("none", "No restrictions"),
    ("vegetarian", "Vegetarian"),
    ("vegan", "Vegan"),
    ("no_dairy", "No dairy"),
    ("no_eggs", "No eggs"),
    ("no_nuts", "No nuts"),
    ("no_fish", "No fish"),
    ("no_gluten", "No gluten"),
    ("halal", "Halal"),
    ("orthodox_fasting", "Orthodox fasting"),
    ("ramadan_fasting", "Ramadan fasting"),
    ("other", "Other"),
]

DIETARY_NOTE_CODES = {code for code, _ in DIETARY_NOTE_CHOICES}

WEEKLY_FOCUS_CHOICES = [
    ("no_focus", "No special focus"),
    ("legs", "Legs"),
    ("upper_body", "Upper body"),
    ("core", "Core"),
    ("cardio", "Cardio"),
    ("mobility", "Mobility"),
    ("other", "Other"),
]

WEEKLY_FOCUS_CODES = {code for code, _ in WEEKLY_FOCUS_CHOICES}

PLAN_REJECTION_REASONS = [
    ("too_hard", "Too hard"),
    ("too_easy", "Too easy"),
    ("exercises_not_suitable", "Exercises not suitable for member limits"),
    ("equipment_not_available", "Equipment not available"),
    ("nutrition_not_suitable", "Nutrition not suitable"),
    ("other", "Other"),
]

PLAN_REJECTION_CODES = {code for code, _ in PLAN_REJECTION_REASONS}
