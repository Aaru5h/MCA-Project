# Controller and memory interface

Owner: Deepak. This describes the implemented RTL and provides the controller/memory and synthesis material for the final report. The default is still write-through with no-write-allocate. `WRITE_ALLOCATE=1` enables refill on a write miss.

## Supported parameters

- `CACHE_SIZE` and `BLOCK_SIZE` are positive integer powers of two, measured in bytes, with `4 <= BLOCK_SIZE <= CACHE_SIZE <= 2**30` for the supported 32-bit integer configurations.
- A 4-byte block and a single-line cache are supported, including `CACHE_SIZE=BLOCK_SIZE=4`. Logical index/word-select widths can be zero; their internal vectors use at least one bit, and array addresses use multiplication plus word index instead of concatenating padded selectors.
- `WRITE_ALLOCATE` must be 0 or 1. Every write reaches memory under either policy.
- `main_mem.LATENCY` and `DEPTH_WORDS` must be positive integers. The counter width follows `LATENCY`; it no longer limits waits to 65,536 cycles. Latency 65,537 was checked in simulation.
- CPU addresses must be word aligned. Memory uses word addresses and requires `0 <= addr < DEPTH_WORDS`. The full block of every allocating request must fit in the memory window; normally choose a depth that is a multiple of the words per block. The default is 4,096 words (16 KB).

Invalid geometry, policy and positive-value parameters cause a simulation-time fatal diagnostic at time zero. The memory model also diagnoses out-of-range requests when they start; it does not intentionally wrap addresses. The bounds assertion is excluded from synthesis and is not a hardware address-fault interface. CPU alignment and trace validation remain integration requirements.

## CPU handshake

All logic uses rising clock edges and an active-low **synchronous** reset. Drive inputs before the sampling edge.

1. When `busy=0`, assert `cpu_req` with `cpu_we`, byte address and write data. The next rising edge latches the request and leaves `IDLE`.
2. Deassert `cpu_req` after acceptance. Live CPU address/data/direction changes while busy do not alter the latched transaction. There is no request queue; pulses while busy are ignored.
3. `cpu_ready` pulses for one cycle after completion. Read data is valid with this pulse and then remains stored until another read or reset. Write responses do not define a new read value.
4. `busy` goes low in the same cycle as `cpu_ready`. The next request can be accepted on the following rising edge. A request held high until this edge is treated as another request, so the source must avoid unintentionally resubmitting it.

Counters increment exactly once in `COMPARE` using the state of the cache before the access. An allocating write miss counts as one miss, not a miss plus a hit. Debug tag/hit signals refer to the latched request; a tag/data entry is meaningful only when its valid bit is set.

## State transitions and allocation

| State | Action and next state |
|---|---|
| `IDLE` | Latch an accepted request, then enter `COMPARE` |
| `COMPARE` | Read hit: select data and enter `RESPOND`. Write hit: update the cache word and enter `WRITE`. Read miss: enter `ALLOCATE`. Write miss: enter `WRITE` with allocation disabled, otherwise `ALLOCATE` |
| `ALLOCATE` | Fetch all words in ascending word-address order. Forward the requested read word. For a write miss, overlay the requested word with the latched write data. Commit tag/valid after the last beat. Read: enter `RESPOND`. Write: start write-through and enter `WRITE` |
| `WRITE` | Keep the memory request active until its completion pulse, then enter `RESPOND` |
| `RESPOND` | Pulse `cpu_ready` and return to `IDLE` |

No-write-allocate misses preserve the victim line. Write-allocate misses replace it, retain neighboring words from the refill and update the backing memory before acknowledging the CPU. The refill deliberately reads every word, including the word that will be overwritten. This is a blocking controller; there is no CPU access to a partially refilled line.

## Memory handshake

The cache outputs word addresses (`cpu_addr >> 2`), direction and write data with `mem_req`. Memory latches those controls on the first active request edge, waits `LATENCY` edges including that first edge, performs the operation and raises `ready`. For `LATENCY=1`, sampling and completion occur on the same edge.

The cache consumes the registered `mem_ready` pulse on the next rising edge. The memory skips that edge because its previous `ready` is high. This **one-edge bubble** lets the cache advance the address or switch the last refill read to a write before memory samples the next word. Keep this behavior when integrating another memory model; this is not an arbitrary ready/valid bus protocol.

With `req` held high, the next word starts after the bubble. With `req` low, an unfinished word is canceled and the wait counter clears. Controls changed after a word has started cannot redirect it. Completed writes are retained even if the request is subsequently withdrawn.

## Reset and recovery

Reset both modules together. Reset clears cache valid bits, counters, request/output registers, beat count and state; it cancels the memory wait and clears its ready/read-data outputs. Data/tag arrays are invalidated through their valid bits rather than cleared. Main-memory storage retains its contents; its known `0xC0DE0000 + word_index` pattern is applied only at initialization.

A reset during refill cannot expose a partially refilled line as valid. A reset before a memory write's completion cancels that word; a write committed on an earlier edge remains committed even if its CPU response is interrupted. There is no rollback guarantee. An illegal controller state recovers to idle, cancels memory outputs and invalidates cache lines; it does not issue a successful response for the interrupted request.

## Cycle costs and measured latency

The convention matches `tb_trace.v`: drive on the falling edge and count rising edges through completion, **including the CPU acceptance edge as cycle 1**. A read hit therefore counts three cycles: accept, compare, respond. This is not the edge-distance convention that would label the same interval two clock periods.

Let `W = BLOCK_SIZE / 4` and `L = LATENCY`. With the supplied memory model:

| Access | CPU cycles | Memory transactions |
|---|---|---|
| Read hit | `3` | None |
| Read miss | `3 + W * (L + 1)` | `W` reads |
| Write hit, either policy | `3 + (L + 1)` | One write |
| Write miss, no-write-allocate | `3 + (L + 1)` | One write |
| Write miss, write-allocate | `3 + (W + 1) * (L + 1)` | `W` reads and one write |

The extra `1` per memory word is the registered completion/ready handoff. It is also paid when transitioning from refill to write-through. Measured for a 1 KB cache and 16-byte blocks:

| Memory latency | Read hit | Read miss | Write hit | Write miss, no allocation | Write miss, allocation |
|---|---:|---:|---:|---:|---:|
| 1 | 3 | 11 | 5 | 5 | 13 |
| 2 | 3 | 15 | 6 | 6 | 18 |
| 4 | 3 | 23 | 8 | 8 | 28 |
| 8 | 3 | 39 | 12 | 12 | 48 |

Raw outputs, CSV and reproduction commands are in [the latency results](results/deepak_latency/README.md). The known mixed-traffic AMAT and no-cache-baseline issues in the shared testbench remain assigned to Utkarsh; these results use individual operation timings, not those aggregate outputs.

## Validation and handoff

Implementation checks used Icarus Verilog 13.0 and Yosys 0.71+post:

- Both existing traces passed data checks for six geometries: 1 KB/16 B, 512 B/16 B, 1 KB/32 B, 64 B/4 B, 16 B/16 B and 4 B/4 B. Default-policy hit/miss counts for the first three match the existing documentation.
- Temporary focused controller checks passed all 48 combinations of those six geometries, latency 1/2/4/8 and both policies. They checked every possible target word on a cold write miss, neighboring data, conflicts, deterministic randomized traffic, counters, memory transaction counts, exact cycle costs, changed live CPU inputs, backing-memory contents, reset interruption and illegal-state recovery.
- Focused memory checks passed at latency 1/2/4/8/65,537, including latched controls, cancellation, ready pulse width and reset/storage preservation. Invalid geometry, policy, memory parameters and out-of-range addresses were rejected.
- Both default-size policy variants synthesized with zero warnings, passed structural/latch checks and passed focused simulation using their generated netlists. Boundary geometries also synthesized. See [synthesis evidence](synthesis/README.md).

The temporary focused checks were implementation validation, not the team's permanent verification suite or a formal proof. Kushagra still owns the permanent directed tests, trace generator, policy-aware Python model and regression runner. Meet owns workload sweeps, diagrams and annotated waveforms. Utkarsh owns performance accounting, a measured no-cache benchmark and final report/video assembly. This change does not implement those packages.
