SYNC1 = 0xB5
SYNC2 = 0x62


class UbxMessage:

    def __init__(self, msg_class, msg_id, payload):
        self.msg_class = msg_class
        self.msg_id = msg_id
        self.payload = payload


def _checksum(data):
    ck_a = ck_b = 0
    for b in data:
        ck_a = (ck_a + b) & 0xFF
        ck_b = (ck_b + ck_a) & 0xFF
    return ck_a, ck_b


def iter_messages(path):
    with open(path, "rb") as f:
        data = f.read()

    n = len(data)
    i = 0

    while i + 8 <= n:
        if data[i] != SYNC1 or data[i + 1] != SYNC2:
            i += 1
            continue

        msg_class = data[i + 2]
        msg_id = data[i + 3]
        length = data[i + 4] | (data[i + 5] << 8)

        total_len = 6 + length + 2
        if i + total_len > n:
            i += 1
            continue

        payload = data[i + 6: i + 6 + length]
        expected_ck_a = data[i + 6 + length]
        expected_ck_b = data[i + 7 + length]

        actual_ck_a, actual_ck_b = _checksum(data[i + 2: i + 6 + length])

        if actual_ck_a != expected_ck_a or actual_ck_b != expected_ck_b:
            i += 1
            continue

        yield UbxMessage(msg_class, msg_id, payload)

        i += total_len
