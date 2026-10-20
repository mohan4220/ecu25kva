//! Engine, generator, rail and sensor model: a port of
//! firmware/sim/engine.py, same constants, same operation order, so its
//! traces match the Python model's (tests/golden.rs). No I/O, so a bench
//! microcontroller can run it later.
//!
//! Mostly assumed: a plausible 3-cylinder genset diesel, chosen so that
//! 34 mg per injection carries 20 kW at 1500 rpm. The measured parts (the
//! injector law, the metering valve's polarity) come from the old ECU's
//! recording, refs/field-evidence-2026-10-14.md.
use std::f64::consts::PI;

pub const RPM: f64 = 2.0 * PI / 60.0; // rad/s per rpm

pub const J: f64 = 2.0; // kg m2, engine + alternator rotor
pub const WORK_PER_MG: f64 = 19.5; // J indicated per mg fuel
pub const GEN_EFF: f64 = 0.9;
/// The alternator's regulator rolls voltage off below this speed, so a
/// resistive load's power falls as (rpm / knee)^2.
pub const AVR_KNEE_RPM: f64 = 1410.0;
pub const STARTER_T: f64 = 100.0; // N m stall
pub const STARTER_NOLOAD: f64 = 165.0; // rpm at zero torque
pub const COMP_T: f64 = 40.0; // N m compression ripple amplitude
pub const TDC1: f64 = 90.0; // cycle angle of cylinder 1 firing TDC
pub const NCYL: usize = 3;
pub const CAM_DEG: f64 = 660.0; // cam edge cycle angle

pub const BAR_PER_CM3: f64 = 750.0;
pub const PUMP: f64 = 4.0 / 1500.0; // cm3/s per rpm, metering fully open
pub const METER_NC: bool = false; // measured: normally open, duty 1 = no flow
pub const LEAK: f64 = 1e-4; // cm3/s per bar
pub const RELIEF: f64 = 1800.0;
pub const CM3_PER_MG: f64 = 0.0012;

pub const INJ_DEAD_US: f64 = 323.0; // measured on the old ECU
pub const INJ_K: f64 = 0.00191;

pub fn friction(rpm: f64) -> f64 {
    10.0 + 0.006 * rpm
}

fn lin(x: f64, lo: f64, hi: f64) -> f64 {
    0.5 + 4.0 * (x - lo) / (hi - lo)
}

fn ntc_volts(t_c: f64) -> f64 {
    let r = 2500.0 * (3450.0 * (1.0 / (t_c + 273.15) - 1.0 / 293.15)).exp();
    5.0 * r / (r + 2490.0)
}

/// Sensor channels, in ecu_io's order.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Ch {
    Clt,
    Oil,
    Rail,
    Boost,
    Egr,
    V5,
}

pub struct Engine {
    pub theta: f64, // cycle angle, deg
    pub omega: f64, // rad/s
    pub rail_bar: f64,
    pub clt_c: f64,
    pub duty: f64, // metering duty from the ECU
    pub load_kw: f64,
    pub starter: bool,
    pub net_torque: f64,
    /// Runaway: fuel regardless of commands, per cylinder.
    pub stuck_fuel: [Option<f64>; NCYL],
    pub fuel: [f64; NCYL], // mg delivered for each cylinder's coming stroke
    pub cmd: [Option<(u64, u32)>; NCYL], // (start_us, dur_us) not yet finished
    seq: [u32; NCYL],
    now: u64,
}

impl Default for Engine {
    fn default() -> Self {
        Self::new()
    }
}

impl Engine {
    pub fn new() -> Self {
        Engine {
            theta: 0.0,
            omega: 0.0,
            rail_bar: 0.0,
            clt_c: 80.0,
            duty: 0.0,
            load_kw: 0.0,
            starter: false,
            net_torque: 0.0,
            stuck_fuel: [None; NCYL],
            fuel: [0.0; NCYL],
            cmd: [None; NCYL],
            seq: [0; NCYL],
            now: 0,
        }
    }

    pub fn rpm(&self) -> f64 {
        self.omega / RPM
    }

    /// Act on a new seq: latch a command, or (dur 0) cancel one not yet
    /// started. Times are the firmware's (u32, wrapping); each is taken as
    /// the u64 time nearest the plant's own.
    pub fn command(&mut self, cyl: usize, start_us: u32, dur_us: u32, seq: u32) {
        if seq == self.seq[cyl] {
            return;
        }
        self.seq[cyl] = seq;
        let back = (self.now as u32).wrapping_sub(start_us) as i32 as i64;
        let start = (self.now as i64 - back) as u64;
        if dur_us != 0 {
            self.cmd[cyl] = Some((start, dur_us));
        } else if matches!(self.cmd[cyl], Some((s, _)) if self.now < s) {
            self.cmd[cyl] = None;
        }
    }

    /// Forget commands and their seq, as a power cycle does.
    pub fn clear_commands(&mut self) {
        self.cmd = [None; NCYL];
        self.seq = [0; NCYL];
    }

    /// Advance one step from t_us; appends (time, is_cam) for each edge.
    pub fn step(&mut self, t_us: u64, dt_us: u32, edges: &mut Vec<(u64, bool)>) {
        self.now = t_us;
        let dt = dt_us as f64 * 1e-6;
        let t_end = t_us + dt_us as u64;
        let rpm = self.rpm();
        let flow = INJ_K * self.rail_bar.max(0.0).sqrt(); // mg/us while open
        let mut q_inj = 0.0;
        let mut torque = 0.0;
        for k in 0..NCYL {
            let phase = (self.theta - TDC1 - 240.0 * k as f64).rem_euclid(720.0);
            if self.stuck_fuel[k].is_none() {
                if let Some((s, d)) = self.cmd[k] {
                    let lo = (t_us as f64).max(s as f64 + INJ_DEAD_US);
                    let hi = (t_end as f64).min((s + d as u64) as f64);
                    if hi > lo {
                        let mg = (hi - lo) * flow;
                        self.fuel[k] += mg;
                        q_inj += mg;
                    }
                    if t_end >= s + d as u64 {
                        self.cmd[k] = None;
                    }
                }
            }
            if phase < 180.0 {
                torque += WORK_PER_MG * self.fuel[k] / PI;
            }
        }
        torque += COMP_T * ((self.theta - TDC1).rem_euclid(240.0) * 1.5).to_radians().sin();
        if self.starter {
            torque += (STARTER_T * (1.0 - rpm / STARTER_NOLOAD)).max(0.0);
        }
        torque -= if self.omega > 0.0 { friction(rpm) } else { 0.0 };
        let roll = (rpm / AVR_KNEE_RPM).min(1.0).powi(2);
        torque -= self.load_kw * roll * 1000.0 / GEN_EFF / self.omega.max(50.0);
        self.net_torque = torque;
        self.omega = (self.omega + torque / J * dt).max(0.0);

        // angle, edges, per-cylinder fuel bookkeeping
        let old = self.theta;
        let new = old + (self.omega * dt).to_degrees();
        let span = new - old;
        if span > 0.0 {
            let mut n = (old / 6.0).floor() as i64 + 1;
            while (n * 6) as f64 <= new {
                let a = n * 6;
                if a % 360 < 348 {
                    edges.push((t_us + ((a as f64 - old) / span * dt_us as f64).round_ties_even() as u64, false));
                }
                n += 1;
            }
            let c = ((old - CAM_DEG) / 720.0).floor() + 1.0;
            if CAM_DEG + 720.0 * c <= new {
                edges.push((t_us + ((CAM_DEG + 720.0 * c - old) / span * dt_us as f64).round_ties_even() as u64, true));
            }
        }
        for k in 0..NCYL {
            let tdc = TDC1 + 240.0 * k as f64;
            let (p_old, p_new) = ((old - tdc).rem_euclid(720.0), (new - tdc).rem_euclid(720.0));
            if p_old < 180.0 && 180.0 <= p_new {
                self.fuel[k] = 0.0; // power stroke over
            }
            if p_new < p_old {
                if let Some(mg) = self.stuck_fuel[k] {
                    self.fuel[k] = mg; // runaway: fuel regardless
                }
            }
        }
        self.theta = new.rem_euclid(720.0);

        // rail
        let opening = if METER_NC { self.duty } else { 1.0 - self.duty };
        let q = PUMP * rpm * opening - q_inj * CM3_PER_MG / dt - LEAK * self.rail_bar;
        self.rail_bar = (self.rail_bar + BAR_PER_CM3 * q * dt).max(0.0).min(RELIEF);

        // coolant towards a load-dependent temperature, tau 60 s
        let target = 75.0 + 15.0 * self.load_kw / 20.0;
        self.clt_c += (target - self.clt_c) * dt / 60.0;
    }

    /// Sensor volts, indexed by `Ch as usize`.
    pub fn volts(&self) -> [f64; 6] {
        let load = self.load_kw / 20.0;
        [
            ntc_volts(self.clt_c),
            lin(400.0 * self.rpm() / 1500.0, 0.0, 1000.0),
            lin(self.rail_bar, 0.0, 1800.0),
            lin(100.0 + 100.0 * load, 50.0, 400.0),
            lin(0.0, 0.0, 100.0),
            5.0,
        ]
    }
}
