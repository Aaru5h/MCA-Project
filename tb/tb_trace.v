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
    wire [31:0] mem_reads, mem_writes;
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
        .mem_reads(mem_reads), .mem_writes(mem_writes),
        .dbg_hit(dbg_hit), .dbg_tag(dbg_tag), .dbg_valid(dbg_valid));

    main_mem #(.LATENCY(LATENCY), .DEPTH_WORDS(MEM_WORDS)) memory (
        .clk(clk), .rst_n(rst_n),
        .req(mem_req), .we(mem_we), .addr(mem_addr), .wdata(mem_wdata),
        .rdata(mem_rdata), .ready(mem_ready));

    // ---------------- reference model + statistics ----------------
    reg [31:0] ref_mem [0:MEM_WORDS-1];

    integer n_access = 0, n_read = 0, n_write = 0, n_err = 0;
    longint unsigned total_cyc = 0;
    integer rd_hit_n = 0, rd_miss_n = 0, wr_n = 0;
    integer wr_hit_n = 0, wr_miss_n = 0;
    longint unsigned rd_hit_cyc = 0, rd_miss_cyc = 0, wr_cyc = 0;
    longint unsigned wr_hit_cyc = 0, wr_miss_cyc = 0;

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
                if (was_hit) begin wr_hit_n = wr_hit_n + 1; wr_hit_cyc = wr_hit_cyc + cost; end
                else         begin wr_miss_n = wr_miss_n + 1; wr_miss_cyc = wr_miss_cyc + cost; end
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

    real hit_rate, miss_rate, avg_cyc, amat, no_cache_estimate;

    // A class absent from this run has no measured average. Never substitute
    // a formula for a measurement; JSON null and human-readable N/A agree.
    task automatic write_average(input longint unsigned cycles, input integer count);
        if (count > 0) $write("%0.6f", 1.0 * cycles / count);
        else           $write("null");
    endtask

    task automatic show_class(input [8*16-1:0] label_text,
                              input integer count, input longint unsigned cycles);
        if (count > 0)
            $display("%0s: %0d accesses, %0d cycles, %0.2f cycles/access (measured)",
                     label_text, count, cycles, 1.0 * cycles / count);
        else
            $display("%0s: 0 accesses, 0 cycles, N/A (no observations)", label_text);
    endtask

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
        if (n_access != rd_hit_n + rd_miss_n + wr_hit_n + wr_miss_n ||
            hit_count != rd_hit_n + wr_hit_n || miss_count != rd_miss_n + wr_miss_n ||
            total_cyc != rd_hit_cyc + rd_miss_cyc + wr_hit_cyc + wr_miss_cyc)
            $fatal(1, "Performance accounting totals disagree");

        hit_rate = (n_access > 0) ? 100.0 * hit_count / n_access : 0.0;
        miss_rate = (n_access > 0) ? 100.0 * miss_count / n_access : 0.0;
        avg_cyc = (n_access > 0) ? 1.0 * total_cyc / n_access : 0.0;
        // Read AMAT is the measured mean of reads only, even if one read class
        // is absent. The all-access average above weights writes as well.
        amat = (n_read > 0) ? 1.0 * (rd_hit_cyc + rd_miss_cyc) / n_read : 0.0;
        no_cache_estimate = LATENCY + 4.0;

        $display("------------------------------------------------------------");
        $display("trace         : %0s", trace_name);
        $display("config        : %0d B cache, %0d B blocks, memory latency %0d, write allocate %0d",
                 CACHE_SIZE, BLOCK_SIZE, LATENCY, WRITE_ALLOCATE);
        $display("address fields: tag %0d | index %0d | offset %0d bits  (%0d lines)",
                 dut.TAG_W, dut.INDEX_W, dut.OFFSET_W, dut.NUM_LINES);
        $display("accesses      : %0d  (reads %0d, writes %0d)", n_access, n_read, n_write);
        $display("hits / misses : %0d / %0d", hit_count, miss_count);
        $display("memory words  : %0d reads, %0d writes (completed)", mem_reads, mem_writes);
        $display("hit rate      : %0.2f %%   miss rate: %0.2f %%", hit_rate, miss_rate);
        if (n_access == 0)
            $display("EMPTY TRACE   : No valid memory accesses processed from %0d lines", line_count);
        show_class("read hits       ", rd_hit_n, rd_hit_cyc);
        show_class("read misses     ", rd_miss_n, rd_miss_cyc);
        show_class("write hits      ", wr_hit_n, wr_hit_cyc);
        show_class("write misses    ", wr_miss_n, wr_miss_cyc);
        if (rd_hit_n > 0)
            $display("hit time      : %0.2f cycles (read hits, measured)", 1.0 * rd_hit_cyc / rd_hit_n);
        else $display("hit time      : N/A (no read hits)");
        if (rd_miss_n > 0)
            $display("read-miss time: %0.2f cycles (measured)", 1.0 * rd_miss_cyc / rd_miss_n);
        else $display("read-miss time: N/A (no read misses)");
        if (rd_hit_n > 0 && rd_miss_n > 0)
            $display("miss penalty  : %0.2f cycles (difference of measured read-class means)",
                     1.0 * rd_miss_cyc / rd_miss_n - 1.0 * rd_hit_cyc / rd_hit_n);
        else $display("miss penalty  : N/A (requires both read classes)");
        if (wr_n > 0)
            $display("write time    : %0.2f cycles (write-through, measured)", 1.0 * wr_cyc / wr_n);
        if (n_access > 0) $display("avg cycles    : %0.2f per access (measured, reads and writes)", avg_cyc);
        else             $display("avg cycles    : N/A (no accesses)");
        if (n_read > 0) begin
            $display("read miss rate: %0.2f %% (read misses / reads)", 100.0 * rd_miss_n / n_read);
            $display("AMAT          : %0.2f cycles (measured read cycles / reads)", amat);
        end else $display("AMAT          : N/A (no reads)");
        $display("no-cache      : %0.2f cycles per access (ESTIMATED: L + 4; use tb_no_cache for measurement)",
                 no_cache_estimate);
        if (n_err == 0) begin
            $display("DATA CHECK PASSED");
        end else begin
            $display("DATA CHECK FAILED: %0d errors", n_err);
            $fatal(1, "Data verification failed");
        end
        // Preserve the legacy CSV column order. Undefined averages use N/A;
        // the last column remains an estimate. METRICS is the versioned API.
        $write("CSV,%0s,%0d,%0d,%0d,%0d,%0d,%0d,%0.2f,",
                 trace_name, CACHE_SIZE, BLOCK_SIZE, LATENCY,
                 n_access, hit_count, miss_count, hit_rate);
        if (n_access > 0) $write("%0.2f,", avg_cyc); else $write("N/A,");
        if (n_read > 0) $write("%0.2f,", amat); else $write("N/A,");
        $display("%0.2f", no_cache_estimate);
        $write("METRICS,{\"schema_version\":1,\"engine\":\"cache\",\"cache_size\":%0d,\"block_size\":%0d,\"latency\":%0d,\"write_allocate\":%0d,",
               CACHE_SIZE, BLOCK_SIZE, LATENCY, WRITE_ALLOCATE);
        $write("\"accesses\":%0d,\"reads\":%0d,\"writes\":%0d,\"hits\":%0d,\"misses\":%0d,\"total_cycles\":%0d,",
               n_access, n_read, n_write, hit_count, miss_count, total_cyc);
        $write("\"rd_hits\":%0d,\"rd_misses\":%0d,\"wr_hits\":%0d,\"wr_misses\":%0d,",
               rd_hit_n, rd_miss_n, wr_hit_n, wr_miss_n);
        $write("\"rd_hit_cycles\":%0d,\"rd_miss_cycles\":%0d,\"wr_hit_cycles\":%0d,\"wr_miss_cycles\":%0d,",
               rd_hit_cyc, rd_miss_cyc, wr_hit_cyc, wr_miss_cyc);
        $write("\"avg_cycles\":"); write_average(total_cyc, n_access);
        $write(",\"read_amat\":"); write_average(rd_hit_cyc + rd_miss_cyc, n_read);
        $write(",\"read_hit_avg_cycles\":"); write_average(rd_hit_cyc, rd_hit_n);
        $write(",\"read_miss_avg_cycles\":"); write_average(rd_miss_cyc, rd_miss_n);
        $write(",\"write_avg_cycles\":"); write_average(wr_cyc, wr_n);
        $display(",\"no_cache_estimate_cycles\":%0.6f,\"mem_reads\":%0d,\"mem_writes\":%0d}",
                 no_cache_estimate, mem_reads, mem_writes);
        $finish;
    end
endmodule
