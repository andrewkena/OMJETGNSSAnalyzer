FIX_NONE = 0
FIX_DEAD_RECKONING = 1
FIX_2D = 2
FIX_3D = 3
FIX_GNSS_DR = 4
FIX_TIME_ONLY = 5


def classify_pos_type(fix_type, diff_soln, carr_soln):
    """Maps u-blox fixType/carrSoln (from NAV-PVT or NAV-STATUS) to the same
    label strings used for Novatel BESTPOS, so reports read the same
    regardless of receiver brand."""
    if fix_type == FIX_NONE:
        return "NONE"
    if fix_type == FIX_DEAD_RECKONING:
        return "DEAD_RECKONING"
    if fix_type == FIX_2D:
        return "TYPE_2D"
    if fix_type == FIX_TIME_ONLY:
        return "TIME_ONLY"

    if carr_soln == 2:
        return "NARROW_INT"
    if carr_soln == 1:
        return "NARROW_FLOAT"
    return "PSRDIFF" if diff_soln else "SINGLE"
