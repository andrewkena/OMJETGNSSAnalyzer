GPS_OBS_TYPES = ["C1C", "L1C", "D1C", "S1C", "C2W", "L2W", "D2W", "S2W",
                 "C2X", "L2X", "D2X", "S2X", "C5I", "L5I", "D5I", "S5I"]


def _format_value(value):
    if value is None:
        return " " * 16
    return f"{value:14.3f}  "


def _obs_types_lines():
    lines = []
    remaining = list(GPS_OBS_TYPES)
    first = True
    while remaining or first:
        chunk, remaining = remaining[:13], remaining[13:]
        prefix = f"G{len(GPS_OBS_TYPES):5d} " if first else " " * 6
        codes = "".join(f"{c:>4}" for c in chunk)
        lines.append(f"{prefix}{codes}".ljust(60) + "SYS / # / OBS TYPES\n")
        first = False
        if not remaining:
            break
    return lines


def write_rinex_obs(path, epochs):
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"{3.04:9.2f}{'':11}OBSERVATION DATA    M: Mixed            RINEX VERSION / TYPE\n")
        f.write(f"{'OMJET GNSS Analyzer':<20}{'':20}{'':20}PGM / RUN BY / DATE \n")
        for line in _obs_types_lines():
            f.write(line)
        f.write("                                                            END OF HEADER       \n")

        for epoch_time, records in epochs:
            by_prn = {}
            for r in records:
                by_prn.setdefault(r["prn"], {})[r["code"]] = r

            f.write(
                f"> {epoch_time.year:4d} {epoch_time.month:2d} {epoch_time.day:2d} "
                f"{epoch_time.hour:2d} {epoch_time.minute:2d}"
                f"{epoch_time.second + epoch_time.microsecond / 1e6:11.7f}  0"
                f"{len(by_prn):3d}\n"
            )

            for prn in sorted(by_prn):
                line = f"G{prn:02d}"
                channels = by_prn[prn]
                for code in ("1C", "2W", "2X", "5I"):
                    rec = channels.get(code)
                    if rec is None:
                        line += " " * 16 * 4
                        continue
                    line += _format_value(rec["psr"])
                    line += _format_value(rec["carrier_phase"])
                    line += _format_value(rec["doppler"])
                    line += _format_value(rec["cn0"])
                f.write(line.rstrip() + "\n")
