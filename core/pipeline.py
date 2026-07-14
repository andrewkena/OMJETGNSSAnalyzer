import os
from collections import Counter

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
from core.novatel.gps_ephemeris import gps_time_to_datetime, decode_rawephem
from core.pdop import compute_pdop_series
from core.obs_header_reader import read_obs_signal_types, system_name
from core.obs_file import find_obs_file

from plots.satellites_plot import SatellitesPlot
from plots.timemark_interval_plot import TimemarkIntervalPlot
from plots.timemark_histogram import TimemarkHistogram
from plots.mission_trajectory_plot import MissionTrajectoryPlot, DEFAULT_BASEMAP
from plots.altitude_profile_plot import AltitudeProfilePlot
from plots.pdop_plot import PdopPlot

MSG_ID_BESTPOS = 42
MSG_ID_RAWEPHEM = 41


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
        "dominant_type": pos_type_label(dominant_type),
        "type_breakdown": {
            pos_type_label(t): c for t, c in type_counts.items()
        },
        "avg_lat_sigma": sum(p["lat_sigma"] for p in trajectory_points) / n,
        "avg_lon_sigma": sum(p["lon_sigma"] for p in trajectory_points) / n,
        "avg_height_sigma": sum(p["height_sigma"] for p in trajectory_points) / n,
    }


def _altitude_summary(trajectory_points):
    if not trajectory_points:
        return None

    heights = [p["height"] for p in trajectory_points]
    return {
        "min_height": min(heights),
        "max_height": max(heights),
        "avg_height": sum(heights) / len(heights),
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


def run_pipeline(cnb_file, progress_callback=None, basemap=None):
    obs_file = find_obs_file(cnb_file)

    runner = ProjectRunner(cnb_file)
    runner.prepare_folders()

    _report(progress_callback, 2, "Анализ CNB файла...")
    CnbAnalysis(cnb_file).analyze()

    _report(progress_callback, 8, "Извлечение траектории из CNB...")
    trajectory_points, trajectory_distance_m = _extract_trajectory(cnb_file)
    position_accuracy = _position_accuracy_summary(trajectory_points)
    altitude_summary = _altitude_summary(trajectory_points)

    altitude_png = None
    if trajectory_points:
        altitude_png = os.path.join(runner.plots_dir, "altitude_profile.png")
        AltitudeProfilePlot(trajectory_points, altitude_png).show()

    _report(progress_callback, 18, "Извлечение GPS-эфемерид из CNB...")
    ephemerides = _extract_ephemerides(cnb_file)

    _report(progress_callback, 28, "Расчёт PDOP по эпохам...")
    pdop_series = compute_pdop_series(cnb_file, ephemerides, trajectory_points)
    pdop_summary = _pdop_summary(pdop_series)

    pdop_png = None
    if pdop_series:
        pdop_png = os.path.join(runner.plots_dir, "pdop.png")
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
    satellites_png = os.path.join(runner.plots_dir, "satellites.png")
    sat_plot = SatellitesPlot(
        epoch_times[:n],
        epoch_counts[:n],
        satellites_png
    )
    sat_plot.show()

    _report(progress_callback, 80, "Анализ качества фотосъёмки...")
    quality = PhotoQuality(tm["timemarks"]).analyze()

    photo_intervals_png = os.path.join(runner.plots_dir, "photo_intervals.png")
    TimemarkIntervalPlot(tm["timemarks"], photo_intervals_png).show()

    photo_histogram_png = os.path.join(runner.plots_dir, "photo_histogram.png")
    TimemarkHistogram(tm["timemarks"], photo_histogram_png).show()

    _report(progress_callback, 88, "Сопоставление фото со спутниками...")
    csv_path = os.path.join(runner.reports_dir, "photo_satellite_report.csv")
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
        trajectory_png = os.path.join(runner.plots_dir, "trajectory.png")
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
    txt_path = os.path.join(runner.reports_dir, "mission_report.txt")
    ReportExporter(mission_data).save_txt(txt_path)

    pdf_path = os.path.join(runner.reports_dir, "mission_report.pdf")
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
