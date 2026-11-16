`timescale 1ns/1ps
// =============================================================================
// tb_trace.v - trace-driven testbench for dm_cache
//
// Build (default 1 KB / 16 B / latency 4):
//   iverilog -g2012 -o sim_trace rtl/main_mem.v rtl/dm_cache.v tb/tb_trace.v
// Build another configuration (no RTL edits needed):
//   iverilog -g2012 -Ptb_trace.CACHE_SIZE=512 -Ptb_trace.BLOCK_SIZE=32 \
//            -Ptb_trace.LATENCY=8 -o sim_trace rtl/main_mem.v rtl/dm_cache.v tb/tb_trace.v
// Run:
//   vvp sim_trace +TRACE=traces/smoke.trace
//
// Trace format, one access per line (hex, no 0x prefix):
//   R <addr>
//   W <addr> <data>
// Blank lines and lines starting with '#' are ignored.
//
// Every read is checked against a reference copy of memory, so a wrong
// value from the cache is reported even if the hit/miss counts look fine.
// =============================================================================
module tb_trace;
    parameter CACHE_SIZE     = 1024;
    parameter BLOCK_SIZE     = 16;
    parameter WRITE_ALLOCATE = 0;
    parameter LATENCY        = 4;
    localparam MEM_WORDS     = 4096;            // 16 KB memory window

    // ---------------- clock, reset, cycle counter ----------------
    reg clk = 1'b0;
    reg rst_n = 1'b0;
    always #5 clk = ~clk;

    integer cycle = 0;
    always @(posedge clk) cycle <= cycle + 1;

    // Simulation watchdog (50 ms wall-time equivalent in sim time)
    initial begin
        #50_000_000;
        $display("[FATAL WATCHDOG] Simulation timeout exceeded at cycle %0d", cycle);
        $fatal(1, "Simulation watchdog expired");
    end

    // ---------------- DUT wiring ----------------
    reg         cpu_req = 0, cpu_we = 0;
    reg  [31:0] cpu_addr = 0, cpu_wdata = 0;
    wire [31:0] cpu_rdata;
    wire        cpu_ready, busy;
    wire        mem_req, mem_we, mem_ready;
    wire [31:0] mem_addr, mem_wdata, mem_rdata;
    wire [31:0] hit_count, miss_count, dbg_tag;
    wire        dbg_hit, dbg_valid;

    dm_cache #(
        .CACHE_SIZE(CACHE_SIZE),
        .BLOCK_SIZE(BLOCK_SIZE),
        .WRITE_ALLOCATE(WRITE_ALLOCATE)
    ) dut (
        .clk(clk), .rst_n(rst_n),
        .cpu_req(cpu_req), .cpu_we(cpu_we), .cpu_addr(cpu_addr), .cpu_wdata(cpu_wdata),
        .cpu_rdata(cpu_rdata), .cpu_ready(cpu_ready), .busy(busy),
        .mem_req(mem_req), .mem_we(mem_we), .mem_addr(mem_addr), .mem_wdata(mem_wdata),
        .mem_rdata(mem_rdata), .mem_ready(mem_ready),
        .hit_count(hit_count), .miss_count(miss_count),
        .dbg_hit(dbg_hit), .dbg_tag(dbg_tag), .dbg_valid(dbg_valid));

    main_mem #(.LATENCY(LATENCY), .DEPTH_WORDS(MEM_WORDS)) memory (
        .clk(clk), .rst_n(rst_n),
        .req(mem_req), .we(mem_we), .addr(mem_addr), .wdata(mem_wdata),
        .rdata(mem_rdata), .ready(mem_ready));

    // ---------------- reference model + statistics ----------------
    reg [31:0] ref_mem [0:MEM_WORDS-1];

    integer n_access = 0, n_read = 0, n_write = 0, n_err = 0;
    integer total_cyc = 0;
    integer rd_hit_n = 0,  rd_hit_cyc = 0;   // read hits
    integer rd_miss_n = 0, rd_miss_cyc = 0;  // read misses
    integer wr_n = 0,      wr_cyc = 0;       // writes (always go to memory)

    // One CPU access: drive the request, wait for cpu_ready with bounded timeout, record cost
    task automatic do_access(input bit is_write, input [31:0] a, input [31:0] d, input integer line_no);
        integer start, cost, hits_before, wait_limit, wait_cnt;
        bit was_hit;
        begin
            hits_before = hit_count;
            @(negedge clk);
            cpu_req = 1; cpu_we = is_write; cpu_addr = a; cpu_wdata = d;
            start = cycle;
            @(negedge clk);
            cpu_req = 0;

            // Bounded wait watchdog: fail fatally if controller hangs
            wait_limit = 2000 + (LATENCY * (BLOCK_SIZE / 4) * 20);
            wait_cnt   = 0;
            while (!cpu_ready && wait_cnt < wait_limit) begin
                @(negedge clk);
                wait_cnt = wait_cnt + 1;
            end

            if (wait_cnt >= wait_limit) begin
                $display("[FATAL TIMEOUT] Access on line %0d (op=%0s, addr=0x%08h) did not complete within %0d cycles",
                         line_no, is_write ? "W" : "R", a, wait_limit);
                $fatal(1, "Access watchdog timeout");
            end

            cost    = cycle - start;
            was_hit = (hit_count != hits_before);

            n_access  = n_access + 1;
            total_cyc = total_cyc + cost;

            if (is_write) begin
                n_write = n_write + 1;
                wr_n = wr_n + 1; wr_cyc = wr_cyc + cost;
                ref_mem[a[13:2]] = d;
            end else begin
                n_read = n_read + 1;
                if (was_hit) begin rd_hit_n  = rd_hit_n + 1;  rd_hit_cyc  = rd_hit_cyc + cost;  end
                else         begin rd_miss_n = rd_miss_n + 1; rd_miss_cyc = rd_miss_cyc + cost; end
                if (cpu_rdata !== ref_mem[a[13:2]]) begin
                    n_err = n_err + 1;
                    if (n_err <= 10)
                        $display("  DATA ERROR [line %0d] addr=%08h  got=%08h  expected=%08h",
                                 line_no, a, cpu_rdata, ref_mem[a[13:2]]);
                end
            end
        end
    endtask

    // ---------------- trace reader ----------------
    reg [8*256-1:0] trace_name;
    reg [8*256-1:0] line;
    reg [7:0]       op;
    reg [31:0]      t_addr, t_data;
    integer fd, nf, k, line_count;

    real hit_rate, miss_rate, avg_cyc, hit_time, miss_time, miss_penalty, amat, no_cache;

    initial begin
        if (!$value$plusargs("TRACE=%s", trace_name)) begin
            $display("usage: vvp sim_trace +TRACE=traces/<file>.trace");
            $finish;
        end
        fd = $fopen(trace_name, "r");
        if (fd == 0) begin
            $display("cannot open %0s", trace_name);
            $fatal(1, "Cannot open trace file");
        end
        if ($test$plusargs("WAVES")) begin
            $dumpfile("trace.vcd");
            $dumpvars(0, tb_trace);
        end

        for (k = 0; k < MEM_WORDS; k = k + 1) ref_mem[k] = 32'hC0DE_0000 + k;

        repeat (3) @(negedge clk);
        rst_n = 1'b1;

        line_count = 0;
        while (!$feof(fd)) begin
            line = 0;
            op = 0; t_addr = 0; t_data = 0;
            nf = 0;
            if ($fgets(line, fd) != 0) begin
                line_count = line_count + 1;
                nf = $sscanf(line, "%c %h %h", op, t_addr, t_data);
                // nf < 2 means a blank line or a '#' comment: skip it
                if (nf >= 2 && (op == "R" || op == "r" || op == "W" || op == "w")) begin
                    // Strict alignment check: word addresses only
                    if (t_addr[1:0] !== 2'b00) begin
                        $display("[ALIGNMENT ERROR] Line %0d: Unaligned address 0x%08h (bits [1:0] != 00)",
                                 line_count, t_addr);
                        $fatal(1, "Unaligned trace address");
                    end
                    // Strict address range check
                    if ((t_addr >> 2) >= MEM_WORDS) begin
                        $display("[RANGE ERROR] Line %0d: Address 0x%08h exceeds memory window (%0d words)",
                                 line_count, t_addr, MEM_WORDS);
                        $fatal(1, "Trace address out of bounds");
                    end

                    if (op == "R" || op == "r")      do_access(0, t_addr, 0, line_count);
                    else if (op == "W" || op == "w") do_access(1, t_addr, t_data, line_count);
                end
            end
        end
        $fclose(fd);

        // ---------------- results ----------------
        // Explicit empty trace handling
        if (n_access == 0) begin
            $display("------------------------------------------------------------");
            $display("trace         : %0s", trace_name);
            $display("EMPTY TRACE   : No valid memory accesses processed from %0d lines", line_count);
            $display("DATA CHECK PASSED (0 accesses)");
            $display("------------------------------------------------------------");
            $finish;
        end

        hit_rate  = 100.0 * hit_count  / (hit_count + miss_count);
        miss_rate = 100.0 - hit_rate;
        avg_cyc   = 1.0 * total_cyc / n_access;

        // Hit time and miss penalty are measured from this run, not assumed
        hit_time     = (rd_hit_n  > 0) ? 1.0 * rd_hit_cyc  / rd_hit_n  : 3.0;
        miss_time    = (rd_miss_n > 0) ? 1.0 * rd_miss_cyc / rd_miss_n
                                       : hit_time + LATENCY * (BLOCK_SIZE / 4);
        miss_penalty = miss_time - hit_time;
        amat         = hit_time + (miss_rate / 100.0) * miss_penalty;
        // No-cache baseline: every access is one single-word memory access through
        // the same interface (request overhead + LATENCY wait + 1 ready cycle).
        // This equals the measured cost of a write-through write.
        no_cache     = hit_time + LATENCY + 1;

        $display("------------------------------------------------------------");
        $display("trace         : %0s", trace_name);
        $display("config        : %0d B cache, %0d B blocks, memory latency %0d, write allocate %0d",
                 CACHE_SIZE, BLOCK_SIZE, LATENCY, WRITE_ALLOCATE);
        $display("address fields: tag %0d | index %0d | offset %0d bits  (%0d lines)",
                 dut.TAG_W, dut.INDEX_W, dut.OFFSET_W, dut.NUM_LINES);
        $display("accesses      : %0d  (reads %0d, writes %0d)", n_access, n_read, n_write);
        $display("hits / misses : %0d / %0d", hit_count, miss_count);
        $display("hit rate      : %0.2f %%   miss rate: %0.2f %%", hit_rate, miss_rate);
        $display("hit time      : %0.2f cycles   read-miss time: %0.2f   miss penalty: %0.2f",
                 hit_time, miss_time, miss_penalty);
        if (wr_n > 0)
            $display("write time    : %0.2f cycles (write-through, measured)", 1.0 * wr_cyc / wr_n);
        $display("avg cycles    : %0.2f per access (measured)", avg_cyc);
        $display("AMAT          : %0.2f cycles (hit time + miss rate x miss penalty)", amat);
        $display("no-cache      : %0.2f cycles per access", no_cache);
        if (n_err == 0) begin
            $display("DATA CHECK PASSED");
        end else begin
            $display("DATA CHECK FAILED: %0d errors", n_err);
            $fatal(1, "Data verification failed");
        end
        $display("CSV,%0s,%0d,%0d,%0d,%0d,%0d,%0d,%0.2f,%0.2f,%0.2f,%0.2f",
                 trace_name, CACHE_SIZE, BLOCK_SIZE, LATENCY,
                 n_access, hit_count, miss_count, hit_rate, avg_cyc, amat, no_cache);
        $finish;
    end
endmodule
