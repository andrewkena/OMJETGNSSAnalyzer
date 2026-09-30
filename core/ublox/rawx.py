import struct

MEAS_BLOCK_SIZE = 32


def decode_rxmrawx(payload):
    if len(payload) < 16:
        return None

    rcv_tow = struct.unpack_from("<d", payload, 0)[0]
    week = struct.unpack_from("<H", payload, 8)[0]
    num_meas = payload[11]

    if week == 0:
        # Cold-start records before the receiver has a valid time fix carry
        # week=0 with rcvTow counting up from ~0 -- not a real GPS epoch.
        return None

    measurements = []
    offset = 16
    for _ in range(num_meas):
        if offset + MEAS_BLOCK_SIZE > len(payload):
            break

        # block = prMes(f8) cpMes(f8) doMes(f4) gnssId(u1) svId(u1) sigId(u1)
        # freqId(u1) locktime(u2) cno(u1) prStdev(x1) cpStdev(x1) doStdev(x1)
        # trkStat(x1) reserved3(u1) = 32 bytes
        gnss_id = payload[offset + 20]
        sv_id = payload[offset + 21]
        trk_stat = payload[offset + 30]
        pr_valid = bool(trk_stat & 0x01)

        measurements.append({"gnssId": gnss_id, "svId": sv_id, "used": pr_valid})
        offset += MEAS_BLOCK_SIZE

    return week, rcv_tow, measurements
