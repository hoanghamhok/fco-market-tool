"""Manual squad salary calculator; independent of game/OCR data."""

import re

# Position, horizontal fraction, vertical fraction; matching the reference squads.
FORMATIONS = {
    "4-3-3": (
        ("ST", 0.50, 0.10),
        ("LW", 0.21, 0.17),
        ("RW", 0.79, 0.17),
        ("CM", 0.50, 0.31),
        ("LDM", 0.34, 0.42),
        ("RDM", 0.66, 0.42),
        ("LB", 0.12, 0.64),
        ("LCB", 0.34, 0.68),
        ("RCB", 0.66, 0.68),
        ("RB", 0.88, 0.64),
        ("GK", 0.50, 0.88),
    ),
    "4-1-4-1": (
        ("ST", 0.50, 0.10),
        ("LM", 0.16, 0.29),
        ("RM", 0.84, 0.29),
        ("LCM", 0.38, 0.35),
        ("RCM", 0.62, 0.35),
        ("CDM", 0.50, 0.52),
        ("LB", 0.12, 0.65),
        ("LCB", 0.34, 0.69),
        ("RCB", 0.66, 0.69),
        ("RB", 0.88, 0.65),
        ("GK", 0.50, 0.88),
    ),
}


def parse_salary(value):
    text = str(value).strip()
    if not text:
        return 0
    if not re.fullmatch(r"[0-9]+", text):
        raise ValueError("Lương phải là số nguyên không âm.")
    return int(text)


def total_salary(values):
    return sum(parse_salary(value) for value in values)


def clean_settings(stored):
    """Recover each valid saved input independently from a damaged settings file."""
    result = {
        "formation": "4-3-3",
        "squads": {
            key: {position: "" for position, _, _ in positions}
            for key, positions in FORMATIONS.items()
        },
    }
    if not isinstance(stored, dict):
        return result
    if isinstance(stored.get("formation"), str) and stored["formation"] in FORMATIONS:
        result["formation"] = stored["formation"]
    squads = stored.get("squads", {})
    if not isinstance(squads, dict):
        return result
    for formation, positions in result["squads"].items():
        values = squads.get(formation, {})
        if not isinstance(values, dict):
            continue
        for position in positions:
            value = values.get(position, "")
            try:
                parse_salary(value)
                positions[position] = str(value).strip()
            except (ValueError, TypeError):
                pass
    return result
