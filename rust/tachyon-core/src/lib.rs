mod ruleset_rcu;

use once_cell::sync::Lazy;
use pyo3::exceptions::PyOverflowError;
use pyo3::prelude::*;
use std::collections::VecDeque;
use std::sync::Mutex;

pub use ruleset_rcu::RcuRuleEngine;

/// 64-byte aligned packet for zero-copy friendly transfer on the hot path.
#[repr(C, align(64))]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct TachyonPacket {
    pub event_id: u128,
    pub sequence: u64,
    pub unix_ns: u64,
    pub payload_len: u32,
    pub flags: u16,
    pub reserved: u16,
    pub payload_head: [u8; 20],
}

impl TachyonPacket {
    pub fn new(event_id: u128, sequence: u64, unix_ns: u64, payload: &[u8], flags: u16) -> Self {
        let mut payload_head = [0u8; 20];
        let prefix_len = payload.len().min(payload_head.len());
        payload_head[..prefix_len].copy_from_slice(&payload[..prefix_len]);

        Self {
            event_id,
            sequence,
            unix_ns,
            payload_len: payload.len() as u32,
            flags,
            reserved: 0,
            payload_head,
        }
    }
}

static PACKET_QUEUE: Lazy<Mutex<VecDeque<TachyonPacket>>> =
    Lazy::new(|| Mutex::new(VecDeque::with_capacity(4096)));

/// Submit packet data from Python without JSON serialization in the hot path.
#[pyfunction]
pub fn submit_packet(
    event_id_hi: u64,
    event_id_lo: u64,
    sequence: u64,
    unix_ns: u64,
    payload: &[u8],
    flags: u16,
) -> PyResult<usize> {
    let payload_len = u32::try_from(payload.len())
        .map_err(|_| PyOverflowError::new_err("payload exceeds u32::MAX"))?;
    let event_id = ((event_id_hi as u128) << 64) | (event_id_lo as u128);

    let packet = TachyonPacket {
        event_id,
        sequence,
        unix_ns,
        payload_len,
        flags,
        reserved: 0,
        payload_head: {
            let mut out = [0u8; 20];
            let n = payload.len().min(20);
            out[..n].copy_from_slice(&payload[..n]);
            out
        },
    };

    let mut queue = PACKET_QUEUE
        .lock()
        .map_err(|_| PyOverflowError::new_err("packet queue lock poisoned"))?;
    queue.push_back(packet);
    Ok(queue.len())
}

#[pyfunction]
fn drain_packet_count() -> PyResult<usize> {
    let mut queue = PACKET_QUEUE
        .lock()
        .map_err(|_| PyOverflowError::new_err("packet queue lock poisoned"))?;
    let count = queue.len();
    queue.clear();
    Ok(count)
}

#[pymodule]
fn tachyon_core(_py: Python<'_>, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(submit_packet, m)?)?;
    m.add_function(wrap_pyfunction!(drain_packet_count, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tachyon_packet_is_64b_aligned() {
        assert_eq!(std::mem::align_of::<TachyonPacket>(), 64);
        assert_eq!(std::mem::size_of::<TachyonPacket>(), 64);
    }

    #[test]
    fn packet_prefix_capture_is_deterministic() {
        let payload = b"abcdefghijklmnopqrstuvwxyz";
        let packet = TachyonPacket::new(9, 10, 11, payload, 0x1);
        assert_eq!(packet.payload_len, payload.len() as u32);
        assert_eq!(&packet.payload_head[..], &payload[..20]);
    }
}
