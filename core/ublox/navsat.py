import struct

# UBX gnssId -> RINEX-style system letter, matching the constellations
# already tracked by core/satellite_analysis.py (G/R/E/C only).
GNSS_ID_LETTER = {
    0: "G",   # GPS
    2: "E",   # Galileo
    3: "C",   # BeiDou
    6: "R",   # GLONASS
}


def decode_navsat(payload):
    if len(payload) < 8:
        return None

    iTOW = struct.unpack_from("<I", payload, 0)[0]
    num_svs = payload[5]

    satellites = []
    offset = 8
    for _ in range(num_svs):
        if offset + 12 > len(payload):
            break

        gnss_id = payload[offset]
        sv_id = payload[offset + 1]
        flags = struct.unpack_from("<I", payload, offset + 8)[0]
        used = bool(flags & 0x08)

        satellites.append({"gnssId": gnss_id, "svId": sv_id, "used": used})
        offset += 12

    return iTOW, satellites
