"""Constants for group classes app."""

CLASS_TITLE_YOGA = "yoga"
CLASS_TITLE_ZUMBA = "zumba"
CLASS_TITLE_SPINNING = "spinning"
CLASS_TITLE_BOXING = "boxing"
CLASS_TITLE_AEROBICS = "aerobics"
CLASS_TITLE_CROSSFIT = "crossfit"
CLASS_TITLE_STRENGTH_CIRCUIT = "strength_circuit"
CLASS_TITLE_STRETCHING_MOBILITY = "stretching_mobility"
CLASS_TITLE_OTHER = "other"

CLASS_TITLE_CHOICES = [
    (CLASS_TITLE_YOGA, "Yoga"),
    (CLASS_TITLE_ZUMBA, "Zumba"),
    (CLASS_TITLE_SPINNING, "Spinning"),
    (CLASS_TITLE_BOXING, "Boxing"),
    (CLASS_TITLE_AEROBICS, "Aerobics"),
    (CLASS_TITLE_CROSSFIT, "CrossFit"),
    (CLASS_TITLE_STRENGTH_CIRCUIT, "Strength Circuit"),
    (CLASS_TITLE_STRETCHING_MOBILITY, "Stretching & Mobility"),
    (CLASS_TITLE_OTHER, "Other"),
]

CLASS_DURATION_CHOICES = [
    (30, "30 minutes"),
    (45, "45 minutes"),
    (60, "60 minutes"),
    (90, "90 minutes"),
]

SESSION_STATUS_SCHEDULED = "scheduled"
SESSION_STATUS_CANCELLED = "cancelled"

SESSION_STATUS_CHOICES = [
    (SESSION_STATUS_SCHEDULED, "Scheduled"),
    (SESSION_STATUS_CANCELLED, "Cancelled"),
]

BOOKING_STATUS_BOOKED = "booked"
BOOKING_STATUS_CANCELLED = "cancelled"

BOOKING_STATUS_CHOICES = [
    (BOOKING_STATUS_BOOKED, "Booked"),
    (BOOKING_STATUS_CANCELLED, "Cancelled"),
]
