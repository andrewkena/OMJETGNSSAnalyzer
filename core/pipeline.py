import os
from collections import Counter

import numpy as np

from core.rinex_time_reader import RinexTimeReader
from core.time_analysis import TimeAnalysis
from core.satellite_analysis import SatelliteAnalysis
from core.timemark_analysis import TimemarkAnalysis
from core.photo_quality import PhotoQuality
from core.cnb_analysis import CnbAnalysis
from core.photo_satellite_report import PhotoSatelliteReport
from core.mission_quality import MissionQuality
from core.mission_report import MissionReport
from core.report_exporter import ReportExporter
from core.pdf_report import PdfReport
from core.project_runner import ProjectRunner

from core.novatel.reader import iter_messages
from core.novatel.bestpos import decode_bestposb, pos_type_label
from core.novatel.gps_ephemeris import gps_time_to_datetime, decode_rawephem, GPS_EPOCH
from core.pdop import compute_pdop_series
from core.obs_header_reader import read_obs_signal_types, system_name
from core.obs_file import find_obs_file

from core.ublox.reader import iter_messages as ubx_iter_messages
from core.ublox.pvt import decode_navpvt
from core.ublox.navsat import decode_navsat, GNSS_ID_LETTER
from core.ublox.timemark import decode_timtm2
from core.ublox.posecef import decode_navposecef
from core.ublox.posllh import decode_navposllh
from core.ublox.navstatus import decode_navstatus
from core.ublox.timeutc import decode_navtimeutc
from core.ublox.rawx import decode_rxmrawx

from plots.satellites_plot import SatellitesPlot
from plots.timemark_interval_plot import TimemarkIntervalPlot
from plots.timemark_histogram import TimemarkHistogram
from plots.mission_trajectory_plot import MissionTrajectoryPlot, DEFAULT_BASEMAP
from plots.altitude_profile_plot import AltitudeProfilePlot
from plots.pdop_plot import PdopPlot

MSG_ID_BESTPOS = 42
MSG_ID_RAWEPHEM = 41

UBX_CLASS_NAV = 0x01
UBX_ID_NAV_POSECEF = 0x01
UBX_ID_NAV_POSLLH = 0x02
UBX_ID_NAV_STATUS = 0x03
UBX_ID_NAV_PVT = 0x07
UBX_ID_NAV_TIMEUTC = 0x21
UBX_ID_NAV_SAT = 0x35
UBX_CLASS_RXM = 0x02
UBX_ID_RXM_RAWX = 0x15
UBX_CLASS_TIM = 0x0D
UBX_ID_TIM_TM2 = 0x03


def _report(progress_callback, percent, message):
    if progress_callback:
        progress_callback(percent, message)


def _haversine_m(lat1, lon1, lat2, lon2):
    import math
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def _extract_trajectory(cnb_file):
    points = []
    for msg in iter_messages(cnb_file):
        if msg.msg_id != MSG_ID_BESTPOS:
            continue
        fix = decode_bestposb(msg.body)
        if fix is not None:
            fix["time"] = gps_time_to_datetime(msg.week, msg.tow_sec)
            fix["pos_type"] = pos_type_label(fix["pos_type"])
            points.append(fix)

    distance_m = sum(
        _haversine_m(
            points[i]["lat"], points[i]["lon"],
            points[i + 1]["lat"], points[i + 1]["lon"]
        )
        for i in range(len(points) - 1)
    )

    return points, distance_m


def _extract_ephemerides(cnb_file):
    ephemerides = []
    for msg in iter_messages(cnb_file):
        if msg.msg_id != MSG_ID_RAWEPHEM:
            continue
        eph = decode_rawephem(msg.body, msg.week)
        if eph is not None:
            ephemerides.append(eph)
    return ephemerides


def _match_photos_to_trajectory(timemarks, trajectory_points):
    if not trajectory_points:
        return []

    matched = []
    for t in timemarks:
        closest = min(
            trajectory_points,
            key=lambda p: abs((p["time"] - t).total_seconds())
        )
        matched.append(closest)

    return matched


def _position_accuracy_summary(trajectory_points):
    if not trajectory_points:
        return None

    type_counts = Counter(p["pos_type"] for p in trajectory_points)
    dominant_type = type_counts.most_common(1)[0][0]

    n = len(trajectory_points)
    return {
        "dominant_type": dominant_type,
        "type_breakdown": dict(type_counts),
        "avg_lat_sigma": sum(p["lat_sigma"] for p in trajectory_points) / n,
        "avg_lon_sigma": sum(p["lon_sigma"] for p in trajectory_points) / n,
        "avg_height_sigma": sum(p["height_sigma"] for p in trajectory_points) / n,
    }


def _cruise_avg(heights):
    if not heights:
        return None
    lo, hi = min(heights), max(heights)
    rng = hi - lo
    if rng < 5:
        return sum(heights) / len(heights)
    threshold = lo + rng * 0.60
    above = [i for i, h in enumerate(heights) if h >= threshold]
    if not above:
        return sum(heights) / len(heights)
    cruise = heights[above[0]: above[-1] + 1]
    return sum(cruise) / len(cruise)


def _altitude_summary(trajectory_points):
    if not trajectory_points:
        return None

    heights = [p["height"] for p in trajectory_points]
    return {
        "min_height": min(heights),
        "max_height": max(heights),
        "avg_height": _cruise_avg(heights),
        "height_range": max(heights) - min(heights),
    }


def _signal_summary(obs_file, sat_result):
    signal_types = read_obs_signal_types(obs_file)

    usage = {
        "G": sat_result["gps_avg"],
        "R": sat_result["glo_avg"],
        "E": sat_result["gal_avg"],
        "C": sat_result["bds_avg"],
    }
    usage = {k: v for k, v in usage.items() if k in signal_types}

    most_used = max(usage, key=usage.get) if usage else None
    least_used = min(usage, key=usage.get) if usage else None

    groups = [
        {
            "system": system_name(sys_char),
            "codes": codes,
            "avg_satellites": usage.get(sys_char),
        }
        for sys_char, codes in signal_types.items()
    ]

    return {
        "groups": groups,
        "most_used": system_name(most_used) if most_used else None,
        "least_used": system_name(least_used) if least_used else None,
    }


def _pdop_summary(pdop_series):
    if not pdop_series:
        return None

    pdops = [s["pdop"] for s in pdop_series]
    return {
        "avg_pdop": sum(pdops) / len(pdops),
        "max_pdop": max(pdops),
        "poor_count": sum(1 for p in pdops if p > 6),
        "samples": len(pdops),
    }


def _ubx_week_from_navpvt(ubx_file):
    for msg in ubx_iter_messages(ubx_file):
        if msg.msg_class != UBX_CLASS_NAV or msg.msg_id != UBX_ID_NAV_PVT:
            continue
        fix = decode_navpvt(msg.payload)
        if fix and fix["utc_datetime"] is not None:
            return (fix["utc_datetime"] - GPS_EPOCH).days // 7
    return None


def _ubx_week_from_navtimeutc(ubx_file):
    for msg in ubx_iter_messages(ubx_file):
        if msg.msg_class != UBX_CLASS_NAV or msg.msg_id != UBX_ID_NAV_TIMEUTC:
            continue
        dt = decode_navtimeutc(msg.payload)
        if dt is not None:
            return (dt - GPS_EPOCH).days // 7
    return None


def _ubx_week_from_rawx(ubx_file):
    for msg in ubx_iter_messages(ubx_file):
        if msg.msg_class != UBX_CLASS_RXM or msg.msg_id != UBX_ID_RXM_RAWX:
            continue
        result = decode_rxmrawx(msg.payload)
        if result is not None:
            return result[0]
    return None


def _ubx_ref_week(ubx_file):
    """GPS week anchor for messages that only carry iTOW (ms of week).
    Tried in order of reliability: TIM-TM2 and RXM-RAWX carry an exact week
    number directly; NAV-TIMEUTC/NAV-PVT only give a UTC date, from which the
    week is derived approximately (fine -- the 18s GPS/UTC leap offset never
    crosses a week boundary in practice)."""
    for msg in ubx_iter_messages(ubx_file):
        if msg.msg_class != UBX_CLASS_TIM or msg.msg_id != UBX_ID_TIM_TM2:
            continue
        result = decode_timtm2(msg.payload)
        if result is not None:
            return result[1]

    week = _ubx_week_from_rawx(ubx_file)
    if week is not None:
        return week

    week = _ubx_week_from_navtimeutc(ubx_file)
    if week is not None:
        return week

    return _ubx_week_from_navpvt(ubx_file)


def _ubx_extract_timemarks(ubx_file):
    timemarks = []
    for msg in ubx_iter_messages(ubx_file):
        if msg.msg_class != UBX_CLASS_TIM or msg.msg_id != UBX_ID_TIM_TM2:
            continue
        result = decode_timtm2(msg.payload)
        if result is not None:
            timemarks.append(result[0])
    return timemarks


def _trajectory_distance(points):
    return sum(
        _haversine_m(
            points[i]["lat"], points[i]["lon"],
            points[i + 1]["lat"], points[i + 1]["lon"]
        )
        for i in range(len(points) - 1)
    )


def _ubx_trajectory_from_navpvt(ubx_file, ref_week):
    points = []
    prev_itow = None
    week = ref_week

    for msg in ubx_iter_messages(ubx_file):
        if msg.msg_class != UBX_CLASS_NAV or msg.msg_id != UBX_ID_NAV_PVT:
            continue

        fix = decode_navpvt(msg.payload)
        if fix is None:
            continue

        itow = fix["iTOW"]
        # A large backward jump in iTOW only happens on a GPS week rollover.
        if prev_itow is not None and itow < prev_itow - 100_000:
            week += 1
        prev_itow = itow

        fix["time"] = gps_time_to_datetime(week, itow / 1000.0)
        points.append(fix)

    return points


def _ubx_trajectory_from_raw_nav(ubx_file, ref_week):
    """Fallback for receivers configured for raw-data (PPK) logging, which
    typically omit NAV-PVT: position comes from NAV-POSLLH (preferred) or
    NAV-POSECEF, fix quality/RTK state from NAV-STATUS, matched by iTOW.
    None of these carry a satellite count or DOP, so those fields are unset."""
    pos_by_itow = {}
    ecef_by_itow = {}
    status_by_itow = {}

    for msg in ubx_iter_messages(ubx_file):
        if msg.msg_class != UBX_CLASS_NAV:
            continue
        if msg.msg_id == UBX_ID_NAV_POSLLH:
            fix = decode_navposllh(msg.payload)
            if fix:
                pos_by_itow[fix["iTOW"]] = fix
        elif msg.msg_id == UBX_ID_NAV_POSECEF:
            fix = decode_navposecef(msg.payload)
            if fix:
                ecef_by_itow[fix["iTOW"]] = fix
        elif msg.msg_id == UBX_ID_NAV_STATUS:
            status = decode_navstatus(msg.payload)
            if status:
                status_by_itow[status["iTOW"]] = status

    # NAV-POSLLH gives lat/lon/height directly and needs no coordinate
    # conversion -- prefer it, falling back to ECEF only if it's not logged.
    if not pos_by_itow:
        pos_by_itow = ecef_by_itow

    points = []
    prev_itow = None
    week = ref_week

    for itow in sorted(pos_by_itow):
        # Rollover tracking runs over the raw iTOW sequence regardless of
        # whether the fix at this iTOW ends up filtered out below.
        if prev_itow is not None and itow < prev_itow - 100_000:
            week += 1
        prev_itow = itow

        fix = dict(pos_by_itow[itow])
        status = status_by_itow.get(itow)

        # No-fix epochs decode to a degenerate ECEF(0,0,0) -> lat=180, height
        # near -6378137 m. NAV-STATUS is the authoritative check; the height
        # sanity bound is a defensive fallback if NAV-STATUS isn't logged.
        if status is not None and status["pos_type"] == "NONE":
            continue
        if abs(fix["height"]) > 100_000:
            continue

        fix["pos_type"] = status["pos_type"] if status else "SINGLE"
        fix["num_svs"] = None
        fix["num_soln_svs"] = None
        fix["pdop"] = 0.0  # not available without NAV-PVT

        fix["time"] = gps_time_to_datetime(week, itow / 1000.0)
        points.append(fix)

    return points


def _ubx_extract_trajectory(ubx_file, ref_week):
    if ref_week is None:
        return [], 0.0

    points = _ubx_trajectory_from_navpvt(ubx_file, ref_week)
    if not points:
        points = _ubx_trajectory_from_raw_nav(ubx_file, ref_week)

    return points, _trajectory_distance(points)


def _empty_satellite_result():
    return {
        "zero_sat_epochs": 0,
        "min_time": None,
        "max_time": None,
        "epoch_times": [],
        "epoch_sat_counts": [],
        "avg_satellites": 0.0,
        "min_satellites": 0,
        "max_satellites": 0,
        "gps_avg": 0.0,
        "glo_avg": 0.0,
        "gal_avg": 0.0,
        "bds_avg": 0.0,
        "unique_satellites": 0,
    }


def _aggregate_satellite_counts(epoch_times, epoch_counts, gps_counts, glo_counts, gal_counts, bds_counts, unique_satellites):
    if not epoch_counts:
        return _empty_satellite_result()

    counts_arr = np.array(epoch_counts)
    min_idx = int(np.argmin(counts_arr))
    max_idx = int(np.argmax(counts_arr))

    return {
        "zero_sat_epochs": int(np.sum(counts_arr == 0)),
        "min_time": epoch_times[min_idx],
        "max_time": epoch_times[max_idx],
        "epoch_times": epoch_times,
        "epoch_sat_counts": epoch_counts,
        "avg_satellites": float(np.mean(counts_arr)),
        "min_satellites": int(np.min(counts_arr)),
        "max_satellites": int(np.max(counts_arr)),
        "gps_avg": float(np.mean(gps_counts)),
        "glo_avg": float(np.mean(glo_counts)),
        "gal_avg": float(np.mean(gal_counts)),
        "bds_avg": float(np.mean(bds_counts)),
        "unique_satellites": len(unique_satellites),
    }


def _ubx_satellites_from_navsat(ubx_file, ref_week):
    epoch_times, epoch_counts = [], []
    gps_counts, glo_counts, gal_counts, bds_counts = [], [], [], []
    unique_satellites = set()

    prev_itow = None
    week = ref_week

    for msg in ubx_iter_messages(ubx_file):
        if msg.msg_class != UBX_CLASS_NAV or msg.msg_id != UBX_ID_NAV_SAT:
            continue

        result = decode_navsat(msg.payload)
        if result is None:
            continue

        itow, satellites = result
        if prev_itow is not None and itow < prev_itow - 100_000:
            week += 1
        prev_itow = itow

        epoch_times.append(gps_time_to_datetime(week, itow / 1000.0))

        used = [s for s in satellites if s["used"]]
        epoch_counts.append(len(used))
        gps_counts.append(sum(1 for s in used if GNSS_ID_LETTER.get(s["gnssId"]) == "G"))
        glo_counts.append(sum(1 for s in used if GNSS_ID_LETTER.get(s["gnssId"]) == "R"))
        gal_counts.append(sum(1 for s in used if GNSS_ID_LETTER.get(s["gnssId"]) == "E"))
        bds_counts.append(sum(1 for s in used if GNSS_ID_LETTER.get(s["gnssId"]) == "C"))

        for s in used:
            letter = GNSS_ID_LETTER.get(s["gnssId"])
            if letter:
                unique_satellites.add(f"{letter}{s['svId']:02d}")

    return _aggregate_satellite_counts(
        epoch_times, epoch_counts, gps_counts, glo_counts, gal_counts, bds_counts, unique_satellites
    )


def _ubx_satellites_from_rawx(ubx_file):
    """Fallback for raw-data (PPK) logging configs that omit NAV-SAT: each
    RXM-RAWX record already carries an exact (week, rcvTow), so no iTOW
    anchoring is needed here. "Used" means the raw pseudorange was flagged
    valid (trkStat.prValid) -- the closest available proxy for svUsed when
    the nav engine's own satellite-usage message isn't logged."""
    epoch_times, epoch_counts = [], []
    gps_counts, glo_counts, gal_counts, bds_counts = [], [], [], []
    unique_satellites = set()

    for msg in ubx_iter_messages(ubx_file):
        if msg.msg_class != UBX_CLASS_RXM or msg.msg_id != UBX_ID_RXM_RAWX:
            continue

        result = decode_rxmrawx(msg.payload)
        if result is None:
            continue

        week, rcv_tow, measurements = result
        epoch_times.append(gps_time_to_datetime(week, rcv_tow))

        # A single satellite can appear as several measurement blocks (one
        # per tracked signal/frequency) -- dedupe by (gnssId, svId) so a
        # dual-frequency satellite isn't counted twice.
        used_svs = {(m["gnssId"], m["svId"]) for m in measurements if m["used"]}
        epoch_counts.append(len(used_svs))
        gps_counts.append(sum(1 for gnss_id, _ in used_svs if GNSS_ID_LETTER.get(gnss_id) == "G"))
        glo_counts.append(sum(1 for gnss_id, _ in used_svs if GNSS_ID_LETTER.get(gnss_id) == "R"))
        gal_counts.append(sum(1 for gnss_id, _ in used_svs if GNSS_ID_LETTER.get(gnss_id) == "E"))
        bds_counts.append(sum(1 for gnss_id, _ in used_svs if GNSS_ID_LETTER.get(gnss_id) == "C"))

        for gnss_id, sv_id in used_svs:
            letter = GNSS_ID_LETTER.get(gnss_id)
            if letter:
                unique_satellites.add(f"{letter}{sv_id:02d}")

    return _aggregate_satellite_counts(
        epoch_times, epoch_counts, gps_counts, glo_counts, gal_counts, bds_counts, unique_satellites
    )


def _ubx_extract_satellites(ubx_file, ref_week):
    if ref_week is not None:
        result = _ubx_satellites_from_navsat(ubx_file, ref_week)
        if result["epoch_sat_counts"]:
            return result

    return _ubx_satellites_from_rawx(ubx_file)


def run_pipeline_ubx(ubx_file, progress_callback=None, basemap=None):
    runner = ProjectRunner(ubx_file)
    runner.prepare_folders()

    name = os.path.splitext(os.path.basename(ubx_file))[0]

    _report(progress_callback, 3, "Определение опорной GPS-недели...")
    ref_week = _ubx_ref_week(ubx_file)

    _report(progress_callback, 5, "Извлечение фотометок (TIM-TM2)...")
    timemarks = _ubx_extract_timemarks(ubx_file)

    _report(progress_callback, 15, "Извлечение траектории (NAV-PVT/NAV-POSECEF)...")
    trajectory_points, trajectory_distance_m = _ubx_extract_trajectory(ubx_file, ref_week)
    position_accuracy = _position_accuracy_summary(trajectory_points)
    altitude_summary = _altitude_summary(trajectory_points)

    altitude_png = None
    if trajectory_points:
        altitude_png = os.path.join(runner.plots_dir, f"{name}_altitude_profile.png")
        AltitudeProfilePlot(trajectory_points, altitude_png).show()

    pdop_series = [
        {"time": p["time"], "pdop": p["pdop"], "num_sats": p["num_svs"]}
        for p in trajectory_points if p["pdop"] > 0
    ]
    pdop_summary = _pdop_summary(pdop_series)

    pdop_png = None
    if pdop_series:
        pdop_png = os.path.join(runner.plots_dir, f"{name}_pdop.png")
        PdopPlot(pdop_series, pdop_png).show()

    _report(progress_callback, 45, "Анализ времени съёмки...")
    time_result = TimeAnalysis(np.array(
        [p["time"] for p in trajectory_points], dtype="datetime64[ms]"
    )).get_summary()

    matched_fixes = _match_photos_to_trajectory(timemarks, trajectory_points)

    _report(progress_callback, 58, "Анализ спутников (NAV-SAT/RXM-RAWX)...")
    sat_result = _ubx_extract_satellites(ubx_file, ref_week)
    signal_summary = None

    epoch_times = sat_result["epoch_times"]
    epoch_counts = sat_result["epoch_sat_counts"]
    n = min(len(epoch_times), len(epoch_counts))

    _report(progress_callback, 75, "Построение графика спутников...")
    satellites_png = os.path.join(runner.plots_dir, f"{name}_satellites.png")
    SatellitesPlot(epoch_times[:n], epoch_counts[:n], satellites_png).show()

    _report(progress_callback, 80, "Анализ качества фотосъёмки...")
    if timemarks:
        quality = PhotoQuality(timemarks).analyze()

        photo_intervals_png = os.path.join(runner.plots_dir, f"{name}_photo_intervals.png")
        TimemarkIntervalPlot(timemarks, photo_intervals_png).show()

        photo_histogram_png = os.path.join(runner.plots_dir, f"{name}_photo_histogram.png")
        TimemarkHistogram(timemarks, photo_histogram_png).show()
    else:
        # No TIM-TM2 in the file (e.g. a test/calibration log without a
        # camera) -- report the mission without a photo-quality section
        # rather than crashing on empty timemark statistics.
        quality = {
            "median_interval": 0.0, "std_dev": 0.0, "p95": 0.0,
            "longest_gap": 0.0, "gap_count": 0, "quality": "NO_PHOTOS",
            "cluster_size": 0, "excluded_count": 0,
        }
        photo_intervals_png = None
        photo_histogram_png = None

    _report(progress_callback, 88, "Сопоставление фото со спутниками...")
    csv_path = os.path.join(runner.reports_dir, f"{name}_photo_satellite_report.csv")
    photo_result = PhotoSatelliteReport(
        timemarks,
        sat_result["epoch_times"],
        sat_result["epoch_sat_counts"],
        csv_path,
        fixes=matched_fixes,
    ).analyze()

    report = photo_result["report"]
    good_count = photo_result["good"]
    normal_count = photo_result["normal"]
    low_count = photo_result["low"]
    good_percent = (good_count / len(report)) * 100 if report else 0.0

    _report(progress_callback, 91, "Построение траектории с метками фото...")
    photo_points = [
        {**fix, "quality": report[i]["quality"], "height": report[i].get("height")}
        for i, fix in enumerate(matched_fixes)
    ]

    trajectory_png = None
    if trajectory_points:
        trajectory_png = os.path.join(runner.plots_dir, f"{name}_trajectory.png")
        MissionTrajectoryPlot(
            trajectory_points, photo_points, trajectory_png,
            basemap=basemap or DEFAULT_BASEMAP
        ).show()

    if sat_result["avg_satellites"] >= 20:
        gnss_quality = "EXCELLENT"
    elif sat_result["avg_satellites"] >= 15:
        gnss_quality = "GOOD"
    elif sat_result["avg_satellites"] >= 10:
        gnss_quality = "NORMAL"
    else:
        gnss_quality = "POOR"

    mission = MissionQuality(
        quality["quality"],
        gnss_quality,
        good_percent
    ).analyze()

    mission_data = {
        "photo_quality": quality["quality"],
        "gnss_quality": gnss_quality,

        "good_count": good_count,
        "normal_count": normal_count,
        "low_count": low_count,

        "good_percent": good_percent,

        # With no photos to correlate against, fall back to the satellite
        # stats over the whole recording rather than dividing by zero.
        "avg_satellites": (
            sum(r["satellites"] for r in report) / len(report)
            if report else sat_result["avg_satellites"]
        ),
        "min_satellites": (
            min(r["satellites"] for r in report)
            if report else sat_result["min_satellites"]
        ),
        "max_satellites": (
            max(r["satellites"] for r in report)
            if report else sat_result["max_satellites"]
        ),

        "photo_count": len(report),
        "flight_duration_min": time_result["duration_sec"] / 60,
        "unique_satellites": sat_result["unique_satellites"],

        "final_score": mission["final"]
    }

    mission_text = MissionReport(mission_data).generate_text()

    _report(progress_callback, 95, "Сохранение отчётов и PDF...")
    txt_path = os.path.join(runner.reports_dir, f"{name}_mission_report.txt")
    ReportExporter(mission_data).save_txt(txt_path)

    pdf_path = os.path.join(runner.reports_dir, f"{name}_mission_report.pdf")
    PdfReport(mission_data, image_dir=runner.plots_dir).generate(pdf_path)

    _report(progress_callback, 100, "Готово")

    return {
        "runner": runner,
        "time_result": time_result,
        "signal_summary": signal_summary,
        "sat_result": sat_result,
        "photo_quality": quality,
        "photo_report": report,
        "matched_fixes": matched_fixes,
        "mission_data": mission_data,
        "mission_text": mission_text,
        "trajectory": {
            "points": trajectory_points,
            "distance_m": trajectory_distance_m,
            "position_accuracy": position_accuracy,
            "altitude": altitude_summary,
        },
        "pdop": pdop_summary,
        "plots": {
            "satellites": satellites_png,
            "photo_intervals": photo_intervals_png,
            "photo_histogram": photo_histogram_png,
            "trajectory": trajectory_png,
            "altitude_profile": altitude_png,
            "pdop": pdop_png,
        },
        "files": {
            "csv": csv_path,
            "txt": txt_path,
            "pdf": pdf_path,
        }
    }


def run_pipeline(cnb_file, progress_callback=None, basemap=None):
    if cnb_file.lower().endswith(".ubx"):
        return run_pipeline_ubx(cnb_file, progress_callback=progress_callback, basemap=basemap)

    obs_file = find_obs_file(cnb_file)

    runner = ProjectRunner(cnb_file)
    runner.prepare_folders()

    name = os.path.splitext(os.path.basename(cnb_file))[0]

    _report(progress_callback, 2, "Анализ CNB файла...")
    CnbAnalysis(cnb_file).analyze()

    _report(progress_callback, 8, "Извлечение траектории из CNB...")
    trajectory_points, trajectory_distance_m = _extract_trajectory(cnb_file)
    position_accuracy = _position_accuracy_summary(trajectory_points)
    altitude_summary = _altitude_summary(trajectory_points)

    altitude_png = None
    if trajectory_points:
        altitude_png = os.path.join(runner.plots_dir, f"{name}_altitude_profile.png")
        AltitudeProfilePlot(trajectory_points, altitude_png).show()

    _report(progress_callback, 18, "Извлечение GPS-эфемерид из CNB...")
    ephemerides = _extract_ephemerides(cnb_file)

    _report(progress_callback, 28, "Расчёт PDOP по эпохам...")
    pdop_series = compute_pdop_series(cnb_file, ephemerides, trajectory_points)
    pdop_summary = _pdop_summary(pdop_series)

    pdop_png = None
    if pdop_series:
        pdop_png = os.path.join(runner.plots_dir, f"{name}_pdop.png")
        PdopPlot(pdop_series, pdop_png).show()

    _report(progress_callback, 40, "Анализ временных меток фото...")
    timemark_analysis = TimemarkAnalysis(obs_file)
    tm = timemark_analysis.analyze()

    _report(progress_callback, 48, "Анализ времени съёмки...")
    reader = RinexTimeReader(obs_file)
    times = reader.get_times()
    time_result = TimeAnalysis(times).get_summary()

    matched_fixes = _match_photos_to_trajectory(tm["timemarks"], trajectory_points)

    _report(progress_callback, 58, "Анализ спутников (RINEX OBS)...")
    sat_result = SatelliteAnalysis(obs_file).analyze()
    signal_summary = _signal_summary(obs_file, sat_result)

    epoch_times = sat_result["epoch_times"]
    epoch_counts = sat_result["epoch_sat_counts"]
    n = min(len(epoch_times), len(epoch_counts))

    _report(progress_callback, 75, "Построение графика спутников...")
    satellites_png = os.path.join(runner.plots_dir, f"{name}_satellites.png")
    sat_plot = SatellitesPlot(
        epoch_times[:n],
        epoch_counts[:n],
        satellites_png
    )
    sat_plot.show()

    _report(progress_callback, 80, "Анализ качества фотосъёмки...")
    quality = PhotoQuality(tm["timemarks"]).analyze()

    photo_intervals_png = os.path.join(runner.plots_dir, f"{name}_photo_intervals.png")
    TimemarkIntervalPlot(tm["timemarks"], photo_intervals_png).show()

    photo_histogram_png = os.path.join(runner.plots_dir, f"{name}_photo_histogram.png")
    TimemarkHistogram(tm["timemarks"], photo_histogram_png).show()

    _report(progress_callback, 88, "Сопоставление фото со спутниками...")
    csv_path = os.path.join(runner.reports_dir, f"{name}_photo_satellite_report.csv")
    photo_result = PhotoSatelliteReport(
        tm["timemarks"],
        sat_result["epoch_times"],
        sat_result["epoch_sat_counts"],
        csv_path,
        fixes=matched_fixes,
    ).analyze()

    report = photo_result["report"]
    good_count = photo_result["good"]
    normal_count = photo_result["normal"]
    low_count = photo_result["low"]
    good_percent = (good_count / len(report)) * 100

    _report(progress_callback, 91, "Построение траектории с метками фото...")
    photo_points = [
        {**fix, "quality": report[i]["quality"], "height": report[i].get("height")}
        for i, fix in enumerate(matched_fixes)
    ]

    trajectory_png = None
    if trajectory_points:
        trajectory_png = os.path.join(runner.plots_dir, f"{name}_trajectory.png")
        MissionTrajectoryPlot(
            trajectory_points, photo_points, trajectory_png,
            basemap=basemap or DEFAULT_BASEMAP
        ).show()

    if sat_result["avg_satellites"] >= 20:
        gnss_quality = "EXCELLENT"
    elif sat_result["avg_satellites"] >= 15:
        gnss_quality = "GOOD"
    elif sat_result["avg_satellites"] >= 10:
        gnss_quality = "NORMAL"
    else:
        gnss_quality = "POOR"

    mission = MissionQuality(
        quality["quality"],
        gnss_quality,
        good_percent
    ).analyze()

    mission_data = {
        "photo_quality": quality["quality"],
        "gnss_quality": gnss_quality,

        "good_count": good_count,
        "normal_count": normal_count,
        "low_count": low_count,

        "good_percent": good_percent,

        "avg_satellites": sum(r["satellites"] for r in report) / len(report),
        "min_satellites": min(r["satellites"] for r in report),
        "max_satellites": max(r["satellites"] for r in report),

        "photo_count": len(report),
        "flight_duration_min": time_result["duration_sec"] / 60,
        "unique_satellites": sat_result["unique_satellites"],

        "final_score": mission["final"]
    }

    mission_text = MissionReport(mission_data).generate_text()

    _report(progress_callback, 95, "Сохранение отчётов и PDF...")
    txt_path = os.path.join(runner.reports_dir, f"{name}_mission_report.txt")
    ReportExporter(mission_data).save_txt(txt_path)

    pdf_path = os.path.join(runner.reports_dir, f"{name}_mission_report.pdf")
    PdfReport(mission_data, image_dir=runner.plots_dir).generate(pdf_path)

    _report(progress_callback, 100, "Готово")

    return {
        "runner": runner,
        "time_result": time_result,
        "signal_summary": signal_summary,
        "sat_result": sat_result,
        "photo_quality": quality,
        "photo_report": report,
        "matched_fixes": matched_fixes,
        "mission_data": mission_data,
        "mission_text": mission_text,
        "trajectory": {
            "points": trajectory_points,
            "distance_m": trajectory_distance_m,
            "position_accuracy": position_accuracy,
            "altitude": altitude_summary,
        },
        "pdop": pdop_summary,
        "plots": {
            "satellites": satellites_png,
            "photo_intervals": photo_intervals_png,
            "photo_histogram": photo_histogram_png,
            "trajectory": trajectory_png,
            "altitude_profile": altitude_png,
            "pdop": pdop_png,
        },
        "files": {
            "csv": csv_path,
            "txt": txt_path,
            "pdf": pdf_path,
        }
    }
