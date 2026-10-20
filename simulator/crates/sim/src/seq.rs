//! `.seq` scripts (spec section 5): timed actions, `end`, and checks.
use crate::check::{evaluate, Check, Outcome};
use crate::{Firmware, Sim};
use plant::{Ch, SensorFault};
use std::fmt;
use std::sync::Arc;

#[derive(Clone, Copy, Debug, PartialEq)]
pub enum SensorCmd {
    Open,
    Short,
    Short5v,
    Volts(f64),
    Offset(f64),
    Stuck,
    Clear,
}

#[derive(Clone, Debug, PartialEq)]
pub enum Action {
    Start,
    Starter(bool),
    Load(f64),
    Ignition(bool),
    IgnitionBounce(u32), // ms off, then on
    Droop(bool),
    Sensor(Ch, SensorCmd),
    CrankLost,
    CrankRestore,
    CrankDrop(u32),
    CrankExtra(u32),
    CamLost,
    CamRestore,
    FuelStuck(f64, Option<usize>), // mg; one cylinder (1-3) or all
    FuelFree,
    Leak(f64),
    Request(&'static str), // dm2, dm3, dm4, hours
    PowerCycle,
    TearNextSave,
}

pub const CHANNELS: [(&str, Ch); 6] = [
    ("clt", Ch::Clt), ("oil", Ch::Oil), ("rail", Ch::Rail),
    ("boost", Ch::Boost), ("egr", Ch::Egr), ("5v", Ch::V5),
];

fn ch_name(c: Ch) -> &'static str {
    CHANNELS.iter().find(|x| x.1 == c).unwrap().0
}

fn on(b: bool) -> &'static str {
    if b { "on" } else { "off" }
}

impl fmt::Display for Action {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        use Action::*;
        match self {
            Start => write!(f, "start"),
            Starter(b) => write!(f, "starter {}", on(*b)),
            Load(kw) => write!(f, "load {kw}"),
            Ignition(b) => write!(f, "ignition {}", on(*b)),
            IgnitionBounce(ms) => write!(f, "ignition bounce {ms}"),
            Droop(b) => write!(f, "droop {}", on(*b)),
            Sensor(c, cmd) => {
                write!(f, "sensor {} ", ch_name(*c))?;
                match cmd {
                    SensorCmd::Open => write!(f, "open"),
                    SensorCmd::Short => write!(f, "short"),
                    SensorCmd::Short5v => write!(f, "short5v"),
                    SensorCmd::Volts(v) => write!(f, "volts {v}"),
                    SensorCmd::Offset(v) => write!(f, "offset {v}"),
                    SensorCmd::Stuck => write!(f, "stuck"),
                    SensorCmd::Clear => write!(f, "clear"),
                }
            }
            CrankLost => write!(f, "crank lost"),
            CrankRestore => write!(f, "crank restore"),
            CrankDrop(n) => write!(f, "crank drop {n}"),
            CrankExtra(n) => write!(f, "crank extra {n}"),
            CamLost => write!(f, "cam lost"),
            CamRestore => write!(f, "cam restore"),
            FuelStuck(mg, None) => write!(f, "fuel stuck {mg}"),
            FuelStuck(mg, Some(k)) => write!(f, "fuel stuck {mg} cyl {k}"),
            FuelFree => write!(f, "fuel free"),
            Leak(x) => write!(f, "leak {x}"),
            Request(r) => write!(f, "request {r}"),
            PowerCycle => write!(f, "power cycle"),
            TearNextSave => write!(f, "tear next save"),
        }
    }
}

pub struct Script {
    pub name: String,
    pub actions: Vec<(u64, Action)>, // t_us
    pub end_us: u64,
    pub checks: Vec<(usize, String, Check)>, // line, text, check
}

pub(crate) fn num(s: &str) -> Result<f64, String> {
    s.parse::<f64>().ok().filter(|x| x.is_finite()).ok_or_else(|| format!("not a number: {s}"))
}

fn count(s: &str) -> Result<u32, String> {
    s.parse::<u32>().map_err(|_| format!("not a whole number: {s}"))
}

fn not_neg(s: &str) -> Result<f64, String> {
    let x = num(s)?;
    if x < 0.0 { Err(format!("must not be negative: {s}")) } else { Ok(x) }
}

/// One action, without its time: a script line's tail, or a live control.
pub fn parse_action(text: &str) -> Result<Action, String> {
    use Action::*;
    let t: Vec<&str> = text.split_whitespace().collect();
    let sw = |s: &str| match s {
        "on" => Ok(true),
        "off" => Ok(false),
        _ => Err(format!("expected on or off, got {s}")),
    };
    Ok(match t.as_slice() {
        ["start"] => Start,
        ["starter", b] => Starter(sw(b)?),
        ["load", kw] => Load(not_neg(kw)?),
        ["ignition", "bounce", ms] => IgnitionBounce(count(ms)?),
        ["ignition", b] => Ignition(sw(b)?),
        ["droop", b] => Droop(sw(b)?),
        ["sensor", c, rest @ ..] => {
            let ch = CHANNELS.iter().find(|x| x.0 == *c).map(|x| x.1)
                .ok_or_else(|| format!("unknown sensor {c}: one of clt oil rail boost egr 5v"))?;
            Sensor(ch, match rest {
                ["open"] => SensorCmd::Open,
                ["short"] => SensorCmd::Short,
                ["short5v"] => SensorCmd::Short5v,
                ["stuck"] => SensorCmd::Stuck,
                ["clear"] => SensorCmd::Clear,
                ["volts", v] => SensorCmd::Volts(num(v)?),
                ["offset", v] => SensorCmd::Offset(num(v)?),
                _ => return Err("sensor: open, short, short5v, volts V, offset V, stuck or clear".into()),
            })
        }
        ["crank", "lost"] => CrankLost,
        ["crank", "restore"] => CrankRestore,
        ["crank", "drop", n] => CrankDrop(count(n)?),
        ["crank", "extra", n] => CrankExtra(count(n)?),
        ["cam", "lost"] => CamLost,
        ["cam", "restore"] => CamRestore,
        ["fuel", "stuck", mg] => FuelStuck(not_neg(mg)?, None),
        ["fuel", "stuck", mg, "cyl", k] => {
            let k = count(k)? as usize;
            if !(1..=3).contains(&k) {
                return Err("cylinder is 1, 2 or 3".into());
            }
            FuelStuck(not_neg(mg)?, Some(k))
        }
        ["fuel", "free"] => FuelFree,
        ["leak", x] => Leak(not_neg(x)?),
        ["request", r] => Request(match *r {
            "dm2" => "dm2",
            "dm3" => "dm3",
            "dm4" => "dm4",
            "hours" => "hours",
            _ => return Err(format!("request dm2, dm3, dm4 or hours, not {r}")),
        }),
        ["power", "cycle"] => PowerCycle,
        ["tear", "next", "save"] => TearNextSave,
        [] => return Err("empty".into()),
        _ => return Err(format!("unknown action: {text}")),
    })
}

/// Seconds as a script writes them.
pub fn secs(t_us: u64) -> String {
    format!("{}", t_us as f64 / 1e6)
}

/// Every error, with its line number (from 1).
pub fn parse(name: &str, text: &str) -> Result<Script, Vec<(usize, String)>> {
    let text = text.strip_prefix('\u{feff}').unwrap_or(text);
    let (mut actions, mut checks, mut errs) = (vec![], vec![], vec![]);
    let (mut end, mut last) = (None::<u64>, 0u64);
    for (i, raw) in text.lines().enumerate() {
        let n = i + 1;
        let line = raw.split('#').next().unwrap().trim();
        if line.is_empty() {
            continue;
        }
        if let Some(rest) = line.strip_prefix("expect ") {
            match crate::check::parse(rest) {
                Ok(c) => checks.push((n, line.to_string(), c)),
                Err(e) => errs.push((n, e)),
            }
            continue;
        }
        let (t, rest) = line.split_once(char::is_whitespace).unwrap_or((line, ""));
        let t = match num(t) {
            Ok(t) if t >= 0.0 => (t * 1e6).round() as u64,
            _ => {
                errs.push((n, format!("a line starts with a time in seconds or `expect`: {line}")));
                continue;
            }
        };
        if end.is_some() {
            errs.push((n, "action after `end`".into()));
            continue;
        }
        if t < last {
            errs.push((n, format!("time goes backwards: {} after {}", secs(t), secs(last))));
            continue;
        }
        last = t;
        if rest.trim() == "end" {
            end = Some(t);
            continue;
        }
        match parse_action(rest) {
            Ok(a) => actions.push((t, a)),
            Err(e) => errs.push((n, e)),
        }
    }
    if end.is_none() {
        errs.push((text.lines().count().max(1), "no `end` line".into()));
    }
    if !errs.is_empty() {
        return Err(errs);
    }
    Ok(Script { name: name.to_string(), actions, end_us: end.unwrap(), checks })
}

impl Sim {
    /// Apply an action now, and record it as a script line.
    pub fn apply(&mut self, a: &Action) {
        use Action::*;
        let e = &mut self.eng;
        match a {
            Start => {
                e.starter = true;
                self.release_on_run = true;
            }
            Starter(b) => {
                e.starter = *b;
                self.release_on_run = false;
            }
            Load(kw) => e.load_kw = *kw,
            Ignition(b) => {
                self.io.ignition = *b as u8;
                self.bounce_until = None;
            }
            IgnitionBounce(ms) => {
                self.io.ignition = 0;
                self.bounce_until = Some(self.t_us + *ms as u64 * 1000);
            }
            Droop(b) => self.io.droop_sw = *b as u8,
            Sensor(c, cmd) => match cmd {
                SensorCmd::Stuck => e.stick(*c),
                _ => e.sensor[*c as usize] = match cmd {
                    SensorCmd::Open => SensorFault::Open,
                    SensorCmd::Short => SensorFault::Short,
                    SensorCmd::Short5v => SensorFault::Short5v,
                    SensorCmd::Volts(v) => SensorFault::Volts(*v),
                    SensorCmd::Offset(v) => SensorFault::Offset(*v),
                    _ => SensorFault::None,
                },
            },
            CrankLost => e.crank_lost = true,
            CrankRestore => {
                e.crank_lost = false;
                e.crank_drop = 0;
                e.crank_extra = 0;
            }
            CrankDrop(n) => e.crank_drop += n,
            CrankExtra(n) => e.crank_extra += n,
            CamLost => e.cam_lost = true,
            CamRestore => e.cam_lost = false,
            FuelStuck(mg, None) => e.stuck_fuel = [Some(*mg); 3],
            FuelStuck(mg, Some(k)) => e.stuck_fuel[k - 1] = Some(*mg),
            FuelFree => e.stuck_fuel = [None; 3],
            Leak(x) => e.leak = *x,
            Request(r) => {
                use crate::j1939::*;
                let pgn = match *r { "dm2" => DM2, "dm3" => DM3, "dm4" => DM4, _ => HOURS };
                self.request(pgn);
            }
            PowerCycle => self.power_cycle(),
            TearNextSave => self.tear_next = true,
        }
        self.events.push(format!("{} {a}", secs(self.t_us)));
    }
}

/// Run a script on this firmware to its end, then evaluate its checks.
pub fn run(fw: Arc<Firmware>, s: &Script) -> (Sim, Vec<Outcome>) {
    let mut sim = Sim::new(fw);
    let mut next = 0;
    loop {
        while next < s.actions.len() && s.actions[next].0 <= sim.t_us {
            sim.apply(&s.actions[next].1);
            next += 1;
        }
        if sim.t_us >= s.end_us {
            break;
        }
        sim.step_ms();
    }
    sim.events.push(format!("{} end", secs(s.end_us)));
    let out = evaluate(&s.checks, &sim);
    (sim, out)
}

#[cfg(test)]
mod tests {
    use super::*;

    const ALL: &str = "start\nstarter on\nstarter off\nload 20\nignition on\nignition off\n\
ignition bounce 300\ndroop on\nsensor clt open\nsensor oil short\nsensor rail short5v\n\
sensor boost volts 2.2\nsensor egr offset 0.3\nsensor 5v stuck\nsensor clt clear\ncrank lost\n\
crank restore\ncrank drop 2\ncrank extra 1\ncam lost\ncam restore\nfuel stuck 80\n\
fuel stuck 5 cyl 2\nfuel free\nleak 10\nrequest dm2\nrequest dm3\nrequest dm4\nrequest hours\n\
power cycle\ntear next save";

    #[test]
    fn parse_all_actions() {
        for l in ALL.lines() {
            let a = parse_action(l).unwrap_or_else(|e| panic!("{l}: {e}"));
            assert_eq!(a.to_string(), l);
        }
        let text: String = ALL.lines().map(|l| format!("1 {l}\n")).collect::<String>() + "2 end\n";
        let s = parse("all", &text).unwrap();
        assert_eq!((s.actions.len(), s.end_us), (ALL.lines().count(), 2_000_000));
    }

    #[test]
    fn parse_crlf_bom_and_errors() {
        let s = parse("w", "\u{feff}# notepad\r\n0 start\r\n8 load 20  # step\r\n13 end\r\nexpect no trip\r\n").unwrap();
        assert_eq!(s.actions, vec![(0, Action::Start), (8_000_000, Action::Load(20.0))]);
        assert_eq!(s.checks.len(), 1);

        let e = parse("bad", "0 start\n5 load 1\n4 load 2\n6 sensor xyz open\n7 foo\n\
expect rpm mean 1..2 over 3\n8 end\n9 load 3\n").err().unwrap();
        let lines: Vec<usize> = e.iter().map(|x| x.0).collect();
        assert_eq!(lines, vec![3, 4, 5, 6, 8], "{e:?}");
        assert!(e[0].1.contains("backwards"));
        assert!(e[1].1.contains("xyz"));
        assert!(e[4].1.contains("after `end`"));

        let e = parse("noend", "0 start\n").err().unwrap();
        assert!(e[0].1.contains("end"));
    }
}
