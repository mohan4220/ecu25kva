//! The bundled scenario library: scenarios/, compiled in. Written out by
//! hand; library_matches_dir keeps it in step with the folder.
pub const LIBRARY: &[(&str, &str)] = &[
    ("faults/cam-lost.seq", include_str!("../../../scenarios/faults/cam-lost.seq")),
    ("faults/crank-drop.seq", include_str!("../../../scenarios/faults/crank-drop.seq")),
    ("faults/crank-extra.seq", include_str!("../../../scenarios/faults/crank-extra.seq")),
    ("faults/crank-lost.seq", include_str!("../../../scenarios/faults/crank-lost.seq")),
    ("faults/fuel-stuck-cyl.seq", include_str!("../../../scenarios/faults/fuel-stuck-cyl.seq")),
    ("faults/ignition-bounce.seq", include_str!("../../../scenarios/faults/ignition-bounce.seq")),
    ("faults/rail-leak.seq", include_str!("../../../scenarios/faults/rail-leak.seq")),
    ("faults/sensor-offset.seq", include_str!("../../../scenarios/faults/sensor-offset.seq")),
    ("faults/sensor-open.seq", include_str!("../../../scenarios/faults/sensor-open.seq")),
    ("faults/sensor-short.seq", include_str!("../../../scenarios/faults/sensor-short.seq")),
    ("faults/sensor-short5v.seq", include_str!("../../../scenarios/faults/sensor-short5v.seq")),
    ("faults/sensor-stuck.seq", include_str!("../../../scenarios/faults/sensor-stuck.seq")),
    ("faults/sensor-volts.seq", include_str!("../../../scenarios/faults/sensor-volts.seq")),
    ("sil/01-start.seq", include_str!("../../../scenarios/sil/01-start.seq")),
    ("sil/02-load-step.seq", include_str!("../../../scenarios/sil/02-load-step.seq")),
    ("sil/03-load-reject.seq", include_str!("../../../scenarios/sil/03-load-reject.seq")),
    ("sil/04-droop.seq", include_str!("../../../scenarios/sil/04-droop.seq")),
    ("sil/05-runaway.seq", include_str!("../../../scenarios/sil/05-runaway.seq")),
    ("sil/06-crank-loss.seq", include_str!("../../../scenarios/sil/06-crank-loss.seq")),
    ("sil/07-ignition-off.seq", include_str!("../../../scenarios/sil/07-ignition-off.seq")),
    ("sil/08-sensor-open.seq", include_str!("../../../scenarios/sil/08-sensor-open.seq")),
    ("sil/09-can-content.seq", include_str!("../../../scenarios/sil/09-can-content.seq")),
    ("sil/10-rail.seq", include_str!("../../../scenarios/sil/10-rail.seq")),
    ("sil/11-watchdog.seq", include_str!("../../../scenarios/sil/11-watchdog.seq")),
    ("sil/12-history.seq", include_str!("../../../scenarios/sil/12-history.seq")),
    ("sil/13-torn-save.seq", include_str!("../../../scenarios/sil/13-torn-save.seq")),
    ("sil/14-dm2-dm3.seq", include_str!("../../../scenarios/sil/14-dm2-dm3.seq")),
    ("sil/15-lost-tooth.seq", include_str!("../../../scenarios/sil/15-lost-tooth.seq")),
    ("sil/16-overload.seq", include_str!("../../../scenarios/sil/16-overload.seq")),
];

#[cfg(test)]
mod tests {
    use super::LIBRARY;

    #[test]
    fn library_matches_dir() {
        let root = std::path::Path::new(concat!(env!("CARGO_MANIFEST_DIR"), "/../../scenarios"));
        let mut on_disk = vec![];
        for sub in std::fs::read_dir(root).unwrap() {
            let sub = sub.unwrap().path();
            for f in std::fs::read_dir(&sub).unwrap() {
                let f = f.unwrap().path();
                if f.extension().is_some_and(|x| x == "seq") {
                    on_disk.push(f.strip_prefix(root).unwrap().to_str().unwrap().replace('\\', "/"));
                }
            }
        }
        on_disk.sort();
        let mut listed: Vec<String> = LIBRARY.iter().map(|x| x.0.to_string()).collect();
        listed.sort();
        assert_eq!(listed, on_disk);
    }

    #[test]
    fn library_parses() {
        for (name, text) in LIBRARY {
            if let Err(e) = sim::seq::parse(name, text) {
                panic!("{name}: {e:?}");
            }
        }
    }
}
