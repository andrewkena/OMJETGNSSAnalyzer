"""Android (Chaquopy) entry point.

Mirrors core/pipeline.py's logic but skips everything that depends on
matplotlib/reportlab (plots, PDF report) -- those aren't wired up for the
mobile build yet. Returns a plain dict (str/int/float/None only) so it
bridges cleanly to Kotlin through Chaquopy.
"""

import math

from core.rinex_time_reader import RinexTimeReader
from core.time_analysis import TimeAnalysis
from core.satellite_analysis import SatelliteAnalysis
from core.timemark_analysis import TimemarkAnalysis
from core.photo_quality import PhotoQuality
from core.photo_satellite_report import PhotoSatelliteReport
from core.mission_quality import MissionQuality
from core.obs_header_reader import read_obs_signal_types, system_name
from core.pdop import compute_pdop_series

from core.novatel.reader import iter_messages
from core.novatel.bestpos import decode_bestposb
from core.novatel.gps_ephemeris import gps_time_to_datetime, decode_rawephem

MSG_ID_BESTPOS = 42
MSG_ID_RAWEPHEM = 41


def _haversine_m(lat1, lon1, lat2, lon2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def _extract_trajectory(cnb_path):
    points = []
    for msg in iter_messages(cnb_path):
        if msg.msg_id != MSG_ID_BESTPOS:
            continue
        fix = decode_bestposb(msg.body)
        if fix is not None:
            fix["time"] = gps_time_to_datetime(msg.week, msg.tow_sec)
            points.append(fix)

    distance_m = sum(
        _haversine_m(
            points[i]["lat"], points[i]["lon"],
            points[i + 1]["lat"], points[i + 1]["lon"]
        )
        for i in range(len(points) - 1)
    )
    return points, distance_m


def _extract_ephemerides(cnb_path):
    ephemerides = []
    for msg in iter_messages(cnb_path):
        if msg.msg_id != MSG_ID_RAWEPHEM:
            continue
        eph = decode_rawephem(msg.body, msg.week)
        if eph is not None:
            ephemerides.append(eph)
    return ephemerides


def analyze(cnb_path, obs_path, csv_out_path):
    trajectory_points, distance_m = _extract_trajectory(cnb_path)
    ephemerides = _extract_ephemerides(cnb_path)
    pdop_series = compute_pdop_series(cnb_path, ephemerides, trajectory_points)

    tm = TimemarkAnalysis(obs_path).analyze()
    times = RinexTimeReader(obs_path).get_times()
    time_result = TimeAnalysis(times).get_summary()
    sat_result = SatelliteAnalysis(obs_path).analyze()

    signal_types = read_obs_signal_types(obs_path)
    usage = {
        "G": sat_result["gps_avg"], "R": sat_result["glo_avg"],
        "E": sat_result["gal_avg"], "C": sat_result["bds_avg"],
    }
    usage = {k: v for k, v in usage.items() if k in signal_types}
    most_used = system_name(max(usage, key=usage.get)) if usage else None
    least_used = system_name(min(usage, key=usage.get)) if usage else None

    quality = PhotoQuality(tm["timemarks"]).analyze()

    matched_fixes = []
    for t in tm["timemarks"]:
        if trajectory_points:
            closest = min(trajectory_points, key=lambda p: abs((p["time"] - t).total_seconds()))
            matched_fixes.append(closest)

    photo_result = PhotoSatelliteReport(
        tm["timemarks"], sat_result["epoch_times"], sat_result["epoch_sat_counts"],
        csv_out_path, fixes=matched_fixes,
    ).analyze()

    report = photo_result["report"]
    good_count = photo_result["good"]
    normal_count = photo_result["normal"]
    low_count = photo_result["low"]
    good_percent = (good_count / len(report)) * 100 if report else 0.0

    if sat_result["avg_satellites"] >= 20:
        gnss_quality = "EXCELLENT"
    elif sat_result["avg_satellites"] >= 15:
        gnss_quality = "GOOD"
    elif sat_result["avg_satellites"] >= 10:
        gnss_quality = "NORMAL"
    else:
        gnss_quality = "POOR"

    mission = MissionQuality(quality["quality"], gnss_quality, good_percent).analyze()

    pdops = [s["pdop"] for s in pdop_series]

    return {
        "final_score": mission["final"],
        "photo_quality": quality["quality"],
        "gnss_quality": gnss_quality,
        "good_percent": round(good_percent, 1),
        "good_count": good_count,
        "normal_count": normal_count,
        "low_count": low_count,
        "avg_satellites": round(float(sum(r["satellites"] for r in report) / len(report)), 1) if report else 0.0,
        "min_satellites": int(min(r["satellites"] for r in report)) if report else 0,
        "max_satellites": int(max(r["satellites"] for r in report)) if report else 0,
        "photo_count": len(report),
        "flight_duration_min": round(float(time_result["duration_sec"]) / 60, 1),
        "start_time": str(time_result["start"]),
        "end_time": str(time_result["end"]),
        "recording_interval_sec": round(float(time_result["median_interval"]), 3),
        "unique_satellites": int(sat_result["unique_satellites"]),
        "most_used_constellation": most_used,
        "least_used_constellation": least_used,
        "trajectory_points": len(trajectory_points),
        "trajectory_distance_m": round(distance_m, 1),
        "avg_pdop": round(float(sum(pdops) / len(pdops)), 2) if pdops else None,
        "max_pdop": round(float(max(pdops)), 2) if pdops else None,
        "csv_path": csv_out_path,
    }
