import math
from datetime import datetime, timedelta

SC2RAD = math.pi

P2_5 = 2.0 ** -5
P2_19 = 2.0 ** -19
P2_29 = 2.0 ** -29
P2_31 = 2.0 ** -31
P2_33 = 2.0 ** -33
P2_43 = 2.0 ** -43
P2_55 = 2.0 ** -55

GPS_EPOCH = datetime(1980, 1, 6)


def getbitu(buff, pos, length):
    bits = 0
    for i in range(pos, pos + length):
        bits = (bits << 1) | ((buff[i // 8] >> (7 - i % 8)) & 1)
    return bits


def getbits(buff, pos, length):
    bits = getbitu(buff, pos, length)
    if length <= 0:
        return bits
    if length >= 32:
        return bits - (1 << 32) if bits >= (1 << 31) else bits
    if not (bits & (1 << (length - 1))):
        return bits
    return bits - (1 << length)


def gps_time_to_datetime(week, tow_sec):
    return GPS_EPOCH + timedelta(weeks=week, seconds=tow_sec)


def _adjust_week(week10, ref_week):
    cycle = round((ref_week - week10) / 1024.0)
    return week10 + cycle * 1024


def _decode_subfrm1(buff):
    i = 48
    week10 = getbitu(buff, i, 10)
    i += 10
    code = getbitu(buff, i, 2)
    i += 2
    sva = getbitu(buff, i, 4)
    i += 4
    svh = getbitu(buff, i, 6)
    i += 6
    iodc0 = getbitu(buff, i, 2)
    i += 2 + 1 + 87
    tgd = getbits(buff, i, 8)
    i += 8
    iodc1 = getbitu(buff, i, 8)
    i += 8
    toc = getbitu(buff, i, 16) * 16.0
    i += 16
    f2 = getbits(buff, i, 8) * P2_55
    i += 8
    f1 = getbits(buff, i, 16) * P2_43
    i += 16
    f0 = getbits(buff, i, 22) * P2_31

    return {
        "week10": week10,
        "code": code,
        "sva": sva,
        "svh": svh,
        "iodc": (iodc0 << 8) + iodc1,
        "toc": toc,
        "f2": f2,
        "f1": f1,
        "f0": f0,
        "tgd": 0.0 if tgd == -128 else tgd * P2_31,
    }


def _decode_subfrm2(buff):
    i = 48
    iode = getbitu(buff, i, 8)
    i += 8
    crs = getbits(buff, i, 16) * P2_5
    i += 16
    deln = getbits(buff, i, 16) * P2_43 * SC2RAD
    i += 16
    m0 = getbits(buff, i, 32) * P2_31 * SC2RAD
    i += 32
    cuc = getbits(buff, i, 16) * P2_29
    i += 16
    e = getbitu(buff, i, 32) * P2_33
    i += 32
    cus = getbits(buff, i, 16) * P2_29
    i += 16
    sqrt_a = getbitu(buff, i, 32) * P2_19
    i += 32
    toes = getbitu(buff, i, 16) * 16.0

    return {
        "iode": iode,
        "crs": crs,
        "deln": deln,
        "m0": m0,
        "cuc": cuc,
        "e": e,
        "cus": cus,
        "a": sqrt_a * sqrt_a,
        "toes": toes,
    }


def _decode_subfrm3(buff):
    i = 48
    cic = getbits(buff, i, 16) * P2_29
    i += 16
    omg0 = getbits(buff, i, 32) * P2_31 * SC2RAD
    i += 32
    cis = getbits(buff, i, 16) * P2_29
    i += 16
    i0 = getbits(buff, i, 32) * P2_31 * SC2RAD
    i += 32
    crc = getbits(buff, i, 16) * P2_5
    i += 16
    omg = getbits(buff, i, 32) * P2_31 * SC2RAD
    i += 32
    omgd = getbits(buff, i, 24) * P2_43 * SC2RAD
    i += 24
    iode = getbitu(buff, i, 8)
    i += 8
    idot = getbits(buff, i, 14) * P2_43 * SC2RAD

    return {
        "iode": iode,
        "cic": cic,
        "omg0": omg0,
        "cis": cis,
        "i0": i0,
        "crc": crc,
        "omg": omg,
        "omgd": omgd,
        "idot": idot,
    }


def decode_rawephem(body, header_week):
    prn = int.from_bytes(body[0:4], "little")
    ref_week = int.from_bytes(body[4:8], "little")
    sub1 = body[12:42]
    sub2 = body[42:72]
    sub3 = body[72:102]

    s1 = _decode_subfrm1(sub1)
    s2 = _decode_subfrm2(sub2)
    s3 = _decode_subfrm3(sub3)

    if s2["iode"] != s3["iode"]:
        return None

    week = _adjust_week(s1["week10"], ref_week or header_week)

    toc_sec = s1["toc"]
    toe_sec = s2["toes"]

    toe_week = week
    if toe_sec - toc_sec > 302400.0:
        toe_week = week - 1
    elif toe_sec - toc_sec < -302400.0:
        toe_week = week + 1

    return {
        "prn": prn,
        "week": week,
        "iode": s2["iode"],
        "iodc": s1["iodc"],
        "svh": s1["svh"],
        "sva": s1["sva"],
        "code": s1["code"],
        "tgd": s1["tgd"],
        "toc": gps_time_to_datetime(week, toc_sec),
        "toc_sec": toc_sec,
        "f0": s1["f0"],
        "f1": s1["f1"],
        "f2": s1["f2"],
        "crs": s2["crs"],
        "deln": s2["deln"],
        "m0": s2["m0"],
        "cuc": s2["cuc"],
        "e": s2["e"],
        "cus": s2["cus"],
        "a": s2["a"],
        "toe": gps_time_to_datetime(toe_week, toe_sec),
        "toe_sec": toe_sec,
        "toe_week": toe_week,
        "cic": s3["cic"],
        "omg0": s3["omg0"],
        "cis": s3["cis"],
        "i0": s3["i0"],
        "crc": s3["crc"],
        "omg": s3["omg"],
        "omgd": s3["omgd"],
        "idot": s3["idot"],
    }
