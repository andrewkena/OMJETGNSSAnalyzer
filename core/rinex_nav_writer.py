def _num(value):
    return f"{value:19.12e}".replace("e", "E")


def write_rinex_nav(path, ephemerides):
    by_key = {}
    for eph in ephemerides:
        by_key[(eph["prn"], eph["iode"])] = eph

    ordered = sorted(by_key.values(), key=lambda e: (e["prn"], e["toe"]))

    with open(path, "w", encoding="utf-8") as f:
        f.write(f"{3.04:9.2f}           N: GNSS NAV DATA    G: GPS              RINEX VERSION / TYPE\n")
        f.write(f"{'OMJET GNSS Analyzer':<20}{'':20}{'':20}PGM / RUN BY / DATE \n")
        f.write("                                                            END OF HEADER       \n")

        for e in ordered:
            t = e["toc"]
            f.write(
                f"G{e['prn']:02d} {t.year:4d} {t.month:2d} {t.day:2d} "
                f"{t.hour:2d} {t.minute:2d} {t.second:2d}"
                f"{_num(e['f0'])}{_num(e['f1'])}{_num(e['f2'])}\n"
            )
            f.write(f"    {_num(float(e['iode']))}{_num(e['crs'])}{_num(e['deln'])}{_num(e['m0'])}\n")
            f.write(f"    {_num(e['cuc'])}{_num(e['e'])}{_num(e['cus'])}{_num(e['a'] ** 0.5)}\n")
            f.write(f"    {_num(e['toe_sec'])}{_num(e['cic'])}{_num(e['omg0'])}{_num(e['cis'])}\n")
            f.write(f"    {_num(e['i0'])}{_num(e['crc'])}{_num(e['omg'])}{_num(e['omgd'])}\n")
            f.write(f"    {_num(e['idot'])}{_num(float(e['code']))}{_num(float(e['toe_week']))}{_num(0.0)}\n")
            f.write(f"    {_num(float(e['sva']))}{_num(float(e['svh']))}{_num(e['tgd'])}{_num(float(e['iodc'] & 0xFF))}\n")
            f.write(f"    {_num(e['toe_sec'])}{_num(4.0)}{_num(0.0)}{_num(0.0)}\n")
