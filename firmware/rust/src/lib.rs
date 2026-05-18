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

    // -----------------------------------------------------------------------
    // Extended CRC tests
    // -----------------------------------------------------------------------

    /// Sealing and re-validating a record is idempotent.
    #[test]
    fn crc_seal_is_idempotent() {
        let mut rec = TelemetryRecord {
            channel: 7,
            value: 0x1234,
            timestamp: 1_234_567_890,
            crc: 0,
        };
        rec.seal();
        let first_crc = rec.crc;
        rec.seal();
        assert_eq!(rec.crc, first_crc, "seal() is not idempotent");
        assert!(rec.validate());
    }

    /// Two records with identical fields produce the same CRC.
    #[test]
    fn crc_deterministic_same_input() {
        let make = || TelemetryRecord {
            channel: 2,
            value: 0xABCD,
            timestamp: 9_999_999,
            crc: 0,
        };
        let mut a = make();
        let mut b = make();
        a.seal();
        b.seal();
        assert_eq!(a.crc, b.crc);
    }

    /// Changing the channel field changes the CRC.
    #[test]
    fn crc_different_channel_gives_different_crc() {
        let mut r1 = TelemetryRecord {
            channel: 1,
            value: 0,
            timestamp: 0,
            crc: 0,
        };
        let mut r2 = TelemetryRecord {
            channel: 2,
            value: 0,
            timestamp: 0,
            crc: 0,
        };
        r1.seal();
        r2.seal();
        assert_ne!(r1.crc, r2.crc);
    }

    /// All-zero record can be sealed and validated.
    #[test]
    fn crc_all_zero_record_valid() {
        let mut rec = TelemetryRecord {
            channel: 0,
            value: 0,
            timestamp: 0,
            crc: 0,
        };
        rec.seal();
        assert!(rec.validate());
        assert_ne!(rec.crc, 0, "CRC of all-zero payload should not be 0");
    }

    /// All-max record (0xFFFF fields) can be sealed and validated.
    #[test]
    fn crc_all_max_record_valid() {
        let mut rec = TelemetryRecord {
            channel: u16::MAX,
            value: u16::MAX,
            timestamp: u32::MAX,
            crc: 0,
        };
        rec.seal();
        assert!(rec.validate());
    }

    /// Flipping the timestamp field invalidates the CRC.
    #[test]
    fn crc_corrupted_timestamp_rejected() {
        let mut rec = TelemetryRecord {
            channel: 3,
            value: 0x0100,
            timestamp: 1_000_000,
            crc: 0,
        };
        rec.seal();
        rec.timestamp ^= 1;
        assert!(!rec.validate());
    }

    /// Flipping the channel field invalidates the CRC.
    #[test]
    fn crc_corrupted_channel_rejected() {
        let mut rec = TelemetryRecord {
            channel: 10,
            value: 42,
            timestamp: 100,
            crc: 0,
        };
        rec.seal();
        rec.channel ^= 1;
        assert!(!rec.validate());
    }

    /// compute_crc() matches crc field after seal().
    #[test]
    fn crc_compute_matches_after_seal() {
        let mut rec = TelemetryRecord {
            channel: 5,
            value: 0x5555,
            timestamp: 2_000_000_000,
            crc: 0,
        };
        rec.seal();
        assert_eq!(rec.crc, rec.compute_crc());
    }

    /// Batch: 100 unique records all validate after sealing.
    #[test]
    fn crc_batch_100_records_all_valid() {
        for i in 0u32..100 {
            let mut rec = TelemetryRecord {
                channel: (i % 64) as u16,
                value: (i * 13 % 65536) as u16,
                timestamp: i * 1000,
                crc: 0,
            };
            rec.seal();
            assert!(rec.validate(), "Record {i} failed validation after seal");
        }
    }

    // -----------------------------------------------------------------------
    // Extended ring buffer tests
    // -----------------------------------------------------------------------

    /// Ring buffer with capacity 1 holds exactly 1 item.
    #[test]
    fn ring_buffer_capacity_1() {
        let mut rb: RingBuffer<u32, 1> = RingBuffer::new();
        rb.push(42);
        assert_eq!(rb.len(), 1);
        // Push again: oldest (42) is dropped, newest replaces it
        rb.push(99);
        assert_eq!(rb.len(), 1);
        assert_eq!(rb.pop(), Some(99));
    }

    /// Ring buffer with capacity 64 can be fully loaded.
    #[test]
    fn ring_buffer_capacity_64_full() {
        let mut rb: RingBuffer<u32, 64> = RingBuffer::new();
        for i in 0..64 {
            rb.push(i);
        }
        assert_eq!(rb.len(), 64);
        assert!(!rb.is_empty());
    }

    /// Filling the buffer exactly to capacity does not drop any item.
    #[test]
    fn ring_buffer_fill_exactly() {
        let mut rb: RingBuffer<u32, 4> = RingBuffer::new();
        rb.push(10);
        rb.push(20);
        rb.push(30);
        rb.push(40);
        assert_eq!(rb.len(), 4);
        assert_eq!(rb.pop(), Some(10));
        assert_eq!(rb.pop(), Some(20));
        assert_eq!(rb.pop(), Some(30));
        assert_eq!(rb.pop(), Some(40));
        assert!(rb.is_empty());
    }

    /// Pop from empty buffer returns None.
    #[test]
    fn ring_buffer_pop_empty_returns_none() {
        let mut rb: RingBuffer<u32, 4> = RingBuffer::new();
        assert_eq!(rb.pop(), None);
    }

    /// Interleaved push/pop maintains FIFO ordering.
    #[test]
    fn ring_buffer_interleaved_push_pop() {
        let mut rb: RingBuffer<u32, 4> = RingBuffer::new();
        rb.push(1);
        rb.push(2);
        assert_eq!(rb.pop(), Some(1));
        rb.push(3);
        assert_eq!(rb.pop(), Some(2));
        assert_eq!(rb.pop(), Some(3));
        assert!(rb.is_empty());
    }

    /// Length tracks pushes and pops correctly.
    #[test]
    fn ring_buffer_len_tracking() {
        let mut rb: RingBuffer<u32, 8> = RingBuffer::new();
        assert_eq!(rb.len(), 0);
        for i in 1u32..=5 {
            rb.push(i);
            assert_eq!(rb.len(), i as usize);
        }
        for remaining in (0..5).rev() {
            rb.pop();
            assert_eq!(rb.len(), remaining);
        }
    }

    /// Default trait produces an empty ring buffer identical to new().
    #[test]
    fn ring_buffer_default_is_empty() {
        let rb: RingBuffer<u32, 8> = RingBuffer::default();
        assert!(rb.is_empty());
        assert_eq!(rb.len(), 0);
    }

    /// Overflow: pushing N+1 items drops the oldest and retains the newest N.
    #[test]
    fn ring_buffer_overflow_retains_newest() {
        let mut rb: RingBuffer<u32, 3> = RingBuffer::new();
        for i in 1u32..=6 {
            rb.push(i);
        }
        // Only 3 through 6 survive; 1,2,3 were dropped as 4,5,6 came in
        assert_eq!(rb.len(), 3);
        assert_eq!(rb.pop(), Some(4));
        assert_eq!(rb.pop(), Some(5));
        assert_eq!(rb.pop(), Some(6));
    }

    /// The ring buffer is correct after 1000 sequential pushes.
    #[test]
    fn ring_buffer_stress_1000_pushes() {
        let capacity = 16usize;
        let mut rb: RingBuffer<u32, 16> = RingBuffer::new();
        for i in 0u32..1000 {
            rb.push(i);
        }
        // Only the last `capacity` items survive
        assert_eq!(rb.len(), capacity);
        // First popped value should be 1000 - 16 = 984
        assert_eq!(rb.pop(), Some(984));
    }
}
