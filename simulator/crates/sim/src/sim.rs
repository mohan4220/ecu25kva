//! The loop of firmware/sim/run_sil.py's Sim.run: the plant every 20 us,
//! edges in time order, the firmware's 1 ms tick, saves, CAN, one trace
//! row per ms.
use crate::j1939::{Bam, Msg};
use crate::{eol_record_sim, Claim, EcuCan, EcuIo, Firmware};
use plant::{Engine, NCYL};
use std::sync::Arc;

pub const STEP_US: u32 = 20;
pub const RUN: u8 = 3;
pub const SHUTDOWN: u8 = 4;
pub const STATES: [&str; 5] = ["OFF", "WAIT", "CRANK", "RUN", "SHUTDOWN"];

/// One trace row, recorded after each 1 ms tick.
#[derive(Clone, Debug, Default)]
pub struct Row {
    pub t_ms: u64,
    pub rpm: f64,
    pub ecu_rpm: f32,
    pub state: u8,
    pub synced: u8,
    pub rail: f64,
    pub rail_set: f32,
    pub duty: f32,
    pub fuel: f32,
    pub load: f64,
    pub clt: f64,
    pub oil: f32,
    pub wdg: u8,
    pub starter: bool,
    pub ignition: u8,
}

#[derive(Clone, Debug)]
pub struct CanRec {
    pub t_ms: u64,
    pub rx: bool,
    pub id: u32,
    pub data: Vec<u8>,
}

pub struct Sim {
    pub fw: Arc<Firmware>,
    pub eng: Engine,
    pub io: Box<EcuIo>,
    pub t_us: u64,
    pub trace: Vec<Row>,
    pub can: Vec<CanRec>,
    pub msgs: Vec<Msg>,
    pub states: Vec<(u64, u8)>, // (t_us, new state)
    pub events: Vec<String>,    // actions applied, as script lines
    pub slots: [Vec<u8>; 2],    // the two NVM slots, as the host's flash
    pub tear_next: bool,        // the next save is cut halfway by a power loss
    pub torn: bool,
    pub saves: u32,
    pub release_on_run: bool, // starter off at the first ms in RUN
    pub bounce_until: Option<u64>, // ignition back on at this t_us
    next_ms: u64,
    sent: [u32; NCYL],
    state: u8,
    bam: Bam,
    edges: Vec<(u64, bool)>,
    _claim: Claim,
}

impl Sim {
    /// Claims the firmware (waits if another Sim has it) and starts it
    /// as run_sil's Sim: init, ignition on, both slots, a passed EOL record.
    pub fn new(fw: Arc<Firmware>) -> Sim {
        let claim = fw.claim();
        let mut s = Sim {
            fw,
            eng: Engine::new(),
            io: EcuIo::new(),
            t_us: 0,
            trace: vec![],
            can: vec![],
            msgs: vec![],
            states: vec![],
            events: vec![],
            slots: [vec![], vec![]],
            tear_next: false,
            torn: false,
            saves: 0,
            release_on_run: false,
            bounce_until: None,
            next_ms: 1000,
            sent: [0; NCYL],
            state: 0,
            bam: Bam::default(),
            edges: Vec::with_capacity(8),
            _claim: claim,
        };
        s.boot(0);
        s
    }

    fn boot(&mut self, droop: u8) {
        self.fw.init(&mut self.io);
        self.io.ignition = 1;
        self.io.droop_sw = droop;
        self.io.reset_cause = 0;
        self.volts();
        let [a, b] = &self.slots;
        self.fw.nvm_load(&mut self.io, a, b);
        let eol = eol_record_sim();
        self.fw.eol_load(&mut self.io, &eol, &eol);
        self.sent = [0; NCYL];
        self.state = self.io.state;
    }

    /// Power off and on: a fresh ECU reloads both slots; the engine runs on.
    /// The droop switch keeps its position.
    pub fn power_cycle(&mut self) {
        let droop = self.io.droop_sw;
        self.boot(droop);
        self.eng.clear_commands();
    }

    fn volts(&mut self) {
        let v = self.eng.volts();
        let io = &mut self.io;
        [io.v_clt, io.v_oil, io.v_rail, io.v_boost, io.v_egr, io.v_5v] = v.map(|x| x as f32);
    }

    fn after(&mut self, t_us: u64) {
        for k in 0..NCYL {
            let inj = self.io.inj[k];
            if inj.seq != self.sent[k] {
                self.sent[k] = inj.seq;
                self.eng.command(k, inj.start_us, inj.dur_us, inj.seq);
            }
        }
        if self.io.state != self.state {
            self.state = self.io.state;
            self.states.push((t_us, self.state));
            let name = STATES.get(self.state as usize).unwrap_or(&"?");
            self.events.push(format!("# {} state {name}", crate::seq::secs(t_us)));
        }
    }

    /// Advance exactly 1 ms of simulated time.
    pub fn step_ms(&mut self) {
        loop {
            self.edges.clear();
            let mut edges = std::mem::take(&mut self.edges);
            self.eng.step(self.t_us, STEP_US, &mut edges);
            edges.sort_unstable();
            for &(te, cam) in &edges {
                if cam {
                    self.fw.cam_edge(&mut self.io, te as u32);
                } else {
                    self.fw.crank_edge(&mut self.io, te as u32);
                }
                self.after(te);
            }
            self.edges = edges;
            self.eng.duty = self.io.meter_duty as f64;
            self.t_us += STEP_US as u64;
            if self.t_us >= self.next_ms {
                break;
            }
        }
        let t = self.next_ms;
        if self.bounce_until.is_some_and(|b| self.t_us >= b) {
            self.io.ignition = 1;
            self.bounce_until = None;
        }
        self.volts();
        self.fw.tick_1ms(&mut self.io, t as u32);
        self.fw.background(&mut self.io);
        if self.io.nvm_save != 0 {
            let mut img = self.fw.nvm_image();
            if self.tear_next {
                let h = img.len() / 2;
                img[h..].fill(0xFF); // the rest of the slot stays erased flash
                self.tear_next = false;
                self.torn = true;
            }
            self.slots[self.io.nvm_slot as usize & 1] = img;
            self.io.nvm_save = 0;
            self.saves += 1;
        }
        let t_ms = t / 1000;
        for i in 0..self.io.can_n as usize {
            let f = self.io.can[i];
            self.can.push(CanRec { t_ms, rx: false, id: f.id, data: f.data[..f.len as usize].to_vec() });
            if let Some(m) = self.bam.push(t_ms, &f) {
                self.msgs.push(m);
            }
        }
        self.io.can_n = 0;
        self.io.can2_n = 0; // the service link: no tester here
        self.io.usb_out_n = 0;
        self.after(t);
        let io = &self.io;
        self.trace.push(Row {
            t_ms,
            rpm: self.eng.rpm(),
            ecu_rpm: io.rpm,
            state: io.state,
            synced: io.synced,
            rail: self.eng.rail_bar,
            rail_set: self.fw.rail_set_bar(io.fuel_mg),
            duty: io.meter_duty,
            fuel: io.fuel_mg,
            load: self.eng.load_kw,
            clt: self.eng.clt_c,
            oil: io.oil_kpa,
            wdg: io.wdg,
            starter: self.eng.starter,
            ignition: io.ignition,
        });
        if self.release_on_run && io.state == RUN {
            self.eng.starter = false;
            self.release_on_run = false;
        }
        self.next_ms += 1000;
    }

    /// A global J1939 request from a tool at address 3.
    pub fn request(&mut self, pgn: u32) {
        let mut f = EcuCan { id: 0x18EAFF03, len: 3, data: [0; 8] };
        f.data[..3].copy_from_slice(&pgn.to_le_bytes()[..3]);
        self.fw.can_rx(&mut self.io, &f);
        self.can.push(CanRec { t_ms: self.t_us / 1000, rx: true, id: f.id, data: f.data[..3].to_vec() });
    }
}
