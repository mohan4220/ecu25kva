"""Engine + generator + rail + sensor model for the SIL simulator.

Mostly assumed: a plausible 3-cylinder genset diesel, chosen so that 34 mg
per injection carries 20 kW at 1500 rpm. The old ECU's own recording
(refs/field-evidence-2026-10-14.md) supplies the measured parts: the
injector law, the metering valve's polarity, and a check on WORK_PER_MG
(its inner torque, 84 Nm at 17 mg, against this model's 79 Nm).
"""
import math

RPM = 2 * math.pi / 60               # rad/s per rpm

J = 2.0                              # kg m2, engine + alternator rotor
WORK_PER_MG = 19.5                   # J indicated per mg fuel (LHV 42.6 kJ/g x 0.46)
GEN_EFF = 0.9
STARTER_T, STARTER_NOLOAD = 100.0, 165.0     # N m stall, rpm at zero torque
COMP_T = 40.0                        # N m compression/expansion ripple amplitude
TDC1 = 90.0                          # cycle angle of cylinder 1 firing TDC (= CRANK_TDC1_DEG)
NCYL = 3
CAM_DEG = 660.0                      # cam edge cycle angle

BAR_PER_CM3 = 750.0                  # bulk modulus / rail+pump volume
PUMP = 4.0 / 1500                    # cm3/s per rpm, metering fully open
METER_NC = False                     # measured: normally open, duty 1 = no flow
LEAK = 1e-4                          # cm3/s per bar
RELIEF = 1800.0
CM3_PER_MG = 0.0012

INJ_DEAD_US, INJ_K = 323.0, 0.00191  # measured on the old ECU (sec. 3d)


def friction(rpm):
    return 10 + 0.006 * rpm          # N m


def _lin(x, lo, hi):
    return 0.5 + 4.0 * (x - lo) / (hi - lo)


def _ntc_volts(t_c):
    r = 2500 * math.exp(3450 * (1 / (t_c + 273.15) - 1 / 293.15))
    return 5.0 * r / (r + 2490)


class Engine:
    def __init__(self):
        self.theta = 0.0             # cycle angle, deg
        self.omega = 0.0             # rad/s
        self.rail_bar = 0.0
        self.clt_c = 80.0
        self.duty = 0.0              # metering duty from the ECU
        self.load_kw = 0.0
        self.starter = False
        self.clt_open = False
        self.stuck_fuel_mg = None
        self.crank_lost = False
        self.drop_edge_once = False  # the next crank edge goes missing
        self.v_override = {}         # sensor faults: {"v_oil": 0.1} forces a reading
        self.net_torque = 0.0
        self.fuel = [0.0] * NCYL     # mg delivered for each cylinder's coming stroke
        self.cmd = [None] * NCYL     # (start_us, dur_us) not yet finished
        self.seq = [0] * NCYL

    @property
    def rpm(self):
        return self.omega / RPM

    def command(self, cyl, start_us, dur_us, seq):
        """Act on a new seq: latch a command, or (dur 0) cancel one not yet started."""
        if seq == self.seq[cyl]:
            return
        self.seq[cyl] = seq
        if dur_us:
            self.cmd[cyl] = (start_us, dur_us)
        elif self.cmd[cyl] and self._now < self.cmd[cyl][0]:
            self.cmd[cyl] = None

    _now = 0

    def step(self, t_us, dt_us=20):
        """Advance one step from t_us. Returns (crank edge times, cam edge times)."""
        self._now = t_us
        dt = dt_us * 1e-6
        rpm = self.rpm
        flow = INJ_K * math.sqrt(max(self.rail_bar, 0.0))     # mg/us while open
        q_inj = 0.0
        torque = 0.0
        for k in range(NCYL):
            phase = (self.theta - TDC1 - 240 * k) % 720
            if self.stuck_fuel_mg is None and self.cmd[k]:
                s, d = self.cmd[k]
                lo, hi = max(t_us, s + INJ_DEAD_US), min(t_us + dt_us, s + d)
                if hi > lo:
                    mg = (hi - lo) * flow
                    self.fuel[k] += mg
                    q_inj += mg
                if t_us + dt_us >= s + d:
                    self.cmd[k] = None
            if phase < 180:
                torque += WORK_PER_MG * self.fuel[k] / math.pi
        torque += COMP_T * math.sin(math.radians((self.theta - TDC1) % 240 * 1.5))
        if self.starter:
            torque += max(0.0, STARTER_T * (1 - rpm / STARTER_NOLOAD))
        torque -= friction(rpm) if self.omega > 0 else 0
        torque -= self.load_kw * 1000 / GEN_EFF / max(self.omega, 50.0)
        self.net_torque = torque
        self.omega = max(0.0, self.omega + torque / J * dt)

        # angle, edges, per-cylinder fuel bookkeeping
        old = self.theta
        new = old + math.degrees(self.omega * dt)
        crank, cam = [], []
        span = new - old
        if span > 0:
            n = math.floor(old / 6) + 1
            while n * 6 <= new:
                a = n * 6
                if (a % 360) / 6 < 58 and not self.crank_lost:
                    if self.drop_edge_once:
                        self.drop_edge_once = False
                    else:
                        crank.append(t_us + round((a - old) / span * dt_us))
                n += 1
            c = math.floor((old - CAM_DEG) / 720) + 1
            if CAM_DEG + 720 * c <= new:
                cam.append(t_us + round((CAM_DEG + 720 * c - old) / span * dt_us))
        for k in range(NCYL):
            tdc = TDC1 + 240 * k
            p_old, p_new = (old - tdc) % 720, (new - tdc) % 720
            if p_old < 180 <= p_new:
                self.fuel[k] = 0.0                       # power stroke over
            if p_new < p_old and self.stuck_fuel_mg is not None:
                self.fuel[k] = self.stuck_fuel_mg        # runaway: fuel regardless
        self.theta = new % 720

        # rail
        opening = self.duty if METER_NC else 1 - self.duty
        q = PUMP * rpm * opening - q_inj * CM3_PER_MG / dt - LEAK * self.rail_bar
        self.rail_bar = min(RELIEF, max(0.0, self.rail_bar + BAR_PER_CM3 * q * dt))

        # coolant towards a load-dependent temperature, tau 60 s
        target = 75 + 15 * self.load_kw / 20
        self.clt_c += (target - self.clt_c) * dt / 60
        return crank, cam

    def volts(self):
        load = self.load_kw / 20
        return {
            "v_clt": 5.0 if self.clt_open else _ntc_volts(self.clt_c),
            "v_oil": _lin(400 * self.rpm / 1500, 0, 1000),
            "v_rail": _lin(self.rail_bar, 0, 1800),
            "v_boost": _lin(100 + 100 * load, 50, 400),
            "v_egr": _lin(0, 0, 100),
            "v_5v": 5.0,
            **self.v_override,
        }



def _self_check():
    import statistics

    # starter alone, from rest: settles a little under 150 rpm
    e = Engine()
    e.starter = True
    t, tail = 0, []
    while t < 2_000_000:
        e.step(t)
        t += 20
        if t > 1_600_000:
            tail.append(e.rpm)
    assert 140 <= statistics.mean(tail) <= 150, statistics.mean(tail)

    # held at 1500 rpm, 34 mg per event, 20 kW: torque nearly balances
    e = Engine()
    e.load_kw, e.stuck_fuel_mg = 20, 34
    net, n, t = 0.0, 0, 0
    while t < 2 * 80_000:                       # two cycles at 1500 rpm
        e.omega = 1500 * RPM
        e.step(t)
        if t >= 80_000:
            net += e.net_torque
            n += 1
        t += 20
    load = 20_000 / GEN_EFF / (1500 * RPM)
    assert abs(net / n) < 0.10 * load, (net / n, load)

    # one cycle at 1500 rpm: 116 crank edges, 1 cam edge
    e = Engine()
    e.theta = 3.0                               # window (3, 723]: no edge on its ends
    crank = cam = 0
    t = 0
    while t < 80_000:
        e.omega = 1500 * RPM
        c, m = e.step(t)
        crank += len(c)
        cam += len(m)
        t += 20
    assert crank == 116 and cam == 1, (crank, cam)

    # rail fills while cranking with the metering valve open and no fuel
    e = Engine()
    e.duty = 1.0 if METER_NC else 0.0
    p0 = e.rail_bar
    for i in range(50_000):
        e.omega = 150 * RPM
        e.step(i * 20)
    assert e.rail_bar > p0 + 100, e.rail_bar
    print("engine.py ok")


if __name__ == "__main__":
    _self_check()
