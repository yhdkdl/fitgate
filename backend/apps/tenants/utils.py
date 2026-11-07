def format_gym_contact_line(phone: str = "", location: str = "") -> str:
    """
    Constructs a front-desk contact line from the gym's public phone and address (location).
    Leaves out whichever is empty; never returns empty brackets or a generic placeholder.
    Example: '(Phone: +251911223344 · Address: Bole, Addis Ababa)'
    """
    parts = []
    clean_phone = (phone or "").strip()
    clean_loc = (location or "").strip()
    if clean_phone:
        parts.append(f"Phone: {clean_phone}")
    if clean_loc:
        parts.append(f"Address: {clean_loc}")
    if not parts:
        return ""
    return f"({' · '.join(parts)})"
