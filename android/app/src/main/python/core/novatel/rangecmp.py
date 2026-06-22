SYS_GPS = 0

# GPS signal type (tracking status bits 21-25) -> RINEX 3 observation band/attribute
# Empirically confirmed against a reference RINEX OBS produced by the vendor's own
# converter (PiDATA/SINOGNSS) -- this receiver only emits these 4 GPS channels.
GPS_SIGNAL_CODE = {
    0: "1C",   # L1 C/A
    9: "2W",   # L2 P(Y), semi-codeless
    17: "2X",  # L2C (M+L)
    2: "5I",   # L5 I
}

MAXVAL = 1 << 23  # 8388608, ADR rollover modulus
WAVELENGTH_L1 = 0.1902936727984
WAVELENGTH_L2 = 0.2442102134246
WAVELENGTH_L5 = 0.254828049

GPS_WAVELENGTH = {
    "1C": WAVELENGTH_L1,
    "2W": WAVELENGTH_L2,
    "2X": WAVELENGTH_L2,
    "5I": WAVELENGTH_L5,
}


def _sign_extend(value, bits):
    if value & (1 << (bits - 1)):
        return value - (1 << bits)
    return value


def decode_rangecmpb(body):
    num_obs = int.from_bytes(body[0:4], "little")
    records = []

    for k in range(num_obs):
        offset = 4 + k * 24
        record = body[offset:offset + 24]

        if len(record) < 24:
            break

        value = int.from_bytes(record, "little")

        tracking_status = value & 0xFFFFFFFF
        system = (tracking_status >> 16) & 0xF
        signal_type = (tracking_status >> 21) & 0x1F
        phase_lock = (tracking_status >> 8) & 1
        code_lock = (tracking_status >> 10) & 1

        if system != SYS_GPS:
            continue

        code = GPS_SIGNAL_CODE.get(signal_type)
        if code is None:
            continue

        doppler_raw = _sign_extend((value >> 32) & 0xFFFFFFF, 28)
        psr_raw = (value >> 60) & 0xFFFFFFFFF
        adr_raw = _sign_extend((value >> 96) & 0xFFFFFFFF, 32)
        prn = (value >> 136) & 0xFF
        locktime_raw = (value >> 144) & 0x1FFFFF
        cno_raw = (value >> 165) & 0x1F

        psr = psr_raw / 128.0
        doppler_hz = doppler_raw / 256.0
        adr_cycles = adr_raw / 256.0
        locktime = locktime_raw / 32.0
        cn0 = 20.0 + cno_raw

        wavelength = GPS_WAVELENGTH[code]
        n_rolls = round((psr / wavelength + adr_cycles) / MAXVAL)
        adr_corrected = adr_cycles - n_rolls * MAXVAL
        carrier_phase = -adr_corrected

        records.append({
            "system": "G",
            "prn": prn,
            "code": code,
            "psr": psr,
            "carrier_phase": carrier_phase,
            "doppler": doppler_hz,
            "cn0": cn0,
            "locktime": locktime,
            "phase_lock": bool(phase_lock),
            "code_lock": bool(code_lock),
        })

    return records
