# Controller latency measurements

Owner: Deepak. These are single-operation timing checks for the supplied controller/memory interface, not workload performance sweeps or a measured no-cache comparison. Configuration: 1 KB, 16-byte blocks. Icarus Verilog 13.0 was used. `cycles.csv` summarizes the measured operation timings; `latency*_wa*.txt` preserves the raw testbench output.

Two short inputs isolate operation classes:

- `read_write_hit`: a cold read, a neighboring read hit, a write hit and a read of the updated word. It measures read miss, read hit and write hit.
- `write_miss`: a cold write followed by a read of that word. It measures write-miss cost; the following read misses under no-write-allocate and hits under write-allocate.

The raw output is from the existing, unmodified team testbench. Its AMAT calculation, estimated no-cache baseline and fallback timings for missing read classes have known limitations. Use the operation-class measurements shown above and in the CSV; do not interpret every raw printed timing as a measured class. For example, the allocation-enabled `write_miss` input has no read miss, so its printed read-miss time is a fallback. The read-miss values in the CSV always come from `read_write_hit` instead.

## Reproduce

Run from the repository root. The temporary override enables the policy without changing another member's testbench. Select it as a second top module so its `defparam` is elaborated.

```bash
latency_dir=$(mktemp -d)
cat > "$latency_dir/read_write_hit.trace" <<'TRACE'
R 00000000
R 00000004
W 00000004 12345678
R 00000004
TRACE
cat > "$latency_dir/write_miss.trace" <<'TRACE'
W 0000000C AABBCCDD
R 0000000C
TRACE
cat > "$latency_dir/write_allocate_override.v" <<'VERILOG'
`timescale 1ns/1ps
module write_allocate_override;
    defparam tb_trace.dut.WRITE_ALLOCATE = 1;
endmodule
VERILOG

for memory_latency in 1 2 4 8; do
    iverilog -g2012 -Wall -s tb_trace \
        -Ptb_trace.LATENCY="$memory_latency" \
        -o "$latency_dir/no_allocate" \
        rtl/main_mem.v rtl/dm_cache.v tb/tb_trace.v
    iverilog -g2012 -Wall -s tb_trace -s write_allocate_override \
        -Ptb_trace.LATENCY="$memory_latency" \
        -o "$latency_dir/allocate" \
        rtl/main_mem.v rtl/dm_cache.v tb/tb_trace.v \
        "$latency_dir/write_allocate_override.v"
    for policy in no_allocate allocate; do
        for input_trace in read_write_hit write_miss; do
            vvp "$latency_dir/$policy" \
                +TRACE="$latency_dir/$input_trace.trace" \
                > "$latency_dir/latency${memory_latency}_${policy}_${input_trace}.txt"
        done
    done
done
printf 'Inspect DATA CHECK PASSED and operation timings in %s\n' "$latency_dir"
```

Expect each data check to pass. At latency 4, `read_write_hit` reports hit time 3, read-miss time 23 and write time 8 under either policy. `write_miss` reports write time 8 with allocation disabled and 28 with allocation enabled. Full timing formulas and reset semantics are in [the controller notes](../../controller_memory.md).
