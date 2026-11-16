`timescale 1ns/1ps
// Utkarsh: measured single-word baseline using the team's unchanged main_mem.
// Build: iverilog -g2012 -s tb_no_cache -o /tmp/no_cache.vvp rtl/main_mem.v tb/tb_no_cache.v
// Run:   vvp /tmp/no_cache.vvp +TRACE=traces/smoke.trace
module tb_no_cache;
    parameter LATENCY = 4;
    localparam MEM_WORDS = 4096;

    reg clk = 0, rst_n = 0;
    always #5 clk = ~clk;
    integer cycle = 0;
    always @(posedge clk) cycle <= cycle + 1;
    initial begin
        #50_000_000;
        $fatal(1, "No-cache simulation watchdog expired");
    end

    reg cpu_req = 0, cpu_we = 0;
    reg [31:0] cpu_addr = 0, cpu_wdata = 0;
    reg [31:0] cpu_rdata = 0;
    reg cpu_ready = 0;
    reg mem_req = 0, mem_we = 0;
    reg [31:0] mem_addr = 0, mem_wdata = 0;
    wire [31:0] mem_rdata;
    wire mem_ready;

    main_mem #(.LATENCY(LATENCY), .DEPTH_WORDS(MEM_WORDS)) memory (
        .clk(clk), .rst_n(rst_n), .req(mem_req), .we(mem_we),
        .addr(mem_addr), .wdata(mem_wdata), .rdata(mem_rdata), .ready(mem_ready)
    );

    // Keep the CPU acceptance, dispatch and registered response stages used by
    // dm_cache. Dispatch replaces COMPARE, but performs no tag lookup or refill.
    // Thus each access is one memory word with expected cost L + 4, measured
    // below rather than assigned from that formula. This is an interface-matched
    // baseline, not a claim about an ideal direct wire to memory.
    localparam IDLE = 0, DISPATCH = 1, WAIT_MEMORY = 2, RESPOND = 3;
    reg [1:0] state = IDLE;
    reg [31:0] req_addr, req_wdata;
    reg req_we;
    always @(posedge clk) begin
        if (!rst_n) begin
            state <= IDLE;
            cpu_ready <= 0;
            cpu_rdata <= 0;
            mem_req <= 0;
            mem_we <= 0;
            mem_addr <= 0;
            mem_wdata <= 0;
            req_addr <= 0;
            req_wdata <= 0;
            req_we <= 0;
        end else begin
            cpu_ready <= 0;
            case (state)
                IDLE: if (cpu_req) begin
                    req_addr <= cpu_addr;
                    req_wdata <= cpu_wdata;
                    req_we <= cpu_we;
                    state <= DISPATCH;
                end
                DISPATCH: begin
                    mem_req <= 1;
                    mem_we <= req_we;
                    mem_addr <= req_addr >> 2;
                    mem_wdata <= req_wdata;
                    state <= WAIT_MEMORY;
                end
                WAIT_MEMORY: if (mem_ready) begin
                    if (!req_we) cpu_rdata <= mem_rdata;
                    mem_req <= 0;
                    mem_we <= 0;
                    state <= RESPOND;
                end
                RESPOND: begin
                    cpu_ready <= 1;
                    state <= IDLE;
                end
                default: $fatal(1, "Illegal no-cache adapter state");
            endcase
        end
    end

    reg [31:0] ref_mem [0:MEM_WORDS-1];
    integer n_access = 0, n_read = 0, n_write = 0, n_err = 0;
    longint unsigned total_cyc = 0, read_cyc = 0, write_cyc = 0;
    integer memory_transactions = 0;
    always @(negedge clk)
        if (rst_n && mem_ready) memory_transactions = memory_transactions + 1;

    // Identical falling-edge drive/observe convention to tb_trace: the CPU
    // acceptance edge counts as cycle 1; inter-request idle time is excluded.
    task automatic do_access(input bit is_write, input [31:0] a, input [31:0] d,
                             input integer line_no);
        integer start, cost, waited;
        begin
            @(negedge clk);
            cpu_req = 1; cpu_we = is_write; cpu_addr = a; cpu_wdata = d;
            start = cycle;
            @(negedge clk);
            cpu_req = 0;
            waited = 0;
            while (!cpu_ready && waited < LATENCY + 100) begin
                @(negedge clk);
                waited = waited + 1;
            end
            if (!cpu_ready) $fatal(1, "No-cache access timeout on line %0d", line_no);
            cost = cycle - start;
            n_access = n_access + 1;
            total_cyc = total_cyc + cost;
            if (is_write) begin
                n_write = n_write + 1;
                write_cyc = write_cyc + cost;
                ref_mem[a >> 2] = d;
                if (memory.storage[a >> 2] !== d) begin
                    n_err = n_err + 1;
                    $display("DATA ERROR [line %0d] write did not reach memory", line_no);
                end
            end else begin
                n_read = n_read + 1;
                read_cyc = read_cyc + cost;
                if (cpu_rdata !== ref_mem[a >> 2]) begin
                    n_err = n_err + 1;
                    $display("DATA ERROR [line %0d] got=%08h expected=%08h",
                             line_no, cpu_rdata, ref_mem[a >> 2]);
                end
            end
        end
    endtask

    task automatic write_average(input longint unsigned cycles, input integer count);
        if (count > 0) $write("%0.6f", 1.0 * cycles / count);
        else           $write("null");
    endtask

    reg [8*256-1:0] trace_name, line;
    reg [7:0] op;
    reg [31:0] t_addr, t_data;
    integer fd, nf, k, line_count;
    initial begin
        if (!$value$plusargs("TRACE=%s", trace_name))
            $fatal(1, "usage: vvp no_cache.vvp +TRACE=traces/<file>.trace");
        fd = $fopen(trace_name, "r");
        if (fd == 0) $fatal(1, "Cannot open trace file %0s", trace_name);
        if ($test$plusargs("WAVES")) begin
            $dumpfile("no_cache.vcd");
            $dumpvars(0, tb_no_cache);
        end
        for (k = 0; k < MEM_WORDS; k = k + 1) ref_mem[k] = 32'hC0DE_0000 + k;
        repeat (3) @(negedge clk);
        rst_n = 1;

        // Match tb_trace's trace format, alignment and 16 KB bounds.
        line_count = 0;
        while (!$feof(fd)) begin
            line = 0; op = 0; t_addr = 0; t_data = 0;
            if ($fgets(line, fd) != 0) begin
                line_count = line_count + 1;
                nf = $sscanf(line, "%c %h %h", op, t_addr, t_data);
                if (nf >= 2 && (op == "R" || op == "r" || op == "W" || op == "w")) begin
                    if (t_addr[1:0] !== 2'b00)
                        $fatal(1, "Unaligned trace address on line %0d", line_count);
                    if ((t_addr >> 2) >= MEM_WORDS)
                        $fatal(1, "Trace address out of bounds on line %0d", line_count);
                    do_access(op == "W" || op == "w", t_addr, t_data, line_count);
                end
            end
        end
        $fclose(fd);
        if (n_access != n_read + n_write || total_cyc != read_cyc + write_cyc ||
            memory_transactions != n_access)
            $fatal(1, "No-cache accounting or memory transaction count disagrees");
        $display("------------------------------------------------------------");
        $display("trace         : %0s", trace_name);
        $display("no-cache      : interface-matched single-word memory, latency %0d", LATENCY);
        $display("accesses      : %0d (reads %0d, writes %0d)", n_access, n_read, n_write);
        $display("total cycles  : %0d (measured)", total_cyc);
        if (n_access > 0)
            $display("avg cycles    : %0.2f per access (measured)", 1.0 * total_cyc / n_access);
        else $display("EMPTY TRACE   : average cycles N/A (no accesses)");
        if (n_err != 0) $fatal(1, "DATA CHECK FAILED: %0d errors", n_err);
        $display("DATA CHECK PASSED");
        $write("METRICS,{\"schema_version\":1,\"engine\":\"no_cache\",\"latency\":%0d,", LATENCY);
        $write("\"accesses\":%0d,\"reads\":%0d,\"writes\":%0d,\"total_cycles\":%0d,",
               n_access, n_read, n_write, total_cyc);
        $write("\"read_cycles\":%0d,\"write_cycles\":%0d,\"memory_transactions\":%0d,",
               read_cyc, write_cyc, memory_transactions);
        $write("\"avg_cycles\":"); write_average(total_cyc, n_access);
        $write(",\"read_amat\":"); write_average(read_cyc, n_read);
        $write(",\"write_avg_cycles\":"); write_average(write_cyc, n_write);
        $display("}");
        $finish;
    end
endmodule
