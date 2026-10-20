//! ecusim: the ECU firmware against the engine model.
//!
//!   ecusim [--port N] [--share]                       the browser UI
//!   ecusim run <file.seq>... [--fw LIB] [--out DIR]   headless, at max speed
use ecusim::{live, runs, server};

use sim::{seq, Firmware};
use std::path::{Path, PathBuf};
use std::process::exit;
use std::sync::Arc;

const USAGE: &str = "usage: ecusim [--port N] [--share]\n       ecusim run <file.seq>... [--fw LIB] [--out DIR]";

/// `dir/*.seq` style patterns, expanded here: Windows' cmd passes them through.
fn expand(arg: &str) -> Vec<PathBuf> {
    let p = Path::new(arg);
    let name = p.file_name().and_then(|n| n.to_str()).unwrap_or("");
    let Some((pre, post)) = name.split_once('*') else { return vec![p.into()] };
    let dir = p.parent().filter(|d| !d.as_os_str().is_empty()).unwrap_or(Path::new("."));
    let mut v: Vec<PathBuf> = std::fs::read_dir(dir).into_iter().flatten().flatten()
        .map(|e| e.path())
        .filter(|f| f.file_name().and_then(|n| n.to_str()).is_some_and(|n| n.starts_with(pre) && n.ends_with(post) && n.len() >= pre.len() + post.len()))
        .collect();
    v.sort();
    v
}

fn run(args: &[String]) -> i32 {
    let (mut files, mut fw_path, mut out) = (vec![], None, PathBuf::from("runs"));
    let mut it = args.iter();
    while let Some(a) = it.next() {
        match a.as_str() {
            "--fw" => fw_path = it.next().cloned(),
            "--out" => out = it.next().map(PathBuf::from).unwrap_or(out),
            _ => files.extend(expand(a)),
        }
    }
    if files.is_empty() {
        eprintln!("{USAGE}");
        return 2;
    }
    let fw: Arc<Firmware> = match fw_path {
        Some(p) => match Firmware::load(Path::new(&p)) {
            Ok(f) => f,
            Err(e) => {
                eprintln!("{p}: {e}");
                return 2;
            }
        },
        None => Firmware::bundled(),
    };
    let mut scripts = vec![];
    let mut bad = false;
    for f in &files {
        let name = f.file_stem().and_then(|n| n.to_str()).unwrap_or("run").to_string();
        match std::fs::read_to_string(f).map_err(|e| vec![(0, e.to_string())]).and_then(|t| seq::parse(&name, &t)) {
            Ok(s) => scripts.push(s),
            Err(errs) => {
                bad = true;
                for (line, msg) in errs {
                    eprintln!("{}:{line}: {msg}", f.display());
                }
            }
        }
    }
    if bad {
        return 2;
    }
    let mut all = true;
    for s in &scripts {
        let (sim, outcomes) = seq::run(fw.clone(), s);
        print!("{}", runs::report(&s.name, &outcomes));
        match runs::write(&out, &s.name, &sim, &outcomes, &fw) {
            Ok(dir) => println!("  -> {}", dir.display()),
            Err(e) => {
                eprintln!("writing the run folder: {e}");
                return 2;
            }
        }
        all &= outcomes.iter().all(|o| o.pass);
    }
    if all { 0 } else { 1 }
}

/// The UI: serve on 127.0.0.1 (all interfaces with --share) and open the browser.
fn ui(args: &[String]) -> i32 {
    let (mut port, mut share) = (8025u16, false);
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--share" => share = true,
            "--port" => {
                i += 1;
                match args.get(i).and_then(|p| p.parse().ok()) {
                    Some(p) => port = p,
                    None => {
                        eprintln!("{USAGE}");
                        return 2;
                    }
                }
            }
            _ => {
                eprintln!("{USAGE}");
                return 2;
            }
        }
        i += 1;
    }
    let (srv, port) = match server::bind(port, share) {
        Ok(x) => x,
        Err(e) => {
            eprintln!("{e}");
            return 2;
        }
    };
    let url = format!("http://127.0.0.1:{port}/");
    println!("ecusim is running at {url}  (close this window or press Ctrl+C to quit)");
    if share {
        println!("--share: other computers on this network can open port {port}; firmware uploads are refused");
    }
    let runs_dir = PathBuf::from("runs");
    let (tx, hub) = live::spawn(Firmware::bundled(), runs_dir.clone());
    if webbrowser::open(&url).is_err() {
        println!("open {url} in a browser");
    }
    server::serve(srv, tx, hub, share, runs_dir);
    0
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    match args.first().map(String::as_str) {
        Some("run") => exit(run(&args[1..])),
        Some("-h" | "--help") => println!("{USAGE}"),
        _ => exit(ui(&args)),
    }
}
