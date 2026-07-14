import gzip
import io
import os


def open_obs(path, encoding="utf-8", errors="ignore"):
    """Open a RINEX OBS file, transparently decompressing .gz archives."""
    if path.endswith(".gz"):
        return io.TextIOWrapper(gzip.open(path, "rb"), encoding=encoding, errors=errors)
    return open(path, "r", encoding=encoding, errors=errors)


def find_obs_file(cnb_file):
    """Return path to .obs or .obs.gz next to the .cnb file, or None."""
    for suffix in (".obs", ".obs.gz"):
        path = cnb_file + suffix
        if os.path.isfile(path):
            return path
    return None
