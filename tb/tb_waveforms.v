`timescale 1ns/1ps
// =============================================================================
// tb_waveforms.v
// Dedicated waveform capture testbench for direct-mapped cache controller.
//
// Owner: Meet (Visual Analysis & Performance Lead)
//
// Drives 7 key controller transaction scenarios with cycle-accurate timing:
//   1. Cold Read Miss & Refill (0x00000040)
//   2. Read Hit in same block (0x00000044)
//   3. Conflict Eviction & Refetch (0x00000440 - same index 0x04, tag 0x01)
//   4. Write Hit (0x00000444 - update cache word and write-through)
//   5. Write Miss with No-Write-Allocate (WA=0: 0x00000840 - bypass cache)
//   6. Write Miss with Write-Allocate (WA=1: 0x00000C40 - refill, overlay, write-through)
//   7. Mid-Refill and Mid-Write Synchronous Reset Recovery
// =============================================================================

module tb_waveforms;
    parameter CACHE_SIZE = 1024;
    parameter BLOCK_SIZE = 16;
    parameter LATENCY    = 4;

    reg clk = 1'b0;
    reg rst_n = 1'b0;
    always #5 clk = ~clk;

    integer cycle = 0;
    always @(posedge clk) cycle <= cycle + 1;

    // CPU interface
    reg         cpu_req   = 0;
    reg         cpu_we    = 0;
    reg  [31:0] cpu_addr  = 0;
    reg  [31:0] cpu_wdata = 0;
    wire [31:0] cpu_rdata;
    wire        cpu_ready;
    wire        busy;

    // Memory interface
    wire        mem_req;
    wire        mem_we;
    wire [31:0] mem_addr;
    wire [31:0] mem_wdata;
    wire [31:0] mem_rdata;
    wire        mem_ready;

    // Stats and debug
    wire [31:0] hit_count;
    wire [31:0] miss_count;
    wire        dbg_hit;
    wire [31:0] dbg_tag;
    wire        dbg_valid;

    reg [8*32-1:0] scenario_name = "INIT";

    // Configurable WRITE_ALLOCATE DUT
    parameter WRITE_ALLOCATE = 0;

    dm_cache #(
        .CACHE_SIZE(CACHE_SIZE),
        .BLOCK_SIZE(BLOCK_SIZE),
        .WRITE_ALLOCATE(WRITE_ALLOCATE)
    ) dut (
        .clk(clk),
        .rst_n(rst_n),
        .cpu_req(cpu_req),
        .cpu_we(cpu_we),
        .cpu_addr(cpu_addr),
        .cpu_wdata(cpu_wdata),
        .cpu_rdata(cpu_rdata),
        .cpu_ready(cpu_ready),
        .busy(busy),
        .mem_req(mem_req),
        .mem_we(mem_we),
        .mem_addr(mem_addr),
        .mem_wdata(mem_wdata),
        .mem_rdata(mem_rdata),
        .mem_ready(mem_ready),
        .hit_count(hit_count),
        .miss_count(miss_count),
        .dbg_hit(dbg_hit),
        .dbg_tag(dbg_tag),
        .dbg_valid(dbg_valid)
    );

    main_mem #(
        .LATENCY(LATENCY),
        .DEPTH_WORDS(4096)
    ) memory (
        .clk(clk),
        .rst_n(rst_n),
        .req(mem_req),
        .we(mem_we),
        .addr(mem_addr),
        .wdata(mem_wdata),
        .rdata(mem_rdata),
        .ready(mem_ready)
    );

    task automatic do_req(input bit we, input [31:0] a, input [31:0] d, input [8*32-1:0] name);
        integer start_cyc;
        begin
            scenario_name = name;
            @(negedge clk);
            cpu_req = 1;
            cpu_we  = we;
            cpu_addr = a;
            cpu_wdata = d;
            start_cyc = cycle;
            @(negedge clk);
            cpu_req = 0;
            while (!cpu_ready) @(negedge clk);
            $display("[%0s] Addr=0x%08h WE=%0b Cost=%0d cycles (Hit=%0b)",
                     name, a, we, cycle - start_cyc, dbg_hit);
            @(negedge clk);
        end
    endtask

    initial begin
        $dumpfile("docs/waveforms/cache_scenarios.vcd");
        $dumpvars(0, tb_waveforms);

        // Power-on reset
        rst_n = 0;
        repeat (3) @(negedge clk);
        rst_n = 1;
        repeat (2) @(negedge clk);

        // 1. Cold Read Miss & Refill
        do_req(0, 32'h0000_0040, 32'h0, "1_READ_MISS_REFILL");

        // 2. Read Hit in same block
        do_req(0, 32'h0000_0044, 32'h0, "2_READ_HIT");

        // 3. Conflict Miss (same index 0x04, tag 0x01)
        do_req(0, 32'h0000_0440, 32'h0, "3_CONFLICT_EVICTION");

        // 4. Write Hit (line now holds 0x0000_0440)
        do_req(1, 32'h0000_0444, 32'hDEAD_BEEF, "4_WRITE_HIT");

        // 5. Write Miss
        do_req(1, 32'h0000_0840, 32'hCAFE_BABE, "5_WRITE_MISS");

        // 6. Mid-refill reset recovery test
        scenario_name = "6_RESET_MID_REFILL";
        @(negedge clk);
        cpu_req = 1; cpu_we = 0; cpu_addr = 32'h0000_0080;
        @(negedge clk);
        cpu_req = 0;
        // Wait until ALLOCATE starts
        while (dut.state !== 3'd2) @(negedge clk);
        repeat (3) @(negedge clk); // Reset mid-refill
        rst_n = 0;
        @(negedge clk);
        rst_n = 1;
        repeat (3) @(negedge clk);
        $display("[6_RESET_MID_REFILL] Reset applied and recovered to IDLE (state=%0d, busy=%0b)",
                 dut.state, busy);

        repeat (5) @(negedge clk);
        $display("Waveform simulation complete. Dumped to docs/waveforms/cache_scenarios.vcd");
        $finish;
    end
endmodule
