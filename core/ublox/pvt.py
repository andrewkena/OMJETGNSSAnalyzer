import struct
import math
from datetime import datetime, timedelta

from core.ublox.pos_type import classify_pos_type


def decode_navpvt(payload):
    if len(payload) < 92:
        return None

    iTOW = struct.unpack_from("<I", payload, 0)[0]
    year, month, day, hour, minute, second = struct.unpack_from("<HBBBBB", payload, 4)
    valid = payload[11]
    nano = struct.unpack_from("<i", payload, 16)[0]
    fix_type = payload[20]
    flags = payload[21]
    numSV = payload[23]
    lon, lat, height, hMSL = struct.unpack_from("<iiii", payload, 24)
    hAcc, vAcc = struct.unpack_from("<II", payload, 40)
    pDOP = struct.unpack_from("<H", payload, 76)[0]

    diff_soln = bool(flags & 0x02)
    carr_soln = (flags >> 6) & 0x03

    utc_dt = None
    if valid & 0x01 and valid & 0x02:
        try:
            utc_dt = datetime(year, month, day, hour, minute, second) + timedelta(
                microseconds=nano / 1000.0
            )
        except ValueError:
            utc_dt = None

    height_sigma = vAcc / 1000.0
    horiz_sigma = hAcc / 1000.0 / math.sqrt(2)

    return {
        "iTOW": iTOW,
        "utc_datetime": utc_dt,
        "lat": lat * 1e-7,
        "lon": lon * 1e-7,
        "height": hMSL / 1000.0,
        "lat_sigma": horiz_sigma,
        "lon_sigma": horiz_sigma,
        "height_sigma": height_sigma,
        "pos_type": classify_pos_type(fix_type, diff_soln, carr_soln),
        "num_svs": numSV,
        "num_soln_svs": numSV,
        "pdop": pDOP * 0.01,
    }
