SYSTEM_NAMES = {
    "G": "GPS",
    "R": "GLONASS",
    "E": "Galileo",
    "C": "BeiDou",
    "J": "QZSS",
    "S": "SBAS",
    "I": "IRNSS",
}


def read_obs_signal_types(obs_file):
    """Reads the 'SYS / # / OBS TYPES' header lines of a RINEX OBS file
    and returns {system_letter: [unique band/attribute codes]}, e.g.
    {"G": ["1C", "2W", "2X", "5I"]}."""

    types_by_system = {}
    current_system = None

    with open(obs_file, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            label = line[60:].strip()

            if label == "END OF HEADER":
                break

            if label != "SYS / # / OBS TYPES":
                continue

            system_char = line[0:1].strip()
            if system_char:
                current_system = system_char
                types_by_system.setdefault(current_system, [])
                codes_field = line[6:60]
            else:
                codes_field = line[6:60]

            if current_system is None:
                continue

            codes = codes_field.split()
            for code in codes:
                if len(code) >= 2:
                    band_attr = code[1:]
                    if band_attr not in types_by_system[current_system]:
                        types_by_system[current_system].append(band_attr)

    return types_by_system


def system_name(system_char):
    return SYSTEM_NAMES.get(system_char, system_char)
