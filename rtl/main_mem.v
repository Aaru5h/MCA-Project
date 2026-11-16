`timescale 1ns/1ps
// =============================================================================
// main_mem.v
// Word-addressed main memory with a fixed access latency.
//
// While mem_req is high, the memory counts LATENCY cycles, performs the read
// or write, and pulses ready for one cycle. If req stays high after ready,
// the next access (next word of a refill) starts on the following cycle.
// Address, direction and data are latched when a word starts. Deasserting req
// cancels an unfinished word. Reset cancels requests but preserves storage.
// Initial contents follow a known pattern so testbenches can check reads.
// =============================================================================
module main_mem #(
    parameter LATENCY     = 4,      // cycles per word access
    parameter DEPTH_WORDS = 4096    // 16 KB
) (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        req,
    input  wire        we,
    input  wire [31:0] addr,        // word address
    input  wire [31:0] wdata,
    output reg  [31:0] rdata,
    output reg         ready
);
    localparam AW = (DEPTH_WORDS > 1) ? $clog2(DEPTH_WORDS) : 1;
    localparam COUNT_W = (LATENCY > 1) ? $clog2(LATENCY) : 1;

    generate
        if (LATENCY < 1 || DEPTH_WORDS < 1) begin : bad_parameters
            initial $fatal(1, "LATENCY and DEPTH_WORDS must be positive");
        end
    endgenerate

    reg [31:0] storage [0:DEPTH_WORDS-1];
    reg [COUNT_W-1:0] wait_cnt;
    reg [31:0] pending_addr, pending_wdata;
    reg pending_we;

    // The finite memory window does not wrap. Diagnose illegal requests in
    // simulation; the controller's integration must supply in-range addresses.
    // synthesis translate_off
    always @(posedge clk)
        if (rst_n && req && !ready && wait_cnt == 0 && addr >= DEPTH_WORDS)
            $fatal(1, "Memory word address %h exceeds DEPTH_WORDS=%0d", addr, DEPTH_WORDS);
    // synthesis translate_on

    // Known pattern: word i holds 0xC0DE0000 + i
    integer k;
    initial begin
        for (k = 0; k < DEPTH_WORDS; k = k + 1)
            storage[k] = 32'hC0DE_0000 + k;
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            wait_cnt <= 0;
            ready    <= 1'b0;
            rdata    <= 0;
            pending_addr  <= 0;
            pending_wdata <= 0;
            pending_we    <= 0;
        end else begin
            ready <= 1'b0;
            if (!req) begin
                // Withdrawal cancels an unfinished word, not a completed write.
                wait_cnt <= 0;
            end else if (!ready) begin
                if (wait_cnt == 0) begin
                    pending_addr  <= addr;
                    pending_wdata <= wdata;
                    pending_we    <= we;
                end
                if (wait_cnt == LATENCY - 1) begin
                    wait_cnt <= 0;
                    ready    <= 1'b1;
                    // A one-cycle access completes on its sampling edge.
                    if (LATENCY == 1) begin
                        if (we) storage[addr[AW-1:0]] <= wdata;
                        else    rdata <= storage[addr[AW-1:0]];
                    end else begin
                        if (pending_we)
                            storage[pending_addr[AW-1:0]] <= pending_wdata;
                        else
                            rdata <= storage[pending_addr[AW-1:0]];
                    end
                end else begin
                    wait_cnt <= wait_cnt + 1;
                end
            end
        end
    end
endmodule
