import struct
import math
from datetime import datetime, timedelta

FIX_NONE = 0
FIX_DEAD_RECKONING = 1
FIX_2D = 2
FIX_3D = 3
FIX_GNSS_DR = 4
FIX_TIME_ONLY = 5


def _pos_type(fix_type, diff_soln, carr_soln):
    if fix_type == FIX_NONE:
        return "NONE"
    if fix_type == FIX_DEAD_RECKONING:
        return "DEAD_RECKONING"
    if fix_type == FIX_2D:
        return "TYPE_2D"
    if fix_type == FIX_TIME_ONLY:
        return "TIME_ONLY"

    # fix_type is 3D or GNSS+dead-reckoning -- carrSoln tells us the RTK
    # ambiguity state, mirroring the Novatel BESTPOS labels so reports read
    # the same regardless of receiver brand.
    if carr_soln == 2:
        return "NARROW_INT"
    if carr_soln == 1:
        return "NARROW_FLOAT"
    return "PSRDIFF" if diff_soln else "SINGLE"


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
        "pos_type": _pos_type(fix_type, diff_soln, carr_soln),
        "num_svs": numSV,
        "num_soln_svs": numSV,
        "pdop": pDOP * 0.01,
    }
