//! The loop against the Python SIL, and history across a power cycle.
use sim::{nvm, Firmware, Sim};

#[test]
fn closed_start_matches_python() {
    let want: Vec<(u64, f64, u8)> = include_str!("../../plant/tests/golden/closed_start.csv")
        .lines()
        .skip(1)
        .map(|l| {
            let f: Vec<&str> = l.split(',').collect();
            (f[0].parse().unwrap(), f[1].parse().unwrap(), f[2].parse().unwrap())
        })
        .collect();
    let mut s = Sim::new(Firmware::bundled());
    s.eng.starter = true;
    s.release_on_run = true;
    for _ in 0..5000 {
        s.step_ms();
    }
    assert_eq!(s.trace.len(), want.len());
    let mut worst = 0.0f64;
    for (r, w) in s.trace.iter().zip(&want) {
        assert_eq!(r.t_ms, w.0);
        assert_eq!(r.state, w.2, "state differs at {} ms", r.t_ms);
        worst = worst.max((r.rpm - w.1).abs());
    }
    assert!(worst < 1.0, "worst rpm difference {worst}");
}

#[test]
fn power_cycle_keeps_history() {
    let mut s = Sim::new(Firmware::bundled());
    s.eng.starter = true;
    s.release_on_run = true;
    while s.t_us < 6_000_000 {
        s.step_ms();
    }
    s.eng.stuck_fuel = [Some(80.0); 3];
    while s.t_us < 9_000_000 {
        s.step_ms();
    }
    s.power_cycle();
    let st = nvm::stored(&s.slots).expect("no valid slot");
    assert!(st.contains(&(190, 0)), "{st:?}");
}
