//! Faults the plant adds beyond the Python model (spec section 3).
use plant::{Ch, Engine, SensorFault, RPM};

/// One cycle at 1500 rpm from theta 3 (no edge on the window's ends).
fn cycle(e: &mut Engine) -> (Vec<u64>, usize) {
    e.theta = 3.0;
    let (mut t, mut v) = (0u64, vec![]);
    while t < 80_000 {
        e.omega = 1500.0 * RPM;
        e.step(t, 20, &mut v);
        t += 20;
    }
    let crank: Vec<u64> = v.iter().filter(|x| !x.1).map(|x| x.0).collect();
    (crank, v.iter().filter(|x| x.1).count())
}

fn with(f: SensorFault, ch: Ch) -> f64 {
    let mut e = Engine::new();
    e.sensor[ch as usize] = f;
    e.volts()[ch as usize]
}

#[test]
fn open_volts() {
    assert_eq!(with(SensorFault::Open, Ch::Clt), 5.0);
    for ch in [Ch::Oil, Ch::Rail, Ch::Boost, Ch::Egr, Ch::V5] {
        assert_eq!(with(SensorFault::Open, ch), 0.0, "{ch:?}");
    }
}

#[test]
fn short() {
    assert_eq!(with(SensorFault::Short, Ch::Clt), 0.0);
    assert_eq!(with(SensorFault::Short, Ch::Oil), 0.0);
}

#[test]
fn short5v() {
    assert_eq!(with(SensorFault::Short5v, Ch::Rail), 5.0);
}

#[test]
fn volts_forced() {
    assert_eq!(with(SensorFault::Volts(2.2), Ch::Boost), 2.2);
}

#[test]
fn offset_adds() {
    let base = Engine::new().volts()[Ch::Oil as usize];
    assert!((with(SensorFault::Offset(0.3), Ch::Oil) - (base + 0.3)).abs() < 1e-12);
}

#[test]
fn stuck_holds() {
    let mut e = Engine::new();
    e.load_kw = 20.0; // coolant heads for 90 degC
    e.stick(Ch::Clt);
    let held = e.volts()[Ch::Clt as usize];
    let mut v = vec![];
    for i in 0..500_000u64 {
        e.step(i * 20, 20, &mut v);
    }
    assert!(e.clt_c > 81.0, "coolant did not warm: {}", e.clt_c);
    assert_eq!(e.volts()[Ch::Clt as usize], held);
    e.sensor[Ch::Clt as usize] = SensorFault::None;
    assert_ne!(e.volts()[Ch::Clt as usize], held);
}

#[test]
fn crank_lost_no_edges() {
    let mut e = Engine::new();
    e.crank_lost = true;
    let (crank, cam) = cycle(&mut e);
    assert_eq!((crank.len(), cam), (0, 1));
}

#[test]
fn cam_lost_no_cam() {
    let mut e = Engine::new();
    e.cam_lost = true;
    let (crank, cam) = cycle(&mut e);
    assert_eq!((crank.len(), cam), (116, 0));
}

#[test]
fn drop_two() {
    let mut e = Engine::new();
    e.crank_drop = 2;
    let (crank, _) = cycle(&mut e);
    assert_eq!(crank.len(), 114);
    assert_eq!(e.crank_drop, 0);
}

#[test]
fn extra_one() {
    let mut e = Engine::new();
    e.crank_extra = 1;
    let (crank, _) = cycle(&mut e);
    assert_eq!(crank.len(), 117);
    let clean = cycle(&mut Engine::new()).0;
    let i = crank.iter().zip(&clean).position(|(a, b)| a != b).unwrap();
    assert!(i > 0, "extra edge before any real one");
    let mid = (clean[i - 1] + clean[i]) as f64 / 2.0;
    assert!((crank[i] as f64 - mid).abs() <= 1.0, "{} vs {}", crank[i], mid);
    assert_eq!(crank[i + 1], clean[i]);
}

#[test]
fn stuck_one_cylinder() {
    let mut e = Engine::new();
    e.stuck_fuel[1] = Some(5.0);
    e.theta = 3.0;
    let (mut t, mut v, mut most) = (0u64, vec![], [0.0f64; 3]);
    while t < 80_000 {
        e.omega = 1500.0 * RPM;
        e.step(t, 20, &mut v);
        for k in 0..3 {
            most[k] = most[k].max(e.fuel[k]);
        }
        t += 20;
    }
    assert_eq!(most, [0.0, 5.0, 0.0]);
}

#[test]
fn leak_drains() {
    let fall = |leak: f64| {
        let mut e = Engine::new();
        e.rail_bar = 1000.0;
        e.leak = leak;
        e.duty = 1.0; // metering closed: no pump flow
        let mut v = vec![];
        for i in 0..5_000u64 {
            e.step(i * 20, 20, &mut v);
        }
        1000.0 - e.rail_bar
    };
    assert!(fall(10.0) > 5.0 * fall(1.0));
}
