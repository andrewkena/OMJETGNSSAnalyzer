from core.pipeline import run_pipeline

CNB_FILE = r"C:\Users\andre\PycharmProjects\OMJET GNSS Analyzer\data\20260522083739.cnb"

result = run_pipeline(CNB_FILE)

sat_result = result["sat_result"]
quality = result["photo_quality"]

print()
print("SATELLITE ANALYSIS")
print("-" * 50)
print(f"Average Satellites  : {sat_result['avg_satellites']:.1f}")
print(f"Minimum Satellites  : {sat_result['min_satellites']}")
print(f"Maximum Satellites  : {sat_result['max_satellites']}")
print(f"GPS Average         : {sat_result['gps_avg']:.1f}")
print(f"GLONASS Average     : {sat_result['glo_avg']:.1f}")
print(f"Galileo Average     : {sat_result['gal_avg']:.1f}")
print(f"BeiDou Average      : {sat_result['bds_avg']:.1f}")
print()
print(f"Unique Satellites   : {sat_result['unique_satellites']}")

print()
print("PHOTO QUALITY")
print("-" * 50)
print(f"Nominal Interval : {quality['median_interval']:.3f} sec")
print(f"Std Deviation    : {quality['std_dev']:.3f} sec")
print(f"95 Percentile    : {quality['p95']:.3f} sec")
print(f"Longest Gap      : {quality['longest_gap']:.3f} sec")
print(f"Gap Count        : {quality['gap_count']}")
print(f"Quality          : {quality['quality']}")

print()
print(result["mission_text"])

print()
print("REPORT SAVED:", result["files"]["txt"])
print("PDF SAVED:", result["files"]["pdf"])
