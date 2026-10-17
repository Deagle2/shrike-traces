`timescale 1ns/1ps

// Circular-buffer capture controller.
// After DONE, logical sample PRE_SAMPLES is the trigger sample.
module scope_controller #(
  parameter integer TRACE_DEPTH = 16,
  parameter integer ADDR_WIDTH  = 4,
  parameter integer PRE_SAMPLES = 8
)(
  input  wire                  clk,
  input  wire                  rst_n,
  input  wire                  arm,
  input  wire                  clear,
  input  wire                  trigger_match,
  output wire                  mem_we,
  output wire [ADDR_WIDTH-1:0] mem_wr_addr,
  output wire                  capturing,
  output wire                  primed,
  output reg                   triggered,
  output reg                   done,
  output reg  [ADDR_WIDTH-1:0] trigger_ptr
);

  localparam [2:0] ST_IDLE    = 3'd0;
  localparam [2:0] ST_PREFILL = 3'd1;
  localparam [2:0] ST_ARMED   = 3'd2;
  localparam [2:0] ST_POST    = 3'd3;
  localparam [2:0] ST_DONE    = 3'd4;
  localparam integer POST_SAMPLES = TRACE_DEPTH - PRE_SAMPLES - 1;

  reg [2:0] state;
  reg [ADDR_WIDTH-1:0] wr_ptr;
  reg [ADDR_WIDTH:0] pre_count;
  reg [ADDR_WIDTH:0] post_count;

  assign capturing   = (state == ST_PREFILL) ||
                       (state == ST_ARMED)   ||
                       (state == ST_POST);
  assign primed      = (state == ST_ARMED) ||
                       (state == ST_POST)  ||
                       (state == ST_DONE);
  assign mem_we      = capturing && rst_n && !clear;
  assign mem_wr_addr = wr_ptr;

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      state       <= ST_IDLE;
      wr_ptr      <= {ADDR_WIDTH{1'b0}};
      pre_count   <= {(ADDR_WIDTH+1){1'b0}};
      post_count  <= {(ADDR_WIDTH+1){1'b0}};
      trigger_ptr <= {ADDR_WIDTH{1'b0}};
      triggered   <= 1'b0;
      done        <= 1'b0;
    end else if (clear) begin
      state       <= ST_IDLE;
      wr_ptr      <= {ADDR_WIDTH{1'b0}};
      pre_count   <= {(ADDR_WIDTH+1){1'b0}};
      post_count  <= {(ADDR_WIDTH+1){1'b0}};
      trigger_ptr <= {ADDR_WIDTH{1'b0}};
      triggered   <= 1'b0;
      done        <= 1'b0;
    end else begin
      case (state)
        ST_IDLE: begin
          if (arm) begin
            state      <= ST_PREFILL;
            wr_ptr     <= {ADDR_WIDTH{1'b0}};
            pre_count  <= {(ADDR_WIDTH+1){1'b0}};
            post_count <= {(ADDR_WIDTH+1){1'b0}};
            triggered  <= 1'b0;
            done       <= 1'b0;
          end
        end

        ST_PREFILL: begin
          wr_ptr <= wr_ptr + 1'b1;
          if (pre_count == PRE_SAMPLES-1)
            state <= ST_ARMED;
          else
            pre_count <= pre_count + 1'b1;
        end

        ST_ARMED: begin
          wr_ptr <= wr_ptr + 1'b1;
          if (trigger_match) begin
            trigger_ptr <= wr_ptr;
            triggered   <= 1'b1;
            post_count  <= {(ADDR_WIDTH+1){1'b0}};
            if (POST_SAMPLES == 0) begin
              state <= ST_DONE;
              done  <= 1'b1;
            end else begin
              state <= ST_POST;
            end
          end
        end

        ST_POST: begin
          wr_ptr <= wr_ptr + 1'b1;
          if (post_count == POST_SAMPLES-1) begin
            state <= ST_DONE;
            done  <= 1'b1;
          end else begin
            post_count <= post_count + 1'b1;
          end
        end

        ST_DONE: begin
          if (arm) begin
            state      <= ST_PREFILL;
            wr_ptr     <= {ADDR_WIDTH{1'b0}};
            pre_count  <= {(ADDR_WIDTH+1){1'b0}};
            post_count <= {(ADDR_WIDTH+1){1'b0}};
            triggered  <= 1'b0;
            done       <= 1'b0;
          end
        end

        default: begin
          state <= ST_IDLE;
          done  <= 1'b0;
        end
      endcase
    end
  end

endmodule
