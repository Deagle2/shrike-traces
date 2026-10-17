`timescale 1ns/1ps

// Small deterministic DUT used to prove the trace flow before attaching a
// larger design. It counts from 0x00 through 0x3f and then enters DONE.
module demo_dut(
  input  wire       clk,
  input  wire       rst_n,
  input  wire       start,
  output reg  [7:0] count,
  output reg  [1:0] state,
  output wire       running,
  output wire       done,
  output wire       terminal
);

  localparam [1:0] IDLE = 2'b00;
  localparam [1:0] RUN  = 2'b01;
  localparam [1:0] DONE = 2'b10;

  assign running  = (state == RUN);
  assign done     = (state == DONE);
  assign terminal = (state == RUN) && (count == 8'h3f);

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      count <= 8'h00;
      state <= IDLE;
    end else begin
      case (state)
        IDLE: begin
          count <= 8'h00;
          if (start)
            state <= RUN;
        end

        RUN: begin
          if (count == 8'h3f) begin
            state <= DONE;
          end else begin
            count <= count + 1'b1;
          end
        end

        default: begin
          count <= count;
          state <= DONE;
        end
      endcase
    end
  end

endmodule
