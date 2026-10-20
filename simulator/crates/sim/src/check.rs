//! `expect` checks (spec section 5), evaluated on a finished run.
use crate::j1939::{dtcs, lamps, DM1, DM2};
use crate::seq::num;
use crate::sim::{Row, SHUTDOWN, STATES};
use crate::{nvm, Sim};

#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Sig { Rpm, EcuRpm, Rail, RailErr, Duty, Fuel, Clt, Oil, Load }

#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Stat { Mean, Min, Max }

/// Inclusive; either end may be open.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Band(pub Option<f64>, pub Option<f64>);

/// SPN and FMI; FMI None is `*`, any.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Dtc(pub u32, pub Option<u8>);

#[derive(Clone, Debug, PartialEq)]
pub enum Check {
    Stat { sig: Sig, stat: Stat, band: Band, win: (f64, f64) },
    Change { sig: Sig, band: Band, a: (f64, f64), b: (f64, f64) },
    Dm1Within { dtc: Dtc, s: f64, t: f64 },
    NeverDm1(Dtc),
    Dm1Clear((f64, f64)),
    Lamp { lamps: u8, dtc: Dtc },
    TripWithin { ms: f64, t: f64 },
    NoTrip,
    StateAtEnd(u8),
    Stored(Dtc),
    NotStored(Dtc),
    Dm2 { dtc: Option<Dtc>, after: f64 }, // None: empty
}

#[derive(Clone, Debug, PartialEq)]
pub struct Outcome {
    pub line: usize,
    pub text: String,
    pub found: String,
    pub pass: bool,
}

const SIGS: [(&str, Sig); 9] = [
    ("rpm", Sig::Rpm), ("ecu_rpm", Sig::EcuRpm), ("rail", Sig::Rail), ("rail_err", Sig::RailErr),
    ("duty", Sig::Duty), ("fuel", Sig::Fuel), ("clt", Sig::Clt), ("oil", Sig::Oil), ("load", Sig::Load),
];
const LAMPS: [(&str, u8); 4] = [("red", 0x10), ("amber", 0x04), ("protect", 0x01), ("mil", 0x40)];

fn band(s: &str) -> Result<Band, String> {
    let (lo, hi) = s.split_once("..").ok_or_else(|| format!("a band is lo..hi: {s}"))?;
    let end = |x: &str| if x.is_empty() { Ok(None) } else { num(x).map(Some) };
    let b = Band(end(lo)?, end(hi)?);
    if b.0.is_none() && b.1.is_none() {
        return Err("a band needs at least one end".into());
    }
    Ok(b)
}

fn win(s: &str) -> Result<(f64, f64), String> {
    match band(s) {
        Ok(Band(Some(a), Some(b))) if a < b => Ok((a, b)),
        _ => Err(format!("a window is t0..t1 in seconds, t0 < t1: {s}")),
    }
}

fn dtc(s: &str) -> Result<Dtc, String> {
    let bad = || format!("a DTC is spn/fmi or spn/*: {s}");
    let (spn, fmi) = s.split_once('/').ok_or_else(bad)?;
    let spn = spn.parse().map_err(|_| bad())?;
    let fmi = if fmi == "*" { None } else { Some(fmi.parse::<u8>().ok().filter(|&f| f < 32).ok_or_else(bad)?) };
    Ok(Dtc(spn, fmi))
}

/// The text after `expect`.
pub fn parse(text: &str) -> Result<Check, String> {
    let t: Vec<&str> = text.split_whitespace().collect();
    let sig = |s: &str| SIGS.iter().find(|x| x.0 == s).map(|x| x.1);
    Ok(match t.as_slice() {
        [s, "mean", "change", b, "from", a0, "to", b0] if sig(s).is_some() =>
            Check::Change { sig: sig(s).unwrap(), band: band(b)?, a: win(a0)?, b: win(b0)? },
        [s, st, b, "over", w] if sig(s).is_some() => Check::Stat {
            sig: sig(s).unwrap(),
            stat: match *st {
                "mean" => Stat::Mean,
                "min" => Stat::Min,
                "max" => Stat::Max,
                _ => return Err(format!("mean, min or max, not {st}")),
            },
            band: band(b)?,
            win: win(w)?,
        },
        ["dm1", "clear", "over", w] => Check::Dm1Clear(win(w)?),
        ["dm1", d, "within", s, "of", t] => Check::Dm1Within { dtc: dtc(d)?, s: num(s)?, t: num(t)? },
        ["never", "dm1", d] => Check::NeverDm1(dtc(d)?),
        ["lamp", names, "with", d] => {
            let mut m = 0;
            for n in names.split('+') {
                m |= LAMPS.iter().find(|x| x.0 == n).ok_or_else(|| format!("lamps: red amber protect mil, not {n}"))?.1;
            }
            Check::Lamp { lamps: m, dtc: dtc(d)? }
        }
        ["trip", "within", ms, "ms", "of", t] => Check::TripWithin { ms: num(ms)?, t: num(t)? },
        ["no", "trip"] => Check::NoTrip,
        ["state", s, "at", "end"] => Check::StateAtEnd(
            STATES.iter().position(|x| x == s).ok_or_else(|| format!("state is one of {}", STATES.join(" ")))? as u8),
        ["stored", d] => Check::Stored(dtc(d)?),
        ["not", "stored", d] => Check::NotStored(dtc(d)?),
        ["dm2", "empty", "after", t] => Check::Dm2 { dtc: None, after: num(t)? },
        ["dm2", d, "after", t] => Check::Dm2 { dtc: Some(dtc(d)?), after: num(t)? },
        _ => return Err(format!("unknown check: expect {text}")),
    })
}

fn value(sig: Sig, r: &Row) -> f64 {
    match sig {
        Sig::Rpm => r.rpm,
        Sig::EcuRpm => r.ecu_rpm as f64,
        Sig::Rail => r.rail,
        Sig::RailErr => if r.rail_set == 0.0 { 0.0 } else { r.rail / r.rail_set as f64 - 1.0 },
        Sig::Duty => r.duty as f64,
        Sig::Fuel => r.fuel as f64,
        Sig::Clt => r.clt,
        Sig::Oil => r.oil as f64,
        Sig::Load => r.load,
    }
}

fn stat(sim: &Sim, sig: Sig, st: Stat, (t0, t1): (f64, f64)) -> Option<f64> {
    let xs: Vec<f64> = sim.trace.iter()
        .filter(|r| { let t = r.t_ms as f64 / 1000.0; t0 <= t && t < t1 })
        .map(|r| value(sig, r))
        .collect();
    if xs.is_empty() {
        return None;
    }
    Some(match st {
        Stat::Mean => xs.iter().sum::<f64>() / xs.len() as f64,
        Stat::Min => xs.iter().cloned().fold(f64::INFINITY, f64::min),
        Stat::Max => xs.iter().cloned().fold(f64::NEG_INFINITY, f64::max),
    })
}

fn inside(b: Band, x: f64) -> bool {
    b.0.is_none_or(|lo| x >= lo) && b.1.is_none_or(|hi| x <= hi)
}

fn has(d: Dtc, list: &[(u32, u8)]) -> bool {
    list.iter().any(|&(s, f)| s == d.0 && d.1.is_none_or(|x| x == f))
}

/// DM1s as (seconds, dtcs, lamps).
fn dm1s(sim: &Sim) -> impl Iterator<Item = (f64, Vec<(u32, u8)>, u8)> + '_ {
    sim.msgs.iter().filter(|m| m.pgn == DM1).map(|m| (m.t_ms as f64 / 1000.0, dtcs(&m.data), lamps(&m.data)))
}

fn at(t: f64) -> String {
    format!("at {t} s")
}

pub fn evaluate(checks: &[(usize, String, Check)], sim: &Sim) -> Vec<Outcome> {
    checks.iter().map(|(line, text, c)| {
        let (found, pass) = one(c, sim);
        Outcome { line: *line, text: text.clone(), found, pass }
    }).collect()
}

fn one(c: &Check, sim: &Sim) -> (String, bool) {
    let none = || ("none".to_string(), false);
    match *c {
        Check::Stat { sig, stat: st, band, win } => match stat(sim, sig, st, win) {
            Some(x) => (format!("{x:.4}"), inside(band, x)),
            None => ("no samples in the window".into(), false),
        },
        Check::Change { sig, band, a, b } => match (stat(sim, sig, Stat::Mean, a), stat(sim, sig, Stat::Mean, b)) {
            (Some(x), Some(y)) => (format!("{:.4}", y - x), inside(band, y - x)),
            _ => ("no samples in a window".into(), false),
        },
        Check::Dm1Within { dtc, s, t } => match dm1s(sim).find(|(tm, d, _)| *tm > t && has(dtc, d)) {
            Some((tm, ..)) => (at(tm), tm <= t + s),
            None => none(),
        },
        Check::NeverDm1(dtc) => match dm1s(sim).find(|(_, d, _)| has(dtc, d)) {
            Some((tm, ..)) => (at(tm), false),
            None => ("never".into(), true),
        },
        Check::Dm1Clear((t0, t1)) => {
            let w: Vec<_> = dm1s(sim).filter(|(t, ..)| t0 <= *t && *t < t1).collect();
            match w.iter().find(|(_, d, _)| !d.is_empty()) {
                Some((t, d, _)) => (format!("{d:?} {}", at(*t)), false),
                None if w.is_empty() => ("no DM1 in the window".into(), false),
                None => (format!("{} DM1s, all clear", w.len()), true),
            }
        }
        Check::Lamp { lamps: want, dtc } => match dm1s(sim).find(|(_, d, _)| has(dtc, d)) {
            Some((_, _, l)) => (format!("{l:#04x}"), l == want),
            None => ("DTC never on DM1".into(), false),
        },
        Check::TripWithin { ms, t } => {
            match sim.states.iter().find(|&&(tu, st)| st == SHUTDOWN && tu as f64 / 1e6 > t) {
                Some(&(tu, _)) => {
                    let after = (tu as f64 / 1e6 - t) * 1000.0;
                    (format!("after {after:.1} ms"), after <= ms)
                }
                None => none(),
            }
        }
        Check::NoTrip => match sim.states.iter().find(|s| s.1 == SHUTDOWN) {
            Some(&(tu, _)) => (format!("SHUTDOWN {}", at(tu as f64 / 1e6)), false),
            None => ("never".into(), true),
        },
        Check::StateAtEnd(s) => {
            let got = sim.io.state;
            (STATES.get(got as usize).unwrap_or(&"?").to_string(), got == s)
        }
        Check::Stored(dtc) | Check::NotStored(dtc) => {
            let want = matches!(c, Check::Stored(_));
            match nvm::stored(&sim.slots) {
                Some(st) => (format!("{st:?}"), has(dtc, &st) == want),
                None => ("no valid slot".into(), !want),
            }
        }
        Check::Dm2 { dtc, after } => {
            match sim.msgs.iter().find(|m| m.pgn == DM2 && m.t_ms as f64 / 1000.0 > after) {
                Some(m) => {
                    let d = dtcs(&m.data);
                    let ok = match dtc { Some(x) => has(x, &d), None => d.is_empty() };
                    (format!("{d:?} {}", at(m.t_ms as f64 / 1000.0)), ok)
                }
                None => ("no DM2".into(), false),
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::j1939::Msg;
    use crate::{Firmware, Row};

    /// A Sim with a hand-made record: rpm ramps 1000 + t_ms for 10 s,
    /// a DM1 with 190/18 (amber) at 4 s, a clear one at 6 s, SHUTDOWN at
    /// 7.05 s, a DM2 with 110/3 at 8 s.
    fn record() -> Sim {
        let mut s = Sim::new(Firmware::bundled());
        s.trace = (1..=10_000u64).map(|t| Row { t_ms: t, rpm: 1000.0 + t as f64, rail: 1000.0, rail_set: 1000.0, ..Default::default() }).collect();
        s.msgs = vec![
            Msg { t_ms: 4000, pgn: DM1, data: vec![0x04, 0xFF, 190, 0, 18, 1] },
            Msg { t_ms: 6000, pgn: DM1, data: vec![0, 0xFF, 0, 0, 0, 0] },
            Msg { t_ms: 8000, pgn: DM2, data: vec![0, 0xFF, 110, 0, 3, 1] },
        ];
        s.states = vec![(7_050_000, SHUTDOWN)];
        s
    }

    fn check(text: &str, s: &Sim) -> bool {
        let c = parse(text.strip_prefix("expect ").unwrap()).unwrap();
        evaluate(&[(1, text.into(), c)], s)[0].pass
    }

    #[test]
    fn each_check_passes_and_fails() {
        let s = record();
        for (good, bad) in [
            ("expect rpm mean 4998..5000 over 2.999..5", "expect rpm mean 0..1 over 3..5"),
            ("expect rpm min 3000.. over 2..3", "expect rpm max ..1500 over 2..3"),
            ("expect rail_err max ..0.01 over 0..10", "expect rail_err min 0.5.. over 0..10"),
            ("expect rpm mean change 999..1001 from 1..2 to 2..3", "expect rpm mean change -75..-45 from 1..2 to 2..3"),
            ("expect dm1 190/18 within 1 of 3.5", "expect dm1 190/18 within 0.2 of 3.5"),
            ("expect never dm1 110/3", "expect never dm1 190/18"),
            ("expect dm1 clear over 5..7", "expect dm1 clear over 3..7"),
            ("expect lamp amber with 190/18", "expect lamp red+protect with 190/18"),
            ("expect trip within 100 ms of 7", "expect trip within 10 ms of 7"),
            ("expect dm2 110/3 after 7", "expect dm2 empty after 7"),
            ("expect not stored 190/0", "expect stored 190/0"),
            ("expect state OFF at end", "expect state RUN at end"),
        ] {
            assert!(check(good, &s), "should pass: {good}");
            assert!(!check(bad, &s), "should fail: {bad}");
        }
        assert!(!check("expect no trip", &s));
        let mut quiet = s;
        quiet.states.clear();
        assert!(check("expect no trip", &quiet));
    }

    #[test]
    fn change_check() {
        let mut s = record();
        for r in s.trace.iter_mut() {
            r.rpm = if r.t_ms < 5000 { 1500.0 } else { 1440.0 };
        }
        assert!(check("expect rpm mean change -75..-45 from 1..2 to 6..7", &s));
    }

    #[test]
    fn fmi_wildcard() {
        let mut s = record();
        s.msgs.push(Msg { t_ms: 9000, pgn: DM1, data: vec![0x11, 0xFF, 0x7C, 0x02, 2, 1] }); // 636/2
        assert!(check("expect dm1 636/* within 1 of 8.5", &s));
        assert!(!check("expect dm1 636/3 within 1 of 8.5", &s));
    }

    #[test]
    fn bad_checks() {
        for t in ["rpm mean 1..2 over 3", "rpm avg 1..2 over 1..2", "dm1 190 within 1 of 2", "lamp blue with 1/2", "state FLYING at end"] {
            assert!(parse(t).is_err(), "{t}");
        }
    }
}
