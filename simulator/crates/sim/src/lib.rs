//! The firmware against the engine model: binding, loop, scripts, checks.
pub mod fw;
pub mod j1939;
pub mod nvm;
pub mod sim;
pub use fw::{crc32, eol_record_sim, Claim, EcuCan, EcuInj, EcuIo, Firmware};
pub use sim::{CanRec, Row, Sim};
