//! J1939 as the simulator reads it: PGNs, BAM reassembly, DTC lists.
use crate::EcuCan;

pub const DM1: u32 = 0xFECA;
pub const DM2: u32 = 0xFECB;
pub const DM3: u32 = 0xFECC;
pub const DM4: u32 = 0xFECD;
pub const HOURS: u32 = 0xFEE5;

/// As run_sil.pgn: PF and PS (a PDU1 frame's PS is its destination).
pub fn pgn(id: u32) -> u32 {
    id >> 8 & 0xFFFF
}

pub fn name(pgn: u32) -> &'static str {
    match pgn {
        0xF004 => "EEC1",
        0xFEEE => "ET1",
        0xFEEF => "EFL/P1",
        DM1 => "DM1",
        DM2 => "DM2",
        DM3 => "DM3",
        DM4 => "DM4",
        HOURS => "HOURS",
        p if p & 0xFF00 == 0xEC00 => "TP.CM",
        p if p & 0xFF00 == 0xEB00 => "TP.DT",
        p if p & 0xFF00 == 0xEA00 => "REQUEST",
        _ => "",
    }
}

/// One whole J1939 message: a single frame, or a BAM put back together.
#[derive(Clone, Debug, PartialEq)]
pub struct Msg {
    pub t_ms: u64,
    pub pgn: u32,
    pub data: Vec<u8>,
}

/// Reassembles TP.CM BAM + TP.DT into messages; other frames pass through.
#[derive(Default)]
pub struct Bam {
    open: Option<(u32, usize, u8, Vec<u8>)>, // pgn, size, packets, data so far
}

impl Bam {
    pub fn push(&mut self, t_ms: u64, f: &EcuCan) -> Option<Msg> {
        let p = pgn(f.id);
        let d = &f.data[..f.len as usize];
        if p & 0xFF00 == 0xEC00 {
            if d.len() == 8 && d[0] == 32 {
                let size = d[1] as usize | (d[2] as usize) << 8;
                let target = d[5] as u32 | (d[6] as u32) << 8 | (d[7] as u32) << 16;
                self.open = Some((target, size, d[3], Vec::with_capacity(size + 7)));
            }
            return None;
        }
        if p & 0xFF00 == 0xEB00 {
            let (target, size, pk, mut buf) = self.open.take()?;
            if d.is_empty() || d[0] as usize != buf.len() / 7 + 1 {
                return None; // out of sequence: drop the message
            }
            buf.extend_from_slice(&d[1..]);
            if d[0] == pk {
                buf.truncate(size);
                return Some(Msg { t_ms, pgn: target, data: buf });
            }
            self.open = Some((target, size, pk, buf));
            return None;
        }
        Some(Msg { t_ms, pgn: p, data: d.to_vec() })
    }
}

/// (spn, fmi) pairs of a DM1/DM2; the all-zero DTC means none.
pub fn dtcs(data: &[u8]) -> Vec<(u32, u8)> {
    let mut out = vec![];
    let mut i = 2;
    while i + 3 < data.len() {
        let spn = data[i] as u32 | (data[i + 1] as u32) << 8 | ((data[i + 2] & 0xE0) as u32) << 11;
        if spn != 0 {
            out.push((spn, data[i + 2] & 0x1F));
        }
        i += 4;
    }
    out
}

pub fn lamps(data: &[u8]) -> u8 {
    data.first().copied().unwrap_or(0)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn frame(id: u32, d: &[u8]) -> EcuCan {
        let mut f = EcuCan { id, len: d.len() as u8, data: [0xFF; 8] };
        f.data[..d.len()].copy_from_slice(d);
        f
    }

    #[test]
    fn bam_two_dtcs() {
        // lamps, 0xFF, 110/3 oc 1, 100/4 oc 1: 10 bytes
        let body = [0x04, 0xFF, 110, 0, 3, 1, 100, 0, 4, 1];
        let mut b = Bam::default();
        assert!(b.push(1, &frame(0x1CECFFEA, &[32, 10, 0, 2, 0xFF, 0xCA, 0xFE, 0])).is_none());
        let mut d1 = vec![1];
        d1.extend_from_slice(&body[..7]);
        assert!(b.push(1, &frame(0x1CEBFFEA, &d1)).is_none());
        let mut d2 = vec![2];
        d2.extend_from_slice(&body[7..]);
        d2.resize(8, 0xFF);
        let m = b.push(2, &frame(0x1CEBFFEA, &d2)).unwrap();
        assert_eq!((m.t_ms, m.pgn), (2, DM1));
        assert_eq!(m.data, body);
        assert_eq!(dtcs(&m.data), vec![(110, 3), (100, 4)]);
        assert_eq!(lamps(&m.data), 0x04);
    }

    #[test]
    fn single_frame_passthrough() {
        let mut b = Bam::default();
        let m = b.push(5, &frame(0x18FECAEA, &[0, 0xFF, 0, 0, 0, 0, 0xFF, 0xFF])).unwrap();
        assert_eq!(m.pgn, DM1);
        assert!(dtcs(&m.data).is_empty());
        assert_eq!(name(pgn(0x0CF004EA)), "EEC1");
    }
}
