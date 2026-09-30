import struct
import math


def decode_navposllh(payload):
    if len(payload) < 28:
        return None

    iTOW = struct.unpack_from("<I", payload, 0)[0]
    lon, lat, height, hMSL = struct.unpack_from("<iiii", payload, 4)
    hAcc, vAcc = struct.unpack_from("<II", payload, 20)

    height_sigma = vAcc / 1000.0
    horiz_sigma = hAcc / 1000.0 / math.sqrt(2)

    return {
        "iTOW": iTOW,
        "lat": lat * 1e-7,
        "lon": lon * 1e-7,
        "height": hMSL / 1000.0,
        "lat_sigma": horiz_sigma,
        "lon_sigma": horiz_sigma,
        "height_sigma": height_sigma,
    }
