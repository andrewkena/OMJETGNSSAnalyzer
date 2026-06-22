import numpy as np

from core.novatel.reader import iter_messages
from core.novatel.rangecmp import decode_rangecmpb
from core.novatel.gps_ephemeris import gps_time_to_datetime
from core.novatel.orbit import gps_satellite_ecef, lla_to_ecef

MSG_ID_RANGECMPB = 140
EPHEMERIS_VALIDITY_SEC = 2 * 3600


def _build_ephemeris_index(ephemerides):
    by_prn = {}
    for eph in ephemerides:
        by_prn.setdefault(eph["prn"], []).append(eph)
    for prn in by_prn:
        by_prn[prn].sort(key=lambda e: e["toe"])
    return by_prn


def _closest_ephemeris(by_prn, prn, t):
    candidates = by_prn.get(prn)
    if not candidates:
        return None
    best = min(candidates, key=lambda e: abs((e["toe"] - t).total_seconds()))
    if abs((best["toe"] - t).total_seconds()) > EPHEMERIS_VALIDITY_SEC:
        return None
    return best


def _closest_trajectory_point(trajectory_points, t):
    if not trajectory_points:
        return None
    return min(trajectory_points, key=lambda p: abs((p["time"] - t).total_seconds()))


def _pdop_from_positions(rcv_ecef, sat_positions):
    rx, ry, rz = rcv_ecef
    rows = []
    for sx, sy, sz in sat_positions:
        dx, dy, dz = sx - rx, sy - ry, sz - rz
        rng = (dx * dx + dy * dy + dz * dz) ** 0.5
        rows.append([-dx / rng, -dy / rng, -dz / rng, 1.0])

    g = np.array(rows)
    try:
        q = np.linalg.inv(g.T @ g)
    except np.linalg.LinAlgError:
        return None

    return float(np.sqrt(q[0, 0] + q[1, 1] + q[2, 2]))


def compute_pdop_series(cnb_file, ephemerides, trajectory_points, sample_every=50):
    by_prn = _build_ephemeris_index(ephemerides)
    series = []

    count = 0
    for msg in iter_messages(cnb_file):
        if msg.msg_id != MSG_ID_RANGECMPB:
            continue

        count += 1
        if count % sample_every != 0:
            continue

        records = decode_rangecmpb(msg.body)
        prns = sorted({r["prn"] for r in records if r["code"] == "1C"})
        if len(prns) < 4:
            continue

        t = gps_time_to_datetime(msg.week, msg.tow_sec)

        rcv_fix = _closest_trajectory_point(trajectory_points, t)
        if rcv_fix is None:
            continue
        rcv_ecef = lla_to_ecef(rcv_fix["lat"], rcv_fix["lon"], rcv_fix["height"])

        sat_positions = []
        for prn in prns:
            eph = _closest_ephemeris(by_prn, prn, t)
            if eph is None:
                continue
            sat_positions.append(gps_satellite_ecef(eph, msg.tow_sec, msg.week))

        if len(sat_positions) < 4:
            continue

        pdop = _pdop_from_positions(rcv_ecef, sat_positions)
        if pdop is not None:
            series.append({"time": t, "pdop": pdop, "num_sats": len(sat_positions)})

    return series
