//! The firmware binding: bundled and loaded firmware, and the loader's refusals.
use sim::{EcuIo, Firmware};
use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, OnceLock};
use std::time::Duration;

fn tmp() -> PathBuf {
    let d = std::env::temp_dir().join(format!("ecusim-binding-{}", std::process::id()));
    std::fs::create_dir_all(&d).unwrap();
    d
}

/// (good library, ABI-99 library), built once per test run.
fn libs() -> &'static (PathBuf, PathBuf) {
    static L: OnceLock<(PathBuf, PathBuf)> = OnceLock::new();
    L.get_or_init(|| {
        let (good, bad) = (tmp().join(format!("good-{}", fwbuild::lib_name())),
                           tmp().join(format!("abi99-{}", fwbuild::lib_name())));
        fwbuild::build(&fwbuild::default_core(), &good, &[]).unwrap();
        fwbuild::build(&fwbuild::default_core(), &bad, &["ECU_ABI_VERSION=99u"]).unwrap();
        (good, bad)
    })
}

#[test]
fn io_size_matches() {
    assert_eq!(Firmware::bundled().io_size(), std::mem::size_of::<EcuIo>());
}

#[test]
fn abi_is_1() {
    assert_eq!(Firmware::bundled().abi, 1);
}

#[test]
fn loaded_is_a_different_instance() {
    let fw = Firmware::load(&libs().0).unwrap();
    assert_eq!(fw.abi, 1);
    assert!(fw.sha256.is_some());
    assert_ne!(fw.entry(), Firmware::bundled().entry());
}

#[test]
fn wrong_abi_refused() {
    let e = Firmware::load(&libs().1).err().unwrap();
    assert!(e.contains("ABI 99"), "{e}");
}

#[test]
fn missing_symbol_refused() {
    let core = tmp().join("partial");
    std::fs::create_dir_all(&core).unwrap();
    std::fs::write(core.join("only.c"),
        "#include <stdint.h>\n#ifdef _WIN32\n__declspec(dllexport)\n#endif\nuint32_t ecu_abi_version(void) { return 1; }\n").unwrap();
    let lib = tmp().join(format!("partial-{}", fwbuild::lib_name()));
    fwbuild::build(&core, &lib, &[]).unwrap();
    let e = Firmware::load(&lib).err().unwrap();
    assert!(e.contains("ecu_io_size"), "{e}");
}

#[test]
fn load_rejects_garbage() {
    let p = tmp().join("garbage.bin");
    let bytes: Vec<u8> = (0..1024u32).map(|i| (i.wrapping_mul(2654435761) >> 13) as u8).collect();
    std::fs::write(&p, bytes).unwrap();
    assert!(Firmware::load(&p).is_err());
}

#[test]
fn reload_same_path_runs_new_code() {
    let p = tmp().join(format!("same-{}", fwbuild::lib_name()));
    std::fs::copy(&libs().0, &p).unwrap();
    let first = Firmware::load(&p).unwrap();
    std::fs::copy(&libs().1, &p).unwrap();
    let e = Firmware::load(&p).err().unwrap();
    assert!(e.contains("ABI 99"), "{e}");
    drop(first);
}

#[test]
fn bundled_runs() {
    let fw = Firmware::bundled();
    let _c = fw.claim();
    let mut io = EcuIo::new();
    fw.init(&mut io);
    io.ignition = 1;
    for ms in 1..=10u32 {
        fw.tick_1ms(&mut io, ms * 1000);
    }
    assert!(!fw.nvm_image().is_empty());
    assert!(fw.rail_set_bar(10.0) > 0.0);
}

#[test]
fn claim_serialises() {
    let fw = Firmware::bundled();
    let first = fw.claim();
    let got = Arc::new(AtomicBool::new(false));
    let (fw2, got2) = (fw.clone(), got.clone());
    let h = std::thread::spawn(move || {
        let _c = fw2.claim();
        got2.store(true, Ordering::SeqCst);
    });
    std::thread::sleep(Duration::from_millis(100));
    assert!(!got.load(Ordering::SeqCst), "second claim did not wait");
    drop(first);
    h.join().unwrap();
    assert!(got.load(Ordering::SeqCst));
}
