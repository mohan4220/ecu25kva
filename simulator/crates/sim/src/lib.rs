//! The firmware against the engine model: binding, loop, scripts, checks.
pub mod fw;
pub use fw::{crc32, eol_record_sim, Claim, EcuCan, EcuInj, EcuIo, Firmware};
