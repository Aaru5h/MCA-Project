`timescale 1ns/1ps
// =============================================================================
// main_mem.v
// Word-addressed main memory with a fixed access latency.
//
// While mem_req is high, the memory counts LATENCY cycles, performs the read
// or write, and pulses ready for one cycle. If req stays high after ready,
// the next access (next word of a refill) starts on the following cycle.
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
    localparam AW = $clog2(DEPTH_WORDS);

    reg [31:0] storage [0:DEPTH_WORDS-1];
    reg [15:0] wait_cnt;

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
        end else begin
            ready <= 1'b0;
            if (req && !ready) begin
                if (wait_cnt == LATENCY - 1) begin
                    wait_cnt <= 0;
                    ready    <= 1'b1;
                    if (we) storage[addr[AW-1:0]] <= wdata;
                    else    rdata <= storage[addr[AW-1:0]];
                end else begin
                    wait_cnt <= wait_cnt + 1;
                end
            end
        end
    end
endmodule
