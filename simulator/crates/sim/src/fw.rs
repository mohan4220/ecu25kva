//! The firmware binding: the C core's entry points as function pointers,
//! from the bundled (statically linked) core or from a loaded library.
//! The C core keeps its state in statics, so one Firmware is one ECU:
//! a Sim claims it for its lifetime.
use sha2::{Digest, Sha256};
use std::ffi::c_void;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU32, Ordering};
use std::sync::{Arc, Condvar, Mutex, OnceLock};

pub const ABI_VERSION: u32 = 1; // ecu.h ECU_ABI_VERSION
pub const NCYL: usize = 3;
pub const CANQ: usize = 16;

#[repr(C)]
#[derive(Clone, Copy, Debug, Default, PartialEq)]
pub struct EcuCan {
    pub id: u32,
    pub len: u8,
    pub data: [u8; 8],
}

#[repr(C)]
#[derive(Clone, Copy, Debug, Default)]
pub struct EcuInj {
    pub start_us: u32,
    pub dur_us: u32,
    pub seq: u32,
}

/// ecu.h's ecu_io, field for field.
#[repr(C)]
pub struct EcuIo {
    pub v_clt: f32,
    pub v_oil: f32,
    pub v_rail: f32,
    pub v_boost: f32,
    pub v_egr: f32,
    pub v_5v: f32,
    pub ignition: u8,
    pub droop_sw: u8,
    pub v_bat: f32,
    pub reset_cause: u8,
    pub inj: [EcuInj; NCYL],
    pub meter_duty: f32,
    pub wdg: u8,
    pub can: [EcuCan; CANQ],
    pub can_n: u8,
    pub can_drops: u16,
    pub nvm_save: u8,
    pub nvm_slot: u8,
    pub state: u8,
    pub fault_n: u8,
    pub synced: u8,
    pub rpm: f32,
    pub fuel_mg: f32,
    pub rail_bar: f32,
    pub clt_c: f32,
    pub oil_kpa: f32,
    pub boot_ver: u16,
    pub usb_in: [u8; 64],
    pub usb_in_n: u8,
    pub usb_out: [u8; 512],
    pub usb_out_n: u16,
    pub can2: [EcuCan; CANQ],
    pub can2_n: u8,
    pub eol_save: u8,
    pub boot_req: u8,
    pub reset_req: u8,
    pub session: u8,
}

impl EcuIo {
    pub fn new() -> Box<EcuIo> {
        // all-zero is a valid ecu_io: plain integers and floats
        Box::new(unsafe { std::mem::zeroed() })
    }
}

type IoFn = unsafe extern "C" fn(*mut EcuIo);
type IoTFn = unsafe extern "C" fn(*mut EcuIo, u32);

#[derive(Clone, Copy)]
struct Api {
    abi: unsafe extern "C" fn() -> u32,
    io_size: unsafe extern "C" fn() -> usize,
    init: IoFn,
    crank_edge: IoTFn,
    cam_edge: IoTFn,
    tick_1ms: IoTFn,
    background: IoFn,
    nvm_load: unsafe extern "C" fn(*mut EcuIo, *const c_void, *const c_void, u32),
    nvm_image: unsafe extern "C" fn(*mut u32) -> *const c_void,
    can_rx: unsafe extern "C" fn(*mut EcuIo, *const EcuCan),
    eol_load: unsafe extern "C" fn(*mut EcuIo, *const c_void, *const c_void),
    rail_set_bar: unsafe extern "C" fn(f32) -> f32,
}

extern "C" {
    fn ecu_abi_version() -> u32;
    fn ecu_io_size() -> usize;
    fn ecu_init(io: *mut EcuIo);
    fn ecu_crank_edge(io: *mut EcuIo, t: u32);
    fn ecu_cam_edge(io: *mut EcuIo, t: u32);
    fn ecu_tick_1ms(io: *mut EcuIo, t: u32);
    fn ecu_background(io: *mut EcuIo);
    fn ecu_nvm_load(io: *mut EcuIo, a: *const c_void, b: *const c_void, len: u32);
    fn ecu_nvm_image(len: *mut u32) -> *const c_void;
    fn ecu_can_rx(io: *mut EcuIo, f: *const EcuCan);
    fn ecu_eol_load(io: *mut EcuIo, a: *const c_void, b: *const c_void);
    fn rail_set_bar(fuel_mg: f32) -> f32;
}

pub struct Firmware {
    pub name: String,
    pub sha256: Option<String>,
    pub abi: u32,
    api: Api,
    lib: Option<libloading::Library>,
    file: Option<PathBuf>,
    busy: Mutex<bool>,
    free: Condvar,
}

/// Held by whoever drives this firmware; dropping it frees the firmware.
pub struct Claim(Arc<Firmware>);

impl Drop for Claim {
    fn drop(&mut self) {
        *self.0.busy.lock().unwrap() = false;
        self.0.free.notify_one();
    }
}

impl Drop for Firmware {
    fn drop(&mut self) {
        drop(self.lib.take()); // unload before deleting the copy (Windows locks it)
        if let Some(f) = &self.file {
            let _ = std::fs::remove_file(f);
        }
    }
}

const SYMBOLS: [&str; 12] = [
    "ecu_abi_version", "ecu_io_size", "ecu_init", "ecu_crank_edge", "ecu_cam_edge",
    "ecu_tick_1ms", "ecu_background", "ecu_nvm_load", "ecu_nvm_image", "ecu_can_rx",
    "ecu_eol_load", "rail_set_bar",
];

impl Firmware {
    fn new(name: String, sha256: Option<String>, api: Api, lib: Option<libloading::Library>, file: Option<PathBuf>) -> Firmware {
        let abi = unsafe { (api.abi)() };
        Firmware { name, sha256, abi, api, lib, file, busy: Mutex::new(false), free: Condvar::new() }
    }

    /// The firmware compiled into this program. The same Arc every call.
    pub fn bundled() -> Arc<Firmware> {
        static B: OnceLock<Arc<Firmware>> = OnceLock::new();
        B.get_or_init(|| {
            let api = Api {
                abi: ecu_abi_version,
                io_size: ecu_io_size,
                init: ecu_init,
                crank_edge: ecu_crank_edge,
                cam_edge: ecu_cam_edge,
                tick_1ms: ecu_tick_1ms,
                background: ecu_background,
                nvm_load: ecu_nvm_load,
                nvm_image: ecu_nvm_image,
                can_rx: ecu_can_rx,
                eol_load: ecu_eol_load,
                rail_set_bar,
            };
            Arc::new(Firmware::new("bundled".into(), None, api, None, None))
        })
        .clone()
    }

    /// A firmware library (.dll, .dylib, .so). It is copied to a fresh
    /// file name first: operating systems hand back an already-loaded
    /// library when the path is the same, whatever is on disk now.
    pub fn load(path: &Path) -> Result<Arc<Firmware>, String> {
        static N: AtomicU32 = AtomicU32::new(0);
        let bytes = std::fs::read(path).map_err(|e| format!("{}: {e}", path.display()))?;
        let ext = path.extension().and_then(|x| x.to_str()).unwrap_or("lib");
        let copy = std::env::temp_dir().join(format!(
            "ecusim-fw-{}-{}.{ext}", std::process::id(), N.fetch_add(1, Ordering::SeqCst)));
        std::fs::write(&copy, &bytes).map_err(|e| e.to_string())?;
        let gone = |e: String| {
            let _ = std::fs::remove_file(&copy);
            e
        };
        // Loading runs the library's initialisers: the UI warns to load only trusted firmware.
        let lib = unsafe { libloading::Library::new(&copy) }
            .map_err(|e| gone(format!("not a firmware library for this computer: {e}")))?;
        let api = match unsafe { Self::symbols(&lib) } {
            Ok(api) => api,
            Err(e) => {
                drop(lib);
                return Err(gone(e));
            }
        };
        let name = path.file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_default();
        let sha = format!("{:x}", Sha256::digest(&bytes));
        let fw = Firmware::new(name, Some(sha), api, Some(lib), Some(copy));
        if fw.abi != ABI_VERSION {
            return Err(format!("firmware ABI {}, this simulator needs ABI {ABI_VERSION}", fw.abi));
        }
        let (theirs, ours) = (fw.io_size(), std::mem::size_of::<EcuIo>());
        if theirs != ours {
            return Err(format!("firmware ecu_io is {theirs} bytes, this simulator's is {ours}"));
        }
        Ok(Arc::new(fw))
    }

    unsafe fn symbols(lib: &libloading::Library) -> Result<Api, String> {
        for s in SYMBOLS {
            lib.get::<*const c_void>(s.as_bytes()).map_err(|_| format!("firmware lacks {s}"))?;
        }
        macro_rules! sym {
            ($n:literal) => {
                *lib.get(concat!($n, "\0").as_bytes()).unwrap()
            };
        }
        Ok(Api {
            abi: sym!("ecu_abi_version"),
            io_size: sym!("ecu_io_size"),
            init: sym!("ecu_init"),
            crank_edge: sym!("ecu_crank_edge"),
            cam_edge: sym!("ecu_cam_edge"),
            tick_1ms: sym!("ecu_tick_1ms"),
            background: sym!("ecu_background"),
            nvm_load: sym!("ecu_nvm_load"),
            nvm_image: sym!("ecu_nvm_image"),
            can_rx: sym!("ecu_can_rx"),
            eol_load: sym!("ecu_eol_load"),
            rail_set_bar: sym!("rail_set_bar"),
        })
    }

    /// Blocks while another Claim on this firmware is alive.
    pub fn claim(self: &Arc<Self>) -> Claim {
        let mut b = self.busy.lock().unwrap();
        while *b {
            b = self.free.wait(b).unwrap();
        }
        *b = true;
        Claim(self.clone())
    }

    /// The address of ecu_init: tells two instances apart.
    pub fn entry(&self) -> usize {
        self.api.init as usize
    }

    pub fn io_size(&self) -> usize {
        unsafe { (self.api.io_size)() }
    }
    pub fn init(&self, io: &mut EcuIo) {
        unsafe { (self.api.init)(io) }
    }
    pub fn crank_edge(&self, io: &mut EcuIo, t_us: u32) {
        unsafe { (self.api.crank_edge)(io, t_us) }
    }
    pub fn cam_edge(&self, io: &mut EcuIo, t_us: u32) {
        unsafe { (self.api.cam_edge)(io, t_us) }
    }
    pub fn tick_1ms(&self, io: &mut EcuIo, t_us: u32) {
        unsafe { (self.api.tick_1ms)(io, t_us) }
    }
    pub fn background(&self, io: &mut EcuIo) {
        unsafe { (self.api.background)(io) }
    }
    pub fn can_rx(&self, io: &mut EcuIo, f: &EcuCan) {
        unsafe { (self.api.can_rx)(io, f) }
    }
    /// Both slots, cut or zero-padded to the image length, as ecu.py does.
    pub fn nvm_load(&self, io: &mut EcuIo, a: &[u8], b: &[u8]) {
        let n = self.nvm_image().len();
        let fit = |x: &[u8]| {
            let mut v = x[..x.len().min(n)].to_vec();
            v.resize(n, 0);
            v
        };
        let (a, b) = (fit(a), fit(b));
        unsafe { (self.api.nvm_load)(io, a.as_ptr().cast(), b.as_ptr().cast(), n as u32) }
    }
    pub fn eol_load(&self, io: &mut EcuIo, a: &[u8; 84], b: &[u8; 84]) {
        unsafe { (self.api.eol_load)(io, a.as_ptr().cast(), b.as_ptr().cast()) }
    }
    pub fn nvm_image(&self) -> Vec<u8> {
        let mut n = 0u32;
        let p = unsafe { (self.api.nvm_image)(&mut n) };
        unsafe { std::slice::from_raw_parts(p as *const u8, n as usize) }.to_vec()
    }
    pub fn rail_set_bar(&self, fuel_mg: f32) -> f32 {
        unsafe { (self.api.rail_set_bar)(fuel_mg) }
    }
}

/// CRC-32 as zlib computes it.
pub fn crc32(data: &[u8]) -> u32 {
    let mut c = !0u32;
    for &b in data {
        c ^= b as u32;
        for _ in 0..8 {
            c = if c & 1 != 0 { c >> 1 ^ 0xEDB8_8320 } else { c >> 1 };
        }
    }
    !c
}

/// A sealed end-of-line record for a unit that passed (eol.h; ecu.py's
/// eol_record(b"SIM", passed=1)).
pub fn eol_record_sim() -> [u8; 84] {
    let mut r = [0u8; 84];
    r[0..2].copy_from_slice(&0xE01Du16.to_le_bytes());
    r[2..4].copy_from_slice(&1u16.to_le_bytes());
    r[4..7].copy_from_slice(b"SIM");
    r[20..22].copy_from_slice(&0x0100u16.to_le_bytes()); // hw_rev, 2 pad bytes follow
    r[24..28].copy_from_slice(&20261020u32.to_le_bytes());
    for i in 0..6 {
        r[28 + 4 * i..32 + 4 * i].copy_from_slice(&1.0f32.to_le_bytes()); // gains; offsets stay 0
    }
    r[77] = 1; // station 76, passed 77, locked 78, spare 79
    let crc = crc32(&r[..80]);
    r[80..].copy_from_slice(&crc.to_le_bytes());
    r
}

#[cfg(test)]
mod tests {
    #[test]
    fn eol_matches_python() {
        // ecu.py: eol_record(b"SIM", passed=1).hex()
        let want = include_str!("../tests/eol_sim.hex").trim();
        let got: String = super::eol_record_sim().iter().map(|b| format!("{b:02x}")).collect();
        assert_eq!(got, want);
    }
}
