from core.novatel.reader import iter_messages
from core.novatel.rangecmp import decode_rangecmpb
from core.novatel.gps_ephemeris import decode_rawephem, gps_time_to_datetime
from core.rinex_obs_writer import write_rinex_obs
from core.rinex_nav_writer import write_rinex_nav

MSG_ID_RANGECMPB = 140
MSG_ID_RAWEPHEM = 41


class CnbDecoder:
    """Decodes the GPS observations (RANGECMPB) and GPS broadcast
    ephemeris (RAWEPHEM) out of a ComNav/SinoGNSS .cnb binary log.

    Other constellations (GLONASS/Galileo/BeiDou/QZSS) are not decoded:
    this vendor uses log IDs for their ephemeris that don't match the
    public NovAtel ICD, so they can't be decoded without an official
    ComNav specification.
    """

    def __init__(self, cnb_file):
        self.cnb_file = cnb_file

    def decode(self):
        epochs = []
        ephemerides = []

        for msg in iter_messages(self.cnb_file):
            if msg.msg_id == MSG_ID_RANGECMPB:
                records = decode_rangecmpb(msg.body)
                if records:
                    epoch_time = gps_time_to_datetime(msg.week, msg.tow_sec)
                    epochs.append((epoch_time, records))

            elif msg.msg_id == MSG_ID_RAWEPHEM:
                eph = decode_rawephem(msg.body, msg.week)
                if eph is not None:
                    ephemerides.append(eph)

        return {
            "epochs": epochs,
            "ephemerides": ephemerides,
        }

    def decode_to_files(self, obs_path, nav_path):
        result = self.decode()
        write_rinex_obs(obs_path, result["epochs"])
        write_rinex_nav(nav_path, result["ephemerides"])
        return result
