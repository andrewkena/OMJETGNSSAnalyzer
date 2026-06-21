import struct

SOL_COMPUTED = 0

POS_TYPE_LABELS = {
    0: "NONE",
    1: "FIXEDPOS",
    16: "SINGLE",
    17: "PSRDIFF",
    32: "L1_FLOAT",
    33: "NARROW_FLOAT",
    48: "L1_INT",
    50: "NARROW_INT",
    34: "WIDE_LANE",
}


def pos_type_label(pos_type):
    return POS_TYPE_LABELS.get(pos_type, f"TYPE_{pos_type}")


def decode_bestposb(body):
    sol_stat, pos_type = struct.unpack_from("<II", body, 0)

    if sol_stat != SOL_COMPUTED:
        return None

    lat, lon, height = struct.unpack_from("<ddd", body, 8)
    lat_sigma, lon_sigma, height_sigma = struct.unpack_from("<fff", body, 40)
    num_svs, num_soln_svs = struct.unpack_from("<BB", body, 64)

    return {
        "pos_type": pos_type,
        "lat": lat,
        "lon": lon,
        "height": height,
        "lat_sigma": lat_sigma,
        "lon_sigma": lon_sigma,
        "height_sigma": height_sigma,
        "num_svs": num_svs,
        "num_soln_svs": num_soln_svs,
    }
