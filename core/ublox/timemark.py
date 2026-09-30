import struct

from core.novatel.gps_ephemeris import gps_time_to_datetime

TIME_BASE_RECEIVER = 0
TIME_BASE_GNSS = 1
TIME_BASE_UTC = 2

# GPS-UTC leap second offset. Stable since the last leap second insertion
# on 2016-12-31; only needed when the receiver is configured to report
# TIM-TM2 in UTC time base, to bring it back onto the GPS time domain used
# everywhere else in this pipeline (gps_time_to_datetime, trajectory times).
LEAP_SECONDS_GPS_UTC = 18

SECONDS_PER_WEEK = 604800


def decode_timtm2(payload):
    """Decodes a rising-edge external event timestamp (photo trigger)."""
    if len(payload) < 28:
        return None

    flags = payload[1]
    time_base = (flags >> 3) & 0x03
    time_valid = bool(flags & 0x40)

    if not time_valid:
        return None

    wnR = struct.unpack_from("<H", payload, 4)[0]
    towMsR, towSubMsR = struct.unpack_from("<II", payload, 8)

    week = wnR
    # towSubMsR is the sub-millisecond fraction of towMsR, scaled by 2**-32 ms.
    # Sub-millisecond precision is far below the resolution needed to match
    # photos to trajectory points, so any uncertainty here is negligible.
    tow_sec = towMsR / 1000.0 + towSubMsR / (2 ** 32) / 1000.0

    if time_base == TIME_BASE_UTC:
        tow_sec += LEAP_SECONDS_GPS_UTC
        if tow_sec >= SECONDS_PER_WEEK:
            tow_sec -= SECONDS_PER_WEEK
            week += 1

    return gps_time_to_datetime(week, tow_sec), week
