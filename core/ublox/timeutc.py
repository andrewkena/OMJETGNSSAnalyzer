import struct
from datetime import datetime, timedelta


def decode_navtimeutc(payload):
    if len(payload) < 20:
        return None

    nano = struct.unpack_from("<i", payload, 8)[0]
    year, month, day, hour, minute, second = struct.unpack_from("<HBBBBB", payload, 12)
    valid = payload[19]

    if not (valid & 0x01 and valid & 0x04):  # validTOW, validUTC
        return None

    try:
        return datetime(year, month, day, hour, minute, second) + timedelta(
            microseconds=nano / 1000.0
        )
    except ValueError:
        return None
