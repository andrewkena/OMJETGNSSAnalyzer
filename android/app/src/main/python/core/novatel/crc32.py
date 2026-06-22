CRC32_POLYNOMIAL = 0xEDB88320


def _crc32_value(i):
    crc = i
    for _ in range(8):
        if crc & 1:
            crc = (crc >> 1) ^ CRC32_POLYNOMIAL
        else:
            crc >>= 1
    return crc & 0xFFFFFFFF


_TABLE = [_crc32_value(i) for i in range(256)]


def block_crc32(buffer):
    crc = 0
    for byte in buffer:
        crc = (crc >> 8) ^ _TABLE[(crc ^ byte) & 0xFF]
    return crc & 0xFFFFFFFF
