//! Run folders (spec section 7): what happened, and which firmware did it.
use sim::check::Outcome;
use sim::j1939::{self, pgn};
use sim::{Firmware, Sim};
use std::fmt::Write as _;
use std::io;
use std::path::{Path, PathBuf};

/// YYYYMMDD-HHMMSS, UTC.
pub fn stamp() -> String {
    let s = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_secs() as i64;
    let (days, rem) = (s.div_euclid(86400), s.rem_euclid(86400));
    // civil from days (H. Hinnant)
    let z = days + 719468;
    let era = z.div_euclid(146097);
    let doe = z - era * 146097;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    let y = yoe + era * 400 + (m <= 2) as i64;
    format!("{y:04}{m:02}{d:02}-{:02}{:02}{:02}", rem / 3600, rem / 60 % 60, rem % 60)
}

pub fn report(title: &str, outcomes: &[Outcome]) -> String {
    let mut r = format!("{title}\n");
    for o in outcomes {
        let _ = writeln!(r, "  {}  {}   (found: {})", if o.pass { "PASS" } else { "FAIL" }, o.text, o.found);
    }
    let n = outcomes.iter().filter(|o| o.pass).count();
    let _ = writeln!(r, "  {n}/{} checks pass", outcomes.len());
    r
}

fn hex(d: &[u8]) -> String {
    d.iter().map(|b| format!("{b:02X}")).collect()
}

pub fn write(dir: &Path, name: &str, sim: &Sim, outcomes: &[Outcome], fw: &Firmware) -> io::Result<PathBuf> {
    std::fs::create_dir_all(dir)?;
    let base = format!("{}-{name}", stamp());
    let mut run = dir.join(&base);
    let mut n = 2;
    while run.exists() {
        run = dir.join(format!("{base}-{n}"));
        n += 1;
    }
    std::fs::create_dir(&run)?;

    let mut t = String::from("t_ms,rpm,ecu_rpm,state,synced,rail,rail_set,duty,fuel,load,clt,oil,wdg,starter,ignition\n");
    for r in &sim.trace {
        let _ = writeln!(t, "{},{:.3},{:.3},{},{},{:.3},{:.3},{:.5},{:.3},{},{:.3},{:.2},{},{},{}",
            r.t_ms, r.rpm, r.ecu_rpm, r.state, r.synced, r.rail, r.rail_set, r.duty, r.fuel,
            r.load, r.clt, r.oil, r.wdg, r.starter as u8, r.ignition);
    }
    std::fs::write(run.join("trace.csv"), t)?;

    let mut c = String::from("t_ms,dir,id,data,name\n");
    for f in &sim.can {
        let _ = writeln!(c, "{},{},{:08X},{},{}", f.t_ms, if f.rx { "rx" } else { "tx" }, f.id, hex(&f.data), j1939::name(pgn(f.id)));
    }
    std::fs::write(run.join("can.csv"), c)?;

    std::fs::write(run.join("events.txt"), sim.events.join("\n") + "\n")?;
    std::fs::write(run.join("report.txt"), report(name, outcomes))?;
    std::fs::write(run.join("firmware.txt"), format!("{}\nsha256 {}\nABI {}\n",
        fw.name, fw.sha256.as_deref().unwrap_or("-"), fw.abi))?;
    Ok(run)
}
