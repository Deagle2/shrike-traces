`timescale 1ns/1ps

// Byte-oriented register protocol. A command updates tx_data; that response is
// shifted out during the next SPI transaction.
module scope_spi_regs(
  input  wire       clk,
  input  wire       rst_n,
  input  wire [7:0] rx_data,
  input  wire       rx_valid,
  output reg  [7:0] tx_data,

  output reg        arm_pulse,
  output reg        clear_pulse,
  input  wire       capturing,
  input  wire       primed,
  input  wire       triggered,
  input  wire       done,
  input  wire [3:0] trigger_ptr,

  output reg  [3:0] rd_index,
  input  wire [15:0] rd_data
);

  reg pending_read;
  reg pending_high;
  reg rx_valid_d;

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      tx_data      <= 8'h00;
      arm_pulse    <= 1'b0;
      clear_pulse  <= 1'b0;
      rd_index     <= 4'h0;
      pending_read <= 1'b0;
      pending_high <= 1'b0;
      rx_valid_d   <= 1'b0;
    end else begin
      rx_valid_d  <= rx_valid;
      arm_pulse   <= 1'b0;
      clear_pulse <= 1'b0;

      // Register-backed memory is asynchronous-read. Waiting one system clock
      // after changing rd_index makes the protocol portable to synchronous
      // memory in a later version.
      if (pending_read) begin
        tx_data      <= pending_high ? rd_data[15:8] : rd_data[7:0];
        pending_read <= 1'b0;
      end

      // The vendor SPI target holds rx_valid until synchronized CS deassertion.
      // Execute each received byte once, on the rising edge of that level.
      if (rx_valid && !rx_valid_d) begin
        casez (rx_data)
          8'h00: begin
            // NOP/dummy byte: preserve the current response.
          end
          8'h01: tx_data <= {4'h2, capturing, primed, triggered, done};
          8'h02: begin
            arm_pulse <= 1'b1;
            tx_data   <= 8'ha2;
          end
          8'h03: begin
            clear_pulse <= 1'b1;
            tx_data     <= 8'ha3;
          end
          8'b0001????: begin
            rd_index     <= rx_data[3:0];
            pending_high <= 1'b0;
            pending_read <= 1'b1;
          end
          8'b0010????: begin
            rd_index     <= rx_data[3:0];
            pending_high <= 1'b1;
            pending_read <= 1'b1;
          end
          8'h30: tx_data <= {4'h0, trigger_ptr};
          8'h7e: tx_data <= 8'h53;
          8'h7f: tx_data <= 8'h02;
          default: tx_data <= 8'hee;
        endcase
      end
    end
  end

endmodule
