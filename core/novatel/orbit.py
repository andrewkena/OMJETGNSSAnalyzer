import math

GM = 3.986005e14
OMEGA_E = 7.2921151467e-5


def gps_satellite_ecef(eph, t_sec, week):
    """Computes GPS satellite ECEF position (metres) at time (week, t_sec)
    from broadcast ephemeris, per the standard ICD-GPS-200 user algorithm."""

    a = eph["a"]
    n0 = math.sqrt(GM / a ** 3)
    n = n0 + eph["deln"]

    tk = (week - eph["toe_week"]) * 604800 + (t_sec - eph["toe_sec"])
    if tk > 302400:
        tk -= 604800
    elif tk < -302400:
        tk += 604800

    m = eph["m0"] + n * tk

    e = eph["e"]
    ek = m
    for _ in range(10):
        ek = m + e * math.sin(ek)

    sin_ek, cos_ek = math.sin(ek), math.cos(ek)
    v = math.atan2(math.sqrt(1 - e * e) * sin_ek, cos_ek - e)

    phi = v + eph["omg"]
    sin2phi, cos2phi = math.sin(2 * phi), math.cos(2 * phi)

    du = eph["cuc"] * cos2phi + eph["cus"] * sin2phi
    dr = eph["crc"] * cos2phi + eph["crs"] * sin2phi
    di = eph["cic"] * cos2phi + eph["cis"] * sin2phi

    u = phi + du
    r = a * (1 - e * cos_ek) + dr
    i = eph["i0"] + di + eph["idot"] * tk

    x1 = r * math.cos(u)
    y1 = r * math.sin(u)

    omega = eph["omg0"] + (eph["omgd"] - OMEGA_E) * tk - OMEGA_E * eph["toe_sec"]
    sin_o, cos_o = math.sin(omega), math.cos(omega)
    sin_i, cos_i = math.sin(i), math.cos(i)

    x = x1 * cos_o - y1 * cos_i * sin_o
    y = x1 * sin_o + y1 * cos_i * cos_o
    z = y1 * sin_i

    return x, y, z


WGS84_A = 6378137.0
WGS84_E2 = 6.69437999014e-3


def lla_to_ecef(lat_deg, lon_deg, height_m):
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)

    sin_lat, cos_lat = math.sin(lat), math.cos(lat)
    n = WGS84_A / math.sqrt(1 - WGS84_E2 * sin_lat ** 2)

    x = (n + height_m) * cos_lat * math.cos(lon)
    y = (n + height_m) * cos_lat * math.sin(lon)
    z = (n * (1 - WGS84_E2) + height_m) * sin_lat

    return x, y, z
