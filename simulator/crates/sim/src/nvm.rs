//! The persistent image (firmware/core/nvm.h), read for `expect stored`.
use crate::crc32;

const MAGIC: u16 = 0xEC25;
const VERSION: u16 = 1;
const DTCS: usize = 16;
const DTC_AT: usize = 64; // after the 16-byte header and the 48-byte counters
const DTC_LEN: usize = 24;

fn u16_at(b: &[u8], i: usize) -> u16 {
    u16::from_le_bytes([b[i], b[i + 1]])
}
fn u32_at(b: &[u8], i: usize) -> u32 {
    u32::from_le_bytes(b[i..i + 4].try_into().unwrap())
}

/// As nvm.c's nvm_valid: magic, version, length, CRC with its own field zeroed.
pub fn valid(b: &[u8]) -> bool {
    if b.len() < DTC_AT + DTCS * DTC_LEN || u16_at(b, 0) != MAGIC || u16_at(b, 2) != VERSION
        || u32_at(b, 8) as usize != b.len() {
        return false;
    }
    let mut c = b.to_vec();
    c[12..16].fill(0);
    crc32(&c) == u32_at(b, 12)
}

/// The stored DTCs (used, active or not) of the newest valid slot.
pub fn stored(slots: &[Vec<u8>; 2]) -> Option<Vec<(u32, u8)>> {
    let img = slots.iter().filter(|s| valid(s)).max_by_key(|s| u32_at(s, 4))?;
    Some((0..DTCS)
        .map(|i| DTC_AT + DTC_LEN * i)
        .filter(|&o| img[o + 5] & 0x02 != 0)
        .map(|o| (u32_at(img, o), img[o + 4]))
        .collect())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn image(seq: u32, dtc: (u32, u8)) -> Vec<u8> {
        let mut b = vec![0u8; 3036];
        b[0..2].copy_from_slice(&MAGIC.to_le_bytes());
        b[2..4].copy_from_slice(&VERSION.to_le_bytes());
        b[4..8].copy_from_slice(&seq.to_le_bytes());
        b[8..12].copy_from_slice(&3036u32.to_le_bytes());
        b[DTC_AT..DTC_AT + 4].copy_from_slice(&dtc.0.to_le_bytes());
        b[DTC_AT + 4] = dtc.1;
        b[DTC_AT + 5] = 0x02;
        let c = crc32(&b);
        b[12..16].copy_from_slice(&c.to_le_bytes());
        b
    }

    #[test]
    fn newest_valid_slot() {
        assert_eq!(stored(&[image(1, (110, 3)), image(2, (190, 0))]), Some(vec![(190, 0)]));
    }

    #[test]
    fn nvm_torn_slot_ignored() {
        let mut torn = image(2, (190, 0));
        torn[1518..].fill(0xFF);
        assert_eq!(stored(&[image(1, (110, 3)), torn]), Some(vec![(110, 3)]));
        assert_eq!(stored(&[vec![], vec![]]), None);
    }
}
