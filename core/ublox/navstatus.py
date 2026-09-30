import struct

from core.ublox.pos_type import classify_pos_type


def decode_navstatus(payload):
    if len(payload) < 16:
        return None

    iTOW = struct.unpack_from("<I", payload, 0)[0]
    gps_fix = payload[4]
    flags = payload[5]
    flags2 = payload[7]

    diff_soln = bool(flags & 0x02)
    carr_soln = (flags2 >> 6) & 0x03

    return {
        "iTOW": iTOW,
        "num_svs": None,
        "pos_type": classify_pos_type(gps_fix, diff_soln, carr_soln),
    }
