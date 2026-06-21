class EpochAnalysis:

    def __init__(self):
        self.records = []

    def add_epoch(
        self,
        time,
        sat_count,
        gps_count,
        glo_count,
        gal_count,
        bds_count
    ):

        self.records.append({
            "time": time,
            "satellites": sat_count,

            "gps": gps_count,
            "glo": glo_count,
            "gal": gal_count,
            "bds": bds_count
        })

    def get_records(self):
        return self.records