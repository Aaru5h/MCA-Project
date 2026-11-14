# Address-field derivation

The cache receives a 32-bit **byte** address. A direct-mapped cache splits it into three fields:

```
 31                          10 9          4 3      2 1      0
+------------------------------+------------+--------+--------+
|             tag              |   index    |  word  |  byte  |
+------------------------------+------------+--------+--------+
                                             \______________/
                                                 offset
```

| Field | What it does |
|---|---|
| **offset** | Picks the byte inside the block. The upper offset bits pick the 32-bit word, and the lowest 2 bits pick the byte inside that word. |
| **index** | Picks which cache line to look in. A direct-mapped cache has exactly one possible line per address. |
| **tag** | Stored next to the line, so the cache can tell *which* memory block is in that line right now. |

## Default configuration: 1 KB cache, 16-byte blocks

**Step 1: offset.** One block holds 16 bytes, and naming one of 16 bytes needs log2(16) = **4 bits**.
That breaks down as 16 B / 4 B = 4 words per block, so log2(4) = 2 bits choose the word and 2 bits choose the byte.

**Step 2: number of lines.** 1024 B / 16 B = **64 lines**.

**Step 3: index.** Naming one of 64 lines needs log2(64) = **6 bits**.

**Step 4: tag.** The tag is everything left over: 32 − 6 − 4 = **22 bits**.

| Field | Calculation | Bits | Address bits |
|---|---|---|---|
| Offset | log2(16 B) | 4 | `[3:0]` (word `[3:2]`, byte `[1:0]`) |
| Lines | 1024 / 16 | 64 | — |
| Index | log2(64) | 6 | `[9:4]` |
| Tag | 32 − 6 − 4 | 22 | `[31:10]` |

### Storage this implies

| Structure | Size |
|---|---|
| Data array | 64 lines × 4 words × 32 bits = 8192 bits (1 KB) |
| Tag array | 64 × 22 bits = 1408 bits |
| Valid bits | 64 × 1 bit |

The cache stores about 1.4 Kbit of tags and valid bits on top of the 8 Kbit of data.

### Worked examples

| Address | Tag (hex) | Index | Word | Note |
|---|---|---|---|---|
| `0x0000_0040` | `0x000000` | 4 | 0 | |
| `0x0000_004C` | `0x000000` | 4 | 3 | same block as 0x40, so a hit after 0x40 is loaded |
| `0x0000_0440` | `0x000001` | 4 | 0 | **same index, different tag**, so it conflicts with 0x40 |
| `0x0000_0800` | `0x000002` | 0 | 0 | |

Any two addresses exactly 1 KB (the cache size) apart have the same index but different tags. They keep evicting each other, which is a *conflict miss*.

## Why the fields are in this order

- **Index from the middle bits:** consecutive blocks in memory then go to *different* lines. A sequential walk fills the whole cache before anything gets evicted. If the index came from the top bits, a large contiguous array would all map to the same few lines.
- **Tag from the top bits:** the top bits are what is left once the line and the byte are known, so they are exactly what tells apart the different blocks that can share a line.
- **Valid bit:** after reset the tag array holds garbage. Without a valid bit, a garbage tag could happen to match and return wrong data as a "hit". The RTL clears every valid bit on reset.

## Other configurations

The RTL takes `CACHE_SIZE` and `BLOCK_SIZE` as parameters and derives every width with `$clog2`, so no other edits are needed. Formulas:

```
offset = log2(BLOCK_SIZE)
lines  = CACHE_SIZE / BLOCK_SIZE
index  = log2(lines)
tag    = 32 - index - offset
```

| Cache | Block | Lines | Offset | Index | Tag | Predicted | Printed by simulation |
|---|---|---|---|---|---|---|---|
| 1 KB | 16 B | 64 | 4 | 6 | 22 | 22 / 6 / 4 | 22 / 6 / 4 ✓ |
| 512 B | 16 B | 32 | 4 | 5 | 23 | 23 / 5 / 4 | 23 / 5 / 4 ✓ |
| 1 KB | 32 B | 32 | 5 | 5 | 22 | 22 / 5 / 5 | 22 / 5 / 5 ✓ |

- **Halving the cache (512 B)** removes one index bit, and that bit moves into the tag (22 → 23).
- **Doubling the block (32 B)** moves one bit from index to offset. The tag stays at 22, because the cache size, and therefore the number of tags that can share one line, is unchanged.

The "printed by simulation" column comes from `tb/tb_trace.v`, which prints the widths the RTL actually derived. See `docs/results/config_check.md`.
