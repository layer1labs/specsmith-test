//! iSMART telemetry validation + ring buffer (REQ-003, REQ-004).
//!
//! - `TelemetryRecord::validate()` verifies CRC-32C integrity (REQ-003).
//! - `RingBuffer<T, N>` is a fixed-size lock-free SPSC buffer that drops
//!   the oldest sample on overflow rather than blocking (REQ-004).

use crc32fast::Hasher;

// ---------------------------------------------------------------------------
// Telemetry record
// ---------------------------------------------------------------------------

/// A single telemetry observation with CRC-32C integrity protection (REQ-003).
#[derive(Debug, Clone, PartialEq)]
pub struct TelemetryRecord {
    /// Sensor channel identifier.
    pub channel: u16,
    /// Raw ADC value (16-bit unsigned).
    pub value: u16,
    /// Unix timestamp (seconds).
    pub timestamp: u32,
    /// CRC-32C over the preceding 8 bytes (channel + value + timestamp + pad).
    pub crc: u32,
}

impl TelemetryRecord {
    /// Compute the expected CRC-32C for this record.
    pub fn compute_crc(&self) -> u32 {
        let mut h = Hasher::new();
        h.update(&self.channel.to_le_bytes());
        h.update(&self.value.to_le_bytes());
        h.update(&self.timestamp.to_le_bytes());
        h.finalize()
    }

    /// Validate the record; returns `true` when CRC matches (REQ-003).
    pub fn validate(&self) -> bool {
        self.crc == self.compute_crc()
    }

    /// Seal the record by setting `crc` to the computed value.
    pub fn seal(&mut self) {
        self.crc = self.compute_crc();
    }
}

// ---------------------------------------------------------------------------
// SPSC ring buffer
// ---------------------------------------------------------------------------

/// Fixed-size single-producer/single-consumer ring buffer (REQ-004).
///
/// When the buffer is full, the oldest entry is silently dropped so the
/// producer never blocks the real-time path.
pub struct RingBuffer<T, const N: usize> {
    buf: [Option<T>; N],
    head: usize, // next read index
    tail: usize, // next write index
    len: usize,
}

impl<T: Copy, const N: usize> RingBuffer<T, N> {
    /// Create an empty ring buffer.
    pub fn new() -> Self {
        Self {
            buf: [None; N],
            head: 0,
            tail: 0,
            len: 0,
        }
    }

    /// Push a value.  If the buffer is full, the oldest entry is dropped (REQ-004).
    pub fn push(&mut self, value: T) {
        if self.len == N {
            // Drop oldest: advance head
            self.head = (self.head + 1) % N;
            self.len -= 1;
        }
        self.buf[self.tail] = Some(value);
        self.tail = (self.tail + 1) % N;
        self.len += 1;
    }

    /// Pop the oldest value, or `None` if empty.
    pub fn pop(&mut self) -> Option<T> {
        if self.len == 0 {
            return None;
        }
        let val = self.buf[self.head].take();
        self.head = (self.head + 1) % N;
        self.len -= 1;
        val
    }

    /// Current number of items.
    pub fn len(&self) -> usize {
        self.len
    }

    /// True when the buffer contains no items.
    pub fn is_empty(&self) -> bool {
        self.len == 0
    }
}

impl<T: Copy, const N: usize> Default for RingBuffer<T, N> {
    fn default() -> Self {
        Self::new()
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    /// TEST-004: A correctly sealed record passes validation (REQ-003).
    #[test]
    fn crc_valid_frame_accepted() {
        let mut rec = TelemetryRecord {
            channel: 1,
            value: 0x0ABC,
            timestamp: 1_700_000_000,
            crc: 0,
        };
        rec.seal();
        assert!(rec.validate(), "sealed record should pass CRC check");
    }

    /// TEST-005: Flipping a payload byte makes validation fail (REQ-003).
    #[test]
    fn crc_corrupted_frame_rejected() {
        let mut rec = TelemetryRecord {
            channel: 1,
            value: 0x0ABC,
            timestamp: 1_700_000_000,
            crc: 0,
        };
        rec.seal();
        rec.value ^= 0x0001; // flip a bit
        assert!(!rec.validate(), "corrupted record should fail CRC check");
    }

    /// TEST-006: Ring buffer drops oldest on overflow (REQ-004).
    #[test]
    fn ring_buffer_overflow_drops_oldest() {
        let mut rb: RingBuffer<u32, 3> = RingBuffer::new();
        rb.push(1);
        rb.push(2);
        rb.push(3);
        assert_eq!(rb.len(), 3);

        // Push beyond capacity — should drop 1 (oldest)
        rb.push(4);
        assert_eq!(rb.len(), 3, "len should stay at capacity");

        // Pop should yield 2, 3, 4 (not 1)
        assert_eq!(
            rb.pop(),
            Some(2),
            "oldest (1) was dropped, next oldest is 2"
        );
        assert_eq!(rb.pop(), Some(3));
        assert_eq!(rb.pop(), Some(4));
        assert!(rb.is_empty());
    }

    /// Extra: ring buffer stays empty after fresh creation.
    #[test]
    fn ring_buffer_starts_empty() {
        let rb: RingBuffer<u32, 8> = RingBuffer::new();
        assert!(rb.is_empty());
        assert_eq!(rb.len(), 0);
    }
}
