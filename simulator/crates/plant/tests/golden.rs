//! The Rust plant against the Python model's traces (tools/golden.py).
use plant::{Engine, RPM};

const DIR: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/tests/golden/");

fn csv(name: &str) -> Vec<Vec<f64>> {
    std::fs::read_to_string(format!("{DIR}{name}.csv"))
        .unwrap()
        .lines()
        .skip(1)
        .map(|l| l.split(',').map(|x| x.parse().unwrap()).collect())
        .collect()
}

/// Steps like golden.py's run(): rows every 1 ms, edges in step order.
fn run(eng: &mut Engine, secs: f64, mut before: impl FnMut(&mut Engine, u64)) -> (Vec<[f64; 4]>, Vec<(u64, bool)>) {
    let (mut rows, mut edges, mut t) = (vec![], vec![], 0u64);
    while (t as f64) < secs * 1e6 {
        before(eng, t);
        eng.step(t, 20, &mut edges);
        t += 20;
        if t % 1000 == 0 {
            rows.push([t as f64, eng.rpm(), eng.rail_bar, eng.theta]);
        }
    }
    (rows, edges)
}

fn close(a: f64, b: f64) -> bool {
    (a - b).abs() <= 1e-6 * b.abs().max(1.0)
}

fn check(name: &str, eng: &mut Engine, secs: f64, before: impl FnMut(&mut Engine, u64)) {
    let (rows, edges) = run(eng, secs, before);
    let want_edges: Vec<(u64, bool)> = csv(&format!("{name}_edges"))
        .iter()
        .map(|r| (r[0] as u64, r[1] != 0.0))
        .collect();
    assert_eq!(edges, want_edges, "{name}: edges differ");
    let want = csv(name);
    assert_eq!(rows.len(), want.len(), "{name}: row count");
    for (r, w) in rows.iter().zip(&want) {
        assert_eq!(r[0], w[0]);
        assert!(close(r[1], w[1]), "{name} t={} rpm {} vs {}", r[0], r[1], w[1]);
        assert!(close(r[2], w[2]), "{name} t={} rail {} vs {}", r[0], r[2], w[2]);
    }
}

fn held(rpm: f64) -> impl FnMut(&mut Engine, u64) {
    move |e: &mut Engine, _| e.omega = rpm * RPM
}

#[test]
fn golden_starter() {
    let mut e = Engine::new();
    e.starter = true;
    check("starter", &mut e, 2.0, |_, _| {});
}

#[test]
fn golden_held() {
    let mut e = Engine::new();
    e.load_kw = 20.0;
    e.stuck_fuel = [Some(34.0); 3];
    check("held", &mut e, 0.16, held(1500.0));
}

#[test]
fn golden_rail_fill() {
    let mut e = Engine::new();
    check("rail_fill", &mut e, 1.0, held(150.0));
}

#[test]
fn golden_free() {
    let mut e = Engine::new();
    e.omega = 1500.0 * RPM;
    e.duty = 0.3;
    e.load_kw = 10.0;
    let mut nxt = [0u32; 3];
    check("free", &mut e, 2.0, move |eng, t| {
        for k in 0..3 {
            let start = k as u64 * 26667 + nxt[k] as u64 * 80000;
            if t + 10000 >= start {
                eng.command(k, start as u32, 1500, nxt[k] + 1);
                nxt[k] += 1;
            }
        }
    });
}

#[test]
fn self_check_starter() {
    let mut e = Engine::new();
    e.starter = true;
    let (mut t, mut tail, mut v) = (0u64, vec![], vec![]);
    while t < 2_000_000 {
        e.step(t, 20, &mut v);
        t += 20;
        if t > 1_600_000 {
            tail.push(e.rpm());
        }
    }
    let m = tail.iter().sum::<f64>() / tail.len() as f64;
    assert!((140.0..=150.0).contains(&m), "{m}");
}

#[test]
fn self_check_torque_balance() {
    let mut e = Engine::new();
    e.load_kw = 20.0;
    e.stuck_fuel = [Some(34.0); 3];
    let (mut net, mut n, mut t, mut v) = (0.0, 0, 0u64, vec![]);
    while t < 160_000 {
        e.omega = 1500.0 * RPM;
        e.step(t, 20, &mut v);
        if t >= 80_000 {
            net += e.net_torque;
            n += 1;
        }
        t += 20;
    }
    let load = 20_000.0 / plant::GEN_EFF / (1500.0 * RPM);
    assert!((net / n as f64).abs() < 0.10 * load);
}

#[test]
fn self_check_edges() {
    let mut e = Engine::new();
    e.theta = 3.0;
    let (mut t, mut v) = (0u64, vec![]);
    while t < 80_000 {
        e.omega = 1500.0 * RPM;
        e.step(t, 20, &mut v);
        t += 20;
    }
    let cam = v.iter().filter(|x| x.1).count();
    assert_eq!((v.len() - cam, cam), (116, 1));
}

#[test]
fn self_check_rail_fill() {
    let mut e = Engine::new();
    let mut v = vec![];
    for i in 0..50_000u64 {
        e.omega = 150.0 * RPM;
        e.step(i * 20, 20, &mut v);
    }
    assert!(e.rail_bar > 100.0, "{}", e.rail_bar);
}

#[test]
fn command_across_u32_wrap() {
    let mut e = Engine::new();
    e.omega = 1500.0 * RPM;
    e.rail_bar = 1000.0;
    let mut v = vec![];
    let mut t: u64 = (1u64 << 32) - 500;
    e.step(t, 20, &mut v);
    t += 20;
    e.command(0, 100, 1500, 1); // 100 us after the wrap, in firmware time
    let mut got = 0.0f64;
    while t < (1u64 << 32) + 2000 {
        e.omega = 1500.0 * RPM;
        e.step(t, 20, &mut v);
        got = got.max(e.fuel[0]);
        t += 20;
    }
    assert!(got > 0.0, "no fuel delivered across the wrap");
}
