import struct

from core.novatel.crc32 import block_crc32

SYNC = b"\xAA\x44\x12"

HEADER_FMT = "<HBBHHBBHI6xH"
# fields: msg_id, msg_type, port_addr, msg_len, sequence,
#         idle_time, time_status, week, ms, (receiver_status+reserved skipped), sw_version


class NovatelMessage:

    def __init__(self, msg_id, week, tow_ms, body):
        self.msg_id = msg_id
        self.week = week
        self.tow_ms = tow_ms
        self.body = body

    @property
    def tow_sec(self):
        return self.tow_ms / 1000.0


def iter_messages(path):
    with open(path, "rb") as f:
        data = f.read()

    n = len(data)
    i = 0

    while i + 4 <= n:
        if data[i:i + 3] != SYNC:
            i += 1
            continue

        header_len = data[i + 3]

        if header_len < 28 or i + header_len > n:
            i += 1
            continue

        msg_id, msg_type, port_addr, msg_len, sequence, idle_time, \
            time_status, week, ms, sw_version = struct.unpack_from(
                HEADER_FMT, data, i + 4
            )

        total_len = header_len + msg_len + 4

        if i + total_len > n:
            i += 1
            continue

        record = data[i:i + total_len]
        expected_crc = struct.unpack_from("<I", record, total_len - 4)[0]
        actual_crc = block_crc32(record[:total_len - 4])

        if actual_crc != expected_crc:
            i += 1
            continue

        body = data[i + header_len: i + header_len + msg_len]
        yield NovatelMessage(msg_id, week, ms, body)

        i += total_len
