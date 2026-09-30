import struct

from core.novatel.orbit import ecef_to_lla


def decode_navposecef(payload):
    if len(payload) < 20:
        return None

    iTOW, ecefX, ecefY, ecefZ, pAcc = struct.unpack_from("<IiiiI", payload, 0)

    lat, lon, height = ecef_to_lla(ecefX / 100.0, ecefY / 100.0, ecefZ / 100.0)

    # pAcc is a single combined (3D) accuracy estimate -- NAV-POSECEF has no
    # separate horizontal/vertical breakdown, so it's split isotropically.
    sigma = pAcc / 100.0 / (3 ** 0.5)

    return {
        "iTOW": iTOW,
        "lat": lat,
        "lon": lon,
        "height": height,
        "lat_sigma": sigma,
        "lon_sigma": sigma,
        "height_sigma": sigma,
    }
