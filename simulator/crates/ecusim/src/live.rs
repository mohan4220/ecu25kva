//! The live runner: one thread owns the Sim, takes commands, paces
//! simulated time against the wall clock, and publishes what happens as
//! Server-Sent Events text to every subscriber.

use crate::runs;
use serde_json::{json, Value};
use sim::check::{evaluate, Outcome};
use sim::j1939::{self, dtcs, lamps, pgn, DM1};
use sim::seq::{self, secs, Script};
use sim::{Firmware, Sim};
use std::collections::VecDeque;
use std::path::PathBuf;
use std::sync::{mpsc, Arc, Mutex};
use std::time::{Duration, Instant};

pub enum Cmd {
    Line(String), // one action, applied now
    Script(Script),
    Run,
    Pause,
    Stop,
    Reset,
    Speed(Option<f64>), // None: as fast as it goes
    Firmware(Arc<Firmware>),
}

/// Subscribers to the event stream; a subscriber whose receiver is gone
/// is dropped on the next publish.
#[derive(Default)]
pub struct Hub {
    subs: Mutex<Vec<mpsc::Sender<String>>>,
}

impl Hub {
    pub fn subscribe(&self) -> mpsc::Receiver<String> {
        let (tx, rx) = mpsc::channel();
        self.subs.lock().unwrap().push(tx);
        rx
    }

    pub fn publish(&self, event: &str, data: &Value) {
        let block = format!("event: {event}\ndata: {data}\n\n");
        self.subs.lock().unwrap().retain(|s| s.send(block.clone()).is_ok());
    }

    pub fn count(&self) -> usize {
        self.subs.lock().unwrap().len()
    }
}

#[derive(Clone, Copy, PartialEq)]
enum Mode {
    Stopped,
    Running,
    Paused,
}

struct Live {
    fw: Arc<Firmware>,
    runs_dir: PathBuf,
    hub: Arc<Hub>,
    sim: Option<Sim>,
    script: Option<Script>,
    next: usize, // the script's next action
    name: String,
    mode: Mode,
    speed: Option<f64>,
    anchor: (Instant, u64), // pacing: wall time and sim time at the last change
    reached: VecDeque<(Instant, u64)>,
    last_pub: Instant,
    sent: (usize, usize, usize, usize), // rows, can frames, events, DM1s already published
}

const CHUNK_MS: u32 = 10;
const PUB_EVERY: Duration = Duration::from_millis(50);
const ROW_EVERY_MS: u64 = 10;

impl Live {
    fn session(&mut self, name: &str, script: Option<Script>) {
        self.finish();
        self.sim = Some(Sim::new(self.fw.clone()));
        self.script = script;
        self.next = 0;
        self.name = name.to_string();
        self.sent = (0, 0, 0, 0);
        self.mode = Mode::Running;
        self.re_anchor();
    }

    fn re_anchor(&mut self) {
        let t = self.sim.as_ref().map_or(0, |s| s.t_us);
        self.anchor = (Instant::now(), t);
        self.reached.clear();
    }

    /// End the run: checks, run folder, report. The sim is dropped, which
    /// frees the firmware for the next one.
    fn finish(&mut self) {
        let Some(mut sim) = self.sim.take() else { return };
        self.publish_new(&mut sim);
        let end = self.script.as_ref().map_or(sim.t_us, |s| s.end_us.min(sim.t_us));
        sim.events.push(format!("{} end", secs(end)));
        let outcomes: Vec<Outcome> = self.script.as_ref().map_or(vec![], |s| evaluate(&s.checks, &sim));
        let folder = match runs::write(&self.runs_dir, &self.name, &sim, &outcomes, &self.fw) {
            Ok(p) => p.display().to_string(),
            Err(e) => {
                self.hub.publish("error", &json!(format!("writing the run folder: {e}")));
                String::new()
            }
        };
        let out: Vec<Value> = outcomes.iter()
            .map(|o| json!({"line": o.line, "text": o.text, "found": o.found, "pass": o.pass}))
            .collect();
        self.hub.publish("report", &json!({"name": self.name, "outcomes": out, "folder": folder}));
        self.script = None;
        self.mode = Mode::Stopped;
        self.reached.clear(); // its samples belong to the run just ended
        self.publish_status();
    }

    fn command(&mut self, c: Cmd) {
        match c {
            Cmd::Line(text) => match seq::parse_action(&text) {
                Ok(a) => {
                    if self.sim.is_none() {
                        self.session("live", None);
                    }
                    self.sim.as_mut().unwrap().apply(&a);
                }
                Err(e) => self.hub.publish("error", &json!(format!("{text}: {e}"))),
            },
            Cmd::Script(s) => {
                let name = s.name.clone();
                self.session(&name, Some(s));
            }
            Cmd::Run => match self.mode {
                Mode::Stopped => self.session("live", None),
                _ => {
                    self.mode = Mode::Running;
                    self.re_anchor();
                }
            },
            Cmd::Pause => {
                if self.mode == Mode::Running {
                    self.mode = Mode::Paused;
                }
            }
            Cmd::Stop => self.finish(),
            Cmd::Reset => {
                self.sim = None;
                self.script = None;
                self.mode = Mode::Stopped;
                self.reached.clear();
            }
            Cmd::Speed(s) => {
                self.speed = s.filter(|x| *x > 0.0);
                self.re_anchor();
            }
            Cmd::Firmware(fw) => {
                self.finish();
                self.fw = fw;
            }
        }
        self.publish_status();
    }

    /// Ten simulated ms, then the script's end if it is due.
    fn chunk(&mut self) {
        let sim = self.sim.as_mut().unwrap();
        for _ in 0..CHUNK_MS {
            if let Some(s) = &self.script {
                while self.next < s.actions.len() && s.actions[self.next].0 <= sim.t_us {
                    sim.apply(&s.actions[self.next].1);
                    self.next += 1;
                }
                if sim.t_us >= s.end_us {
                    self.finish();
                    return;
                }
            }
            sim.step_ms();
        }
        if let Some(sp) = self.speed {
            let ahead = (sim.t_us - self.anchor.1) as f64 / 1e6 / sp;
            let due = self.anchor.0 + Duration::from_secs_f64(ahead);
            if let Some(wait) = due.checked_duration_since(Instant::now()) {
                std::thread::sleep(wait);
            }
        }
    }

    fn publish_new(&mut self, sim: &mut Sim) {
        let rows: Vec<Value> = sim.trace[self.sent.0..].iter().filter(|r| r.t_ms % ROW_EVERY_MS == 0)
            .map(|r| json!([r.t_ms, r.rpm, r.ecu_rpm, r.state, r.synced, r.rail, r.rail_set, r.duty,
                            r.fuel, r.load, r.clt, r.oil, r.wdg, r.starter as u8, r.ignition]))
            .collect();
        self.sent.0 = sim.trace.len();
        if !rows.is_empty() {
            self.hub.publish("rows", &json!(rows));
        }
        let new = &sim.can[self.sent.1..];
        let frames: Vec<Value> = new[new.len().saturating_sub(200)..].iter()
            .map(|f| json!({"t": f.t_ms, "dir": if f.rx { "rx" } else { "tx" }, "id": format!("{:08X}", f.id),
                            "data": f.data.iter().map(|b| format!("{b:02X}")).collect::<String>(),
                            "name": j1939::name(pgn(f.id))}))
            .collect();
        self.sent.1 = sim.can.len();
        if !frames.is_empty() {
            self.hub.publish("can", &json!(frames));
        }
        for e in &sim.events[self.sent.2..] {
            self.hub.publish("event", &json!(e));
        }
        self.sent.2 = sim.events.len();
        if let Some(m) = sim.msgs[self.sent.3..].iter().rev().find(|m| m.pgn == DM1) {
            let d: Vec<Value> = dtcs(&m.data).iter().map(|&(s, f)| json!([s, f])).collect();
            self.hub.publish("dm1", &json!({"t": m.t_ms, "dtcs": d, "lamps": lamps(&m.data)}));
        }
        self.sent.3 = sim.msgs.len();
    }

    fn publish_status(&mut self) {
        let t = self.sim.as_ref().map_or(0, |s| s.t_us);
        let now = Instant::now();
        self.reached.push_back((now, t));
        while self.reached.len() > 2 && now - self.reached[0].0 > Duration::from_secs(1) {
            self.reached.pop_front();
        }
        let (w0, t0) = self.reached[0];
        let wall = (now - w0).as_secs_f64();
        let reached = if wall > 0.2 { Some((t - t0) as f64 / 1e6 / wall) } else { None };
        let mode = match self.mode { Mode::Stopped => "stopped", Mode::Running => "running", Mode::Paused => "paused" };
        self.hub.publish("status", &json!({
            "t": t as f64 / 1e6, "speed": self.speed, "reached": reached, "mode": mode,
            "firmware": self.fw.name, "abi": self.fw.abi, "run": self.name,
        }));
    }

    fn tick_publish(&mut self) {
        if self.last_pub.elapsed() < PUB_EVERY {
            return;
        }
        self.last_pub = Instant::now();
        if let Some(mut sim) = self.sim.take() {
            self.publish_new(&mut sim);
            self.sim = Some(sim);
        }
        self.publish_status();
    }
}

/// Starts the live thread. It ends when every Sender is dropped.
pub fn spawn(fw: Arc<Firmware>, runs_dir: PathBuf) -> (mpsc::Sender<Cmd>, Arc<Hub>) {
    let (tx, rx) = mpsc::channel::<Cmd>();
    let hub = Arc::new(Hub::default());
    let mut live = Live {
        fw, runs_dir, hub: hub.clone(), sim: None, script: None, next: 0, name: "live".into(),
        mode: Mode::Stopped, speed: Some(1.0), anchor: (Instant::now(), 0), reached: VecDeque::new(),
        last_pub: Instant::now(), sent: (0, 0, 0, 0),
    };
    std::thread::spawn(move || loop {
        if live.mode == Mode::Running {
            loop {
                match rx.try_recv() {
                    Ok(c) => live.command(c),
                    Err(mpsc::TryRecvError::Empty) => break,
                    Err(mpsc::TryRecvError::Disconnected) => return,
                }
            }
            if live.mode == Mode::Running {
                live.chunk();
            }
        } else {
            match rx.recv_timeout(Duration::from_millis(100)) {
                Ok(c) => live.command(c),
                Err(mpsc::RecvTimeoutError::Timeout) => {}
                Err(mpsc::RecvTimeoutError::Disconnected) => return,
            }
        }
        live.tick_publish();
    });
    (tx, hub)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::Path;
    use std::sync::Mutex;
    use std::time::{Duration, Instant};

    // the live threads share the bundled firmware: one test at a time
    static ONE: Mutex<()> = Mutex::new(());

    fn tmp(name: &str) -> PathBuf {
        let d = std::env::temp_dir().join(format!("ecusim-live-{}-{name}", std::process::id()));
        let _ = std::fs::remove_dir_all(&d);
        d
    }

    /// (event, data) blocks until `until` returns true or 20 s pass.
    fn watch(rx: &mpsc::Receiver<String>, mut until: impl FnMut(&str, &serde_json::Value) -> bool) {
        let end = Instant::now() + Duration::from_secs(20);
        while Instant::now() < end {
            let Ok(block) = rx.recv_timeout(Duration::from_millis(500)) else { continue };
            let ev = block.lines().find_map(|l| l.strip_prefix("event: ")).unwrap_or("");
            let data = block.lines().find_map(|l| l.strip_prefix("data: ")).unwrap_or("null");
            if until(ev, &serde_json::from_str(data).unwrap()) {
                return;
            }
        }
        panic!("timed out");
    }

    fn sim_t(ev: &str, d: &serde_json::Value) -> Option<f64> {
        (ev == "status").then(|| d["t"].as_f64().unwrap())
    }

    #[test]
    fn pacing_1x() {
        let _one = ONE.lock().unwrap_or_else(|e| e.into_inner());
        let (tx, hub) = spawn(Firmware::bundled(), tmp("pace"));
        let rx = hub.subscribe();
        tx.send(Cmd::Speed(Some(1.0))).unwrap();
        tx.send(Cmd::Run).unwrap();
        let mut first = None;
        let mut took = 0.0;
        watch(&rx, |ev, d| {
            let Some(t) = sim_t(ev, d) else { return false };
            let (w0, t0) = *first.get_or_insert((Instant::now(), t));
            if t - t0 >= 2.0 {
                took = w0.elapsed().as_secs_f64() / (t - t0);
                return true;
            }
            false
        });
        assert!((0.95..=1.05).contains(&took), "wall per sim second {took}");
    }

    #[test]
    fn line_applies_now() {
        let _one = ONE.lock().unwrap_or_else(|e| e.into_inner());
        let (tx, hub) = spawn(Firmware::bundled(), tmp("line"));
        let rx = hub.subscribe();
        tx.send(Cmd::Speed(Some(5.0))).unwrap();
        tx.send(Cmd::Line("start".into())).unwrap();
        watch(&rx, |ev, d| sim_t(ev, d).is_some_and(|t| t >= 1.0));
        tx.send(Cmd::Line("load 20".into())).unwrap();
        let mut at = None;
        watch(&rx, |ev, d| {
            if ev == "event" {
                if let Some(s) = d.as_str().and_then(|s| s.strip_suffix(" load 20")) {
                    at = Some(s.parse::<f64>().unwrap());
                }
            }
            // a later row carries the load
            ev == "rows" && at.is_some() && d.as_array().unwrap().iter().any(|r| r[9].as_f64() == Some(20.0))
        });
        assert!(at.unwrap() >= 1.0);
    }

    #[test]
    fn stop_writes_folder() {
        let _one = ONE.lock().unwrap_or_else(|e| e.into_inner());
        let (tx, hub) = spawn(Firmware::bundled(), tmp("stop"));
        let rx = hub.subscribe();
        tx.send(Cmd::Speed(None)).unwrap();
        tx.send(Cmd::Line("start".into())).unwrap();
        watch(&rx, |ev, d| sim_t(ev, d).is_some_and(|t| t >= 0.5));
        tx.send(Cmd::Stop).unwrap();
        let mut folder = String::new();
        watch(&rx, |ev, d| {
            if ev == "report" {
                folder = d["folder"].as_str().unwrap().to_string();
            }
            ev == "report"
        });
        let events = std::fs::read_to_string(Path::new(&folder).join("events.txt")).unwrap();
        let s = seq::parse("events", &events).unwrap();
        assert!(s.end_us >= 500_000);
        assert_eq!(s.actions[0].1, sim::seq::Action::Start);
    }

    #[test]
    fn script_reports() {
        let _one = ONE.lock().unwrap_or_else(|e| e.into_inner());
        let (tx, hub) = spawn(Firmware::bundled(), tmp("script"));
        let rx = hub.subscribe();
        let text = include_str!("../../../scenarios/sil/01-start.seq");
        tx.send(Cmd::Speed(None)).unwrap();
        tx.send(Cmd::Script(seq::parse("01-start", text).unwrap())).unwrap();
        let mut outcomes = vec![];
        watch(&rx, |ev, d| {
            if ev == "report" {
                outcomes = d["outcomes"].as_array().unwrap().clone();
            }
            ev == "report"
        });
        assert_eq!(outcomes.len(), 3);
        assert!(outcomes.iter().all(|o| o["pass"] == true), "{outcomes:?}");
    }

    #[test]
    fn stop_after_a_long_run_keeps_the_thread() {
        let _one = ONE.lock().unwrap_or_else(|e| e.into_inner());
        let (tx, hub) = spawn(Firmware::bundled(), tmp("long"));
        let rx = hub.subscribe();
        tx.send(Cmd::Speed(None)).unwrap();
        tx.send(Cmd::Line("start".into())).unwrap();
        let t0 = Instant::now();
        watch(&rx, |ev, _| ev == "status" && t0.elapsed() > Duration::from_millis(1500));
        tx.send(Cmd::Stop).unwrap();
        watch(&rx, |ev, _| ev == "report");
        tx.send(Cmd::Line("start".into())).unwrap();
        watch(&rx, |ev, d| ev == "status" && d["mode"] == "running");
    }

    #[test]
    fn bad_line_reported() {
        let _one = ONE.lock().unwrap_or_else(|e| e.into_inner());
        let (tx, hub) = spawn(Firmware::bundled(), tmp("bad"));
        let rx = hub.subscribe();
        tx.send(Cmd::Speed(None)).unwrap();
        tx.send(Cmd::Line("start".into())).unwrap();
        tx.send(Cmd::Line("load".into())).unwrap();
        watch(&rx, |ev, d| ev == "error" && d.as_str().unwrap().contains("load"));
        watch(&rx, |ev, d| ev == "status" && d["mode"] == "running");
    }
}
