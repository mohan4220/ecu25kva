//! `ecusim run`, end to end.
use std::path::{Path, PathBuf};
use std::process::Command;

const SCEN: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/../../scenarios");

fn tmp(name: &str) -> PathBuf {
    let d = std::env::temp_dir().join(format!("ecusim-cli-{}-{name}", std::process::id()));
    let _ = std::fs::remove_dir_all(&d);
    std::fs::create_dir_all(&d).unwrap();
    d
}

fn ecusim(args: &[&str]) -> (i32, String) {
    let o = Command::new(env!("CARGO_BIN_EXE_ecusim")).args(args).output().unwrap();
    (o.status.code().unwrap_or(-1), String::from_utf8_lossy(&o.stdout).into_owned() + &String::from_utf8_lossy(&o.stderr))
}

fn folders(d: &Path) -> Vec<PathBuf> {
    let mut v: Vec<PathBuf> = std::fs::read_dir(d).unwrap().map(|e| e.unwrap().path()).collect();
    v.sort();
    v
}

#[test]
fn sil_all_pass() {
    let out = tmp("sil");
    // the pattern is expanded by ecusim itself, as Windows' cmd does not
    let (code, text) = ecusim(&["run", &format!("{SCEN}/sil/*.seq"), "--out", out.to_str().unwrap()]);
    assert_eq!(code, 0, "{text}");
    assert_eq!(folders(&out).len(), 16);
}

#[test]
fn failing_check_exits_1() {
    let d = tmp("fail");
    let f = d.join("fail.seq");
    std::fs::write(&f, "0 start\n5 end\nexpect rpm mean 0..1 over 4..5\n").unwrap();
    let out = d.join("runs");
    let (code, text) = ecusim(&["run", f.to_str().unwrap(), "--out", out.to_str().unwrap()]);
    assert_eq!(code, 1, "{text}");
    let report = std::fs::read_to_string(folders(&out)[0].join("report.txt")).unwrap();
    assert!(report.contains("FAIL"), "{report}");
}

#[test]
fn bad_script_exits_2() {
    let d = tmp("bad");
    let f = d.join("bad.seq");
    std::fs::write(&f, "0 start\n1 fly\n").unwrap();
    let (code, text) = ecusim(&["run", f.to_str().unwrap(), "--out", d.join("runs").to_str().unwrap()]);
    assert_eq!(code, 2);
    assert!(text.contains(":2:"), "{text}");
}

#[test]
fn run_folder_files() {
    let out = tmp("files");
    let (code, text) = ecusim(&["run", &format!("{SCEN}/sil/01-start.seq"), "--out", out.to_str().unwrap()]);
    assert_eq!(code, 0, "{text}");
    let run = &folders(&out)[0];
    assert!(run.file_name().unwrap().to_str().unwrap().ends_with("-01-start"));
    for f in ["trace.csv", "can.csv", "events.txt", "report.txt", "firmware.txt"] {
        assert!(run.join(f).exists(), "{f}");
    }
    let trace = std::fs::read_to_string(run.join("trace.csv")).unwrap();
    assert_eq!(trace.lines().count(), 5001);
    assert!(trace.starts_with("t_ms,rpm,ecu_rpm,state,synced,rail,rail_set,duty,fuel,load,clt,oil,wdg,starter,ignition\n"));
    let events = std::fs::read_to_string(run.join("events.txt")).unwrap();
    let s = sim::seq::parse("events", &events).unwrap();
    assert_eq!(s.end_us, 5_000_000);
    let fw = std::fs::read_to_string(run.join("firmware.txt")).unwrap();
    assert!(fw.contains("bundled") && fw.contains("ABI 1"), "{fw}");
    let can = std::fs::read_to_string(run.join("can.csv")).unwrap();
    assert!(can.lines().any(|l| l.ends_with(",EEC1")), "no EEC1 in can.csv");
}
