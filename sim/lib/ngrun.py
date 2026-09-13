"""Minimal headless ngspice driver via libngspice + ctypes.

PySpice's exec_command treats ngspice's stderr chatter as fatal, which it isn't.
This talks to the shared library directly: feed it a netlist whose .control block
does the analysis and writes results with wrdata, then read the file back.
"""
import ctypes, os, tempfile, pathlib

LIB = os.environ.get("NGSPICE_LIB", "/usr/lib/x86_64-linux-gnu/libngspice.so.0")

_OUT = []

@ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p)
def _send_char(msg, _id, _ud):
    _OUT.append(msg.decode("utf-8", "replace"))
    return 0

@ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p)
def _send_stat(msg, _id, _ud):
    return 0

@ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.c_bool, ctypes.c_bool, ctypes.c_int, ctypes.c_void_p)
def _exit(status, _unload, _quit, _id, _ud):
    return 0


def run(netlist: str, workdir=None):
    """Run a netlist containing its own .control block. Returns ngspice's log lines."""
    _OUT.clear()
    ng = ctypes.CDLL(LIB)
    ng.ngSpice_Init(_send_char, _send_stat, _exit, None, None, None, None)
    wd = pathlib.Path(workdir or tempfile.mkdtemp())
    wd.mkdir(parents=True, exist_ok=True)
    cir = wd / "_run.cir"
    cir.write_text(netlist)
    cwd = os.getcwd()
    try:
        os.chdir(wd)
        ng.ngSpice_Command(b"source _run.cir")
    finally:
        os.chdir(cwd)
    return list(_OUT)


def read_wrdata(path, names):
    """Read an ngspice `wrdata` file into a dict of name -> list[float].

    wrdata writes bare numeric columns with no header, and repeats the sweep
    variable before every trace: for `wrdata f a b` the columns are
    (x, a, x, b). Pass `names` for the logical columns including the sweep
    variable first -- e.g. ["frequency", "vdb_out"] -- and the duplicate
    sweep columns are dropped.
    """
    rows = [[float(v) for v in l.split()]
            for l in pathlib.Path(path).read_text().splitlines() if l.strip()]
    if not rows:
        raise ValueError(f"{path}: no data -- did the analysis converge?")
    cols = list(zip(*rows))
    x, traces = cols[0], cols[1::2]
    if len(names) != 1 + len(traces):
        raise ValueError(f"{path}: got {len(traces)} traces, names has {len(names)-1}")
    return {names[0]: list(x), **{n: list(t) for n, t in zip(names[1:], traces)}}
