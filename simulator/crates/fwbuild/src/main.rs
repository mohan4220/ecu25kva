//! fwbuild [--core DIR] [--out FILE] [-D NAME=VAL]...
use std::path::PathBuf;

fn main() {
    let mut core = fwbuild::default_core();
    let mut out = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../build").join(fwbuild::lib_name());
    let mut defines = vec![];
    let mut args = std::env::args().skip(1);
    while let Some(a) = args.next() {
        match (a.as_str(), args.next()) {
            ("--core", Some(v)) => core = v.into(),
            ("--out", Some(v)) => out = v.into(),
            ("-D", Some(v)) => defines.push(v),
            _ => {
                eprintln!("usage: fwbuild [--core DIR] [--out FILE] [-D NAME=VAL]...");
                std::process::exit(2);
            }
        }
    }
    let d: Vec<&str> = defines.iter().map(String::as_str).collect();
    match fwbuild::build(&core, &out, &d) {
        Ok(()) => println!("{}", out.display()),
        Err(e) => {
            eprintln!("{e}");
            std::process::exit(1);
        }
    }
}
