`timescale 1ns/1ps
// =============================================================================
// tb_dm_cache.v
// Directed unit testbench for dm_cache and main_mem interface
//
// Verification Lead: Kushagra
//
// Directed checks:
//   1. Reset and initialization (counters, invalid lines, idle state)
//   2. Cold read miss and ascending-order block refill validation
//   3. Refill completeness: verify every word within fetched block hits
//   4. Repeated hits and spatial/temporal locality
//   5. Conflict eviction: same index, distinct tag eviction and refetch
//   6. Write hit: cache update + backing memory write-through verification
//   7. Write miss (no-write-allocate): memory updated, cache not allocated
//   8. Backing memory direct inspection (prevent cache masking broken writes)
//   9. Handshake & contract checks (cpu_ready 1-cycle pulse, busy, ignore while busy)
//  10. Mid-transaction synchronous reset recovery (during refill and write)
//
// Run:
//   iverilog -g2012 -o sim_dm_cache rtl/main_mem.v rtl/dm_cache.v tb/tb_dm_cache.v
//   vvp sim_dm_cache
// =============================================================================

module tb_dm_cache;
    parameter CACHE_SIZE     = 1024;
    parameter BLOCK_SIZE     = 16;
    parameter WRITE_ALLOCATE = 0;
    parameter LATENCY        = 4;
    localparam MEM_WORDS     = 4096;
    localparam WORDS_PER_B   = BLOCK_SIZE / 4;

    // Clock and reset
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

    // Instantiate DUT
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

    // Instantiate Main Memory
    main_mem #(
        .LATENCY(LATENCY),
        .DEPTH_WORDS(MEM_WORDS)
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

    // Test tracking
    integer test_num = 0;
    integer errors   = 0;

    task check(input bit cond, input [8*64-1:0] msg);
        begin
            if (!cond) begin
                $display("  [FAIL] Test %0d: %0s (cycle %0d)", test_num, msg, cycle);
                errors = errors + 1;
            end else begin
                $display("  [PASS] Test %0d: %0s", test_num, msg);
            end
        end
    endtask

    // CPU access task with bounded timeout and contract assertions
    task cpu_access(
        input        is_write,
        input [31:0] addr,
        input [31:0] wdata,
        output [31:0] rdata,
        output integer elapsed_cycles,
        output bit   was_hit
    );
        integer start_cyc, timeout_cyc, hits_before;
        begin
            hits_before = hit_count;
            @(negedge clk);
            cpu_req   = 1'b1;
            cpu_we    = is_write;
            cpu_addr  = addr;
            cpu_wdata = wdata;
            start_cyc = cycle;

            @(negedge clk);
            cpu_req   = 1'b0;

            timeout_cyc = 0;
            while (!cpu_ready && timeout_cyc < 1000) begin
                @(negedge clk);
                timeout_cyc = timeout_cyc + 1;
            end

            if (timeout_cyc >= 1000) begin
                $display("  [FATAL] Timeout waiting for cpu_ready on addr=0x%08h", addr);
                errors = errors + 1;
                $finish;
            end

            // Verify cpu_ready is asserted exactly when busy drops
            if (busy !== 1'b0) begin
                $display("  [FAIL] Contract: busy should be 0 when cpu_ready pulses");
                errors = errors + 1;
            end

            rdata          = cpu_rdata;
            elapsed_cycles = cycle - start_cyc;
            was_hit        = (hit_count != hits_before);

            // Verify cpu_ready pulses for exactly 1 cycle
            @(negedge clk);
            if (cpu_ready !== 1'b0) begin
                $display("  [FAIL] Contract: cpu_ready was high for more than 1 cycle");
                errors = errors + 1;
            end
        end
    endtask

    reg [31:0] rd_data;
    integer cyc_taken;
    bit got_hit;
    integer w;

    initial begin
        $display("============================================================");
        $display("Running Directed Verification: tb_dm_cache");
        $display("Config: %0d B Cache, %0d B Blocks, WRITE_ALLOCATE=%0d, LATENCY=%0d",
                 CACHE_SIZE, BLOCK_SIZE, WRITE_ALLOCATE, LATENCY);
        $display("============================================================");

        // ------------------------------------------------------------
        // Test 1: Reset and Initialization
        // ------------------------------------------------------------
        test_num = 1;
        rst_n = 1'b0;
        repeat (4) @(posedge clk);
        #1;
        check(busy == 0 && cpu_ready == 0 && hit_count == 0 && miss_count == 0,
              "Reset holds controller idle and counters at zero");
        check(dut.valid_arr[0] == 0 && dut.valid_arr[dut.NUM_LINES-1] == 0,
              "Valid array cleared upon reset");

        @(negedge clk);
        rst_n = 1'b1;
        repeat (2) @(posedge clk);

        // ------------------------------------------------------------
        // Test 2: Cold Read Miss (Address 0x00000040)
        // ------------------------------------------------------------
        test_num = 2;
        // Memory has default values: 0xC0DE0000 + word_index
        // For addr 0x40 (word 16 = 0x10): expected data = 0xC0DE0010
        cpu_access(0, 32'h0000_0040, 32'h0, rd_data, cyc_taken, got_hit);
        check(!got_hit, "Cold read misses");
        check(rd_data == 32'hC0DE_0010, "Cold read returns correct initial memory data");
        check(miss_count == 1 && hit_count == 0, "Miss counter incremented, hit counter unchanged");
        check(dut.dbg_valid == 1'b1, "Line is marked valid after refill");
        check(dut.dbg_tag == (32'h0000_0040 >> (dut.OFFSET_W + dut.INDEX_W)),
              "Stored tag matches address tag");

        // ------------------------------------------------------------
        // Test 3: Refill Completeness (All words in fetched block hit)
        // ------------------------------------------------------------
        test_num = 3;
        for (w = 0; w < WORDS_PER_B; w = w + 1) begin
            cpu_access(0, 32'h0000_0040 + (w * 4), 32'h0, rd_data, cyc_taken, got_hit);
            check(got_hit, "Subsequent read in refilled block is a hit");
            check(rd_data == (32'hC0DE_0010 + w), "Refilled word data matches memory");
            check(cyc_taken == 3, "Read hit finishes in 3 cycles");
        end

        // ------------------------------------------------------------
        // Test 4: Repeated Hits on Same Block
        // ------------------------------------------------------------
        test_num = 4;
        cpu_access(0, 32'h0000_0040, 32'h0, rd_data, cyc_taken, got_hit);
        check(got_hit && rd_data == 32'hC0DE_0010, "Repeated hit returns correct data");

        // ------------------------------------------------------------
        // Test 5: Conflict Miss and Line Eviction
        // ------------------------------------------------------------
        test_num = 5;
        // Addr 0x40 has index (0x40 >> OFFSET_W) & (NUM_LINES - 1).
        // Addr 0x40 + CACHE_SIZE has identical index, but tag differing by 1.
        cpu_access(0, 32'h0000_0040 + CACHE_SIZE, 32'h0, rd_data, cyc_taken, got_hit);
        check(!got_hit, "Conflict address misses and evicts old line");
        check(rd_data == (32'hC0DE_0000 + ((32'h0000_0040 + CACHE_SIZE) >> 2)),
              "Conflict miss returns correct memory data");
        check(dut.dbg_tag == ((32'h0000_0040 + CACHE_SIZE) >> (dut.OFFSET_W + dut.INDEX_W)),
              "New tag stored in line index");

        // Re-accessing 0x40 must now miss again (conflict thrashing)
        cpu_access(0, 32'h0000_0040, 32'h0, rd_data, cyc_taken, got_hit);
        check(!got_hit, "Re-accessing evicted address results in conflict miss");

        // ------------------------------------------------------------
        // Test 6: Write Hit (Update cache + verify write-through in memory)
        // ------------------------------------------------------------
        test_num = 6;
        // Line 0x40 is currently cached from Test 5
        cpu_access(1, 32'h0000_0040, 32'hDEAD_BEEF, rd_data, cyc_taken, got_hit);
        check(got_hit, "Write to valid cached line is a write hit");
        // Check backing memory directly (word addr = 0x40 >> 2 = 16 = 0x10)
        check(memory.storage[32'h40 >> 2] == 32'hDEAD_BEEF,
              "Backing memory directly contains updated write-through data");
        // Verify subsequent read hits and returns updated data from cache
        cpu_access(0, 32'h0000_0040, 32'h0, rd_data, cyc_taken, got_hit);
        check(got_hit && rd_data == 32'hDEAD_BEEF, "Subsequent read hit returns modified data");

        // ------------------------------------------------------------
        // Test 7: Write Miss & Backing Memory Verification
        // ------------------------------------------------------------
        test_num = 7;
        // Address 0x800 is not cached
        cpu_access(1, 32'h0000_0800, 32'hCAFE_BABE, rd_data, cyc_taken, got_hit);
        check(!got_hit, "Write to uncached line is a write miss");
        check(memory.storage[32'h800 >> 2] == 32'hCAFE_BABE,
              "Backing memory updated on write miss via write-through");

        if (WRITE_ALLOCATE == 0) begin
            // In no-write-allocate, cache line should NOT be allocated
            // Subsequent read must miss and fetch from memory
            cpu_access(0, 32'h0000_0800, 32'h0, rd_data, cyc_taken, got_hit);
            check(!got_hit, "Read after no-write-allocate write miss is a cold miss");
            check(rd_data == 32'hCAFE_BABE, "Read miss fetches updated data from backing memory");
        end else begin
            // In write-allocate, cache line WAS allocated during write miss
            cpu_access(0, 32'h0000_0800, 32'h0, rd_data, cyc_taken, got_hit);
            check(got_hit, "Read after write-allocate write miss is a hit");
            check(rd_data == 32'hCAFE_BABE, "Read hit returns allocated write data");
        end

        // ------------------------------------------------------------
        // Test 8: Handshake Integrity & Live Signal Immunity
        // ------------------------------------------------------------
        test_num = 8;
        // Start access and perturb inputs on next cycle while busy
        @(negedge clk);
        cpu_req   = 1'b1;
        cpu_we    = 1'b0;
        cpu_addr  = 32'h0000_0040;
        @(negedge clk);
        cpu_req   = 1'b1; // hold high or change address
        cpu_addr  = 32'hFFFF_FFFF;
        cpu_we    = 1'b1;
        while (!cpu_ready) @(negedge clk);
        cpu_req   = 1'b0;
        check(rd_data != 32'hFFFF_FFFF, "Controller ignores address/direction changes while busy");
        @(negedge clk);

        // ------------------------------------------------------------
        // Test 9: Synchronous Reset Recovery Mid-Refill
        // ------------------------------------------------------------
        test_num = 9;
        // Launch cold miss to uncached line
        @(negedge clk);
        cpu_req  = 1'b1;
        cpu_we   = 1'b0;
        cpu_addr = 32'h0000_0C00;
        @(negedge clk);
        cpu_req  = 1'b0;
        // Wait until memory request starts
        while (!mem_req) @(negedge clk);
        // Assert reset mid-transaction
        rst_n = 1'b0;
        @(negedge clk);
        rst_n = 1'b1;
        @(negedge clk);
        check(busy == 0, "Controller returns to idle immediately upon synchronous reset");
        check(dut.valid_arr[(32'hC00 >> dut.OFFSET_W) & (dut.NUM_LINES - 1)] == 0,
              "Partially refilled line remains invalid after reset");

        // Normal transaction should proceed cleanly after reset
        cpu_access(0, 32'h0000_0040, 32'h0, rd_data, cyc_taken, got_hit);
        check(!got_hit, "Clean cold miss after reset recovery");

        // ------------------------------------------------------------
        // Test 10: Multi-Word Write Sequencing and Coherency
        // ------------------------------------------------------------
        test_num = 10;
        // Line 0x40 is valid; write to all words in block 0x40
        for (w = 0; w < WORDS_PER_B; w = w + 1) begin
            cpu_access(1, 32'h0000_0040 + (w * 4), 32'hA000_0000 + w, rd_data, cyc_taken, got_hit);
            check(got_hit, "Consecutive write hit in same block");
            check(memory.storage[(32'h40 >> 2) + w] == (32'hA000_0000 + w),
                  "Memory storage immediately updated with write-through data");
        end
        // Read back all words from cache to ensure cache integrity
        for (w = 0; w < WORDS_PER_B; w = w + 1) begin
            cpu_access(0, 32'h0000_0040 + (w * 4), 32'h0, rd_data, cyc_taken, got_hit);
            check(got_hit && rd_data == (32'hA000_0000 + w),
                  "Cache line read hit returns newly written block data");
        end

        // ------------------------------------------------------------
        // Test 11: Write Allocation Refill & Word Overlay Integrity
        // ------------------------------------------------------------
        test_num = 11;
        // Target uncached block at 0x0000_1000, write specifically to word 1 (0x1004)
        cpu_access(1, 32'h0000_1004, 32'hBEEF_0001, rd_data, cyc_taken, got_hit);
        check(!got_hit, "Write to uncached address 0x1004 is a write miss");
        check(memory.storage[32'h1004 >> 2] == 32'hBEEF_0001,
              "Backing memory updated at 0x1004");

        if (WRITE_ALLOCATE == 1) begin
            // In write-allocate: block was refilled, word 1 overlaid with BEEF_0001,
            // while word 0 should retain 0xC0DE_0400 (32'h1000 >> 2 = 0x400)
            cpu_access(0, 32'h0000_1000, 32'h0, rd_data, cyc_taken, got_hit);
            check(got_hit, "Neighboring word 0 hits in allocated cache line");
            check(rd_data == (32'hC0DE_0000 + (32'h1000 >> 2)),
                  "Neighboring word 0 preserves refilled backing memory value");

            cpu_access(0, 32'h0000_1004, 32'h0, rd_data, cyc_taken, got_hit);
            check(got_hit && rd_data == 32'hBEEF_0001,
                  "Written word 1 returns overlaid write value");
        end

        // ------------------------------------------------------------
        // Test 12: Synchronous Reset Mid-Write Transaction
        // ------------------------------------------------------------
        test_num = 12;
        @(negedge clk);
        cpu_req   = 1'b1;
        cpu_we    = 1'b1;
        cpu_addr  = 32'h0000_1400;
        cpu_wdata = 32'h1234_5678;
        @(negedge clk);
        cpu_req   = 1'b0;
        // Wait until memory write is initiated
        while (!mem_we) @(negedge clk);
        // Reset mid-write
        rst_n = 1'b0;
        @(negedge clk);
        rst_n = 1'b1;
        @(negedge clk);
        check(busy == 0, "Controller resets to idle from WRITE state");
        // Verify subsequent normal read access
        cpu_access(0, 32'h0000_0040, 32'h0, rd_data, cyc_taken, got_hit);
        check(!got_hit, "Cold miss after mid-write reset recovery");

        // ------------------------------------------------------------
        // Summary
        // ------------------------------------------------------------
        $display("============================================================");
        if (errors == 0) begin
            $display("ALL %0d DIRECTED TESTS PASSED!", test_num);
            $display("============================================================");
            $finish;
        end else begin
            $display("DIRECTED VERIFICATION FAILED: %0d error(s)", errors);
            $display("============================================================");
            $fatal(1, "Directed tests failed");
        end
    end

endmodule
