`timescale 1ns/1ps
// =============================================================================
// dm_cache.v
// Direct-mapped cache controller (write-through, no-write-allocate)
//
// Default configuration: 1 KB cache, 16-byte blocks, 32-bit byte addresses
//   lines        = CACHE_SIZE / BLOCK_SIZE      = 64
//   offset bits  = log2(BLOCK_SIZE)             = 4  (2 word-select + 2 byte)
//   index bits   = log2(lines)                  = 6
//   tag bits     = 32 - index - offset          = 22
//
// Address layout (default):  [31:10] tag | [9:4] index | [3:2] word | [1:0] byte
//
// Only CACHE_SIZE and BLOCK_SIZE need to change for a new configuration;
// every field width below is derived from them.
// =============================================================================
module dm_cache #(
    parameter CACHE_SIZE = 1024,   // bytes, power of two
    parameter BLOCK_SIZE = 16      // bytes, power of two, >= 4
) (
    input  wire        clk,
    input  wire        rst_n,          // active-low synchronous reset

    // ---------------- processor side ----------------
    input  wire        cpu_req,        // start a request (sampled when idle)
    input  wire        cpu_we,         // 1 = write, 0 = read
    input  wire [31:0] cpu_addr,       // byte address (word aligned)
    input  wire [31:0] cpu_wdata,
    output reg  [31:0] cpu_rdata,
    output reg         cpu_ready,      // one-cycle pulse: request finished
    output wire        busy,           // high while a request is in flight

    // ---------------- memory side -------------------
    output reg         mem_req,
    output reg         mem_we,
    output reg  [31:0] mem_addr,       // word address (byte address >> 2)
    output reg  [31:0] mem_wdata,
    input  wire [31:0] mem_rdata,
    input  wire        mem_ready,      // one-cycle pulse per completed word

    // ---------------- statistics / debug ------------
    output reg  [31:0] hit_count,
    output reg  [31:0] miss_count,
    output wire        dbg_hit,        // live hit signal for waveforms
    output wire [31:0] dbg_tag,        // stored tag of the selected line
    output wire        dbg_valid       // valid bit of the selected line
);

    // ------------------------------------------------------------------
    // Derived geometry
    // ------------------------------------------------------------------
    // Safe intermediate values let invalid parameters reach the diagnostic.
    localparam NUM_LINES   = (BLOCK_SIZE >= 4 && CACHE_SIZE >= BLOCK_SIZE)
                             ? CACHE_SIZE / BLOCK_SIZE : 1;
    localparam WORDS_PER_B = (BLOCK_SIZE >= 4) ? BLOCK_SIZE / 4 : 1;
    localparam OFFSET_W    = (BLOCK_SIZE >= 4) ? $clog2(BLOCK_SIZE) : 2;
    localparam WSEL_W      = $clog2(WORDS_PER_B);   // word-select bits
    localparam INDEX_W     = $clog2(NUM_LINES);
    localparam TAG_W       = 32 - INDEX_W - OFFSET_W;
    // Logical field widths may be zero; Verilog storage widths must not be.
    localparam INDEX_BITS  = (INDEX_W > 0) ? INDEX_W : 1;
    localparam WSEL_BITS   = (WSEL_W > 0) ? WSEL_W : 1;

    generate
        if (CACHE_SIZE < 4 || BLOCK_SIZE < 4 || CACHE_SIZE < BLOCK_SIZE ||
            (CACHE_SIZE & (CACHE_SIZE - 1)) != 0 ||
            (BLOCK_SIZE & (BLOCK_SIZE - 1)) != 0 || TAG_W < 1) begin : bad_geometry
            initial $fatal(1, "Cache sizes must be powers of two: CACHE_SIZE >= BLOCK_SIZE >= 4, with a positive tag width");
        end
    endgenerate

    // ------------------------------------------------------------------
    // Storage: data array, tag array, valid bits
    // ------------------------------------------------------------------
    reg [31:0]      data_arr [0:NUM_LINES*WORDS_PER_B-1];
    reg [TAG_W-1:0] tag_arr  [0:NUM_LINES-1];
    reg             valid_arr[0:NUM_LINES-1];

    // ------------------------------------------------------------------
    // Latched request
    // ------------------------------------------------------------------
    reg [31:0] req_addr;
    reg [31:0] req_wdata;
    reg        req_we;

    wire [TAG_W-1:0]   a_tag   = req_addr[31 -: TAG_W];
    wire [INDEX_BITS-1:0] a_index = (req_addr >> OFFSET_W) & (NUM_LINES - 1);
    wire [WSEL_BITS-1:0]  a_word  = (req_addr >> 2) & (WORDS_PER_B - 1);

    // Hit = the line is valid AND its stored tag equals the address tag
    wire line_valid = valid_arr[a_index];
    wire tag_match  = (tag_arr[a_index] == a_tag);
    wire is_hit     = line_valid & tag_match;

    assign dbg_hit   = is_hit;
    assign dbg_valid = line_valid;
    assign dbg_tag   = {{(32-TAG_W){1'b0}}, tag_arr[a_index]};

    // ------------------------------------------------------------------
    // Controller FSM
    // ------------------------------------------------------------------
    localparam [2:0] S_IDLE     = 3'd0,
                     S_COMPARE  = 3'd1,
                     S_ALLOCATE = 3'd2,   // read miss: fetch the block
                     S_WRITE    = 3'd3,   // write-through to memory
                     S_RESPOND  = 3'd4;

    reg [2:0]        state;
    reg [WSEL_BITS-1:0] beat;                // which word of the block is arriving

    assign busy = (state != S_IDLE);

    integer i;

    always @(posedge clk) begin
        if (!rst_n) begin
            state      <= S_IDLE;
            cpu_ready  <= 1'b0;
            mem_req    <= 1'b0;
            mem_we     <= 1'b0;
            hit_count  <= 0;
            miss_count <= 0;
            beat       <= 0;
            for (i = 0; i < NUM_LINES; i = i + 1)
                valid_arr[i] <= 1'b0;     // no false hits after reset
        end else begin
            cpu_ready <= 1'b0;

            case (state)
            // ----------------------------------------------------------
            S_IDLE: begin
                if (cpu_req) begin
                    req_addr  <= cpu_addr;
                    req_wdata <= cpu_wdata;
                    req_we    <= cpu_we;
                    state     <= S_COMPARE;
                end
            end
            // ----------------------------------------------------------
            S_COMPARE: begin
                if (is_hit) hit_count  <= hit_count + 1;
                else        miss_count <= miss_count + 1;

                if (req_we) begin
                    // write-through: memory is always updated;
                    // the cache copy is updated only on a hit (no allocate)
                    if (is_hit)
                        data_arr[a_index * WORDS_PER_B + a_word] <= req_wdata;
                    mem_req   <= 1'b1;
                    mem_we    <= 1'b1;
                    mem_addr  <= req_addr >> 2;
                    mem_wdata <= req_wdata;
                    state     <= S_WRITE;
                end else if (is_hit) begin
                    cpu_rdata <= data_arr[a_index * WORDS_PER_B + a_word];
                    state     <= S_RESPOND;
                end else begin
                    // read miss: request the whole block, starting at word 0
                    beat     <= 0;
                    mem_req  <= 1'b1;
                    mem_we   <= 1'b0;
                    mem_addr <= ((req_addr >> OFFSET_W) << (OFFSET_W - 2));
                    state    <= S_ALLOCATE;
                end
            end
            // ----------------------------------------------------------
            S_ALLOCATE: begin
                if (mem_ready) begin
                    data_arr[a_index * WORDS_PER_B + beat] <= mem_rdata;
                    if (beat == a_word)
                        cpu_rdata <= mem_rdata;          // forward requested word
                    if (beat == WORDS_PER_B - 1) begin
                        mem_req            <= 1'b0;
                        tag_arr[a_index]   <= a_tag;
                        valid_arr[a_index] <= 1'b1;
                        state              <= S_RESPOND;
                    end else begin
                        beat     <= beat + 1'b1;
                        mem_addr <= mem_addr + 1;
                    end
                end
            end
            // ----------------------------------------------------------
            S_WRITE: begin
                if (mem_ready) begin
                    mem_req <= 1'b0;
                    mem_we  <= 1'b0;
                    state   <= S_RESPOND;
                end
            end
            // ----------------------------------------------------------
            S_RESPOND: begin
                cpu_ready <= 1'b1;
                state     <= S_IDLE;
            end
            default: state <= S_IDLE;
            endcase
        end
    end

endmodule
