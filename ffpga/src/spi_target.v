`timescale 1ns/1ps

// SPI mode-0 target adapted from Vicharak's official CORDIC example.
module spi_target #(
  parameter CPOL  = 1'b0,
  parameter CPHA  = 1'b0,
  parameter WIDTH = 8,
  parameter LSB   = 1'b0
)(
  input                  i_clk,
  input                  i_rst_n,
  input                  i_enable,
  input                  i_ss_n,
  input                  i_sck,
  input                  i_mosi,
  output                 o_miso,
  output                 o_miso_oe,
  output reg [WIDTH-1:0] o_rx_data,
  output reg             o_rx_data_valid,
  input      [WIDTH-1:0] i_tx_data,
  output                 o_tx_data_hold
);

  reg [2:0] r_ss_n_sync;
  reg [2:0] r_sck_sync;
  reg [$clog2(WIDTH-1):0] r_transmission_count;
  reg [WIDTH-1:0] r_miso_data;

  wire w_sck_r_edge;
  wire w_sck_f_edge;
  wire w_sck_edge;
  wire w_sck_edge_op;

  always @(posedge i_clk or negedge i_rst_n) begin
    if (!i_rst_n)
      r_ss_n_sync <= 3'b111;
    else if (i_enable)
      r_ss_n_sync <= {r_ss_n_sync[1:0], i_ss_n};
    else
      r_ss_n_sync <= 3'b111;
  end

  always @(posedge i_clk or negedge i_rst_n) begin
    if (!i_rst_n)
      r_sck_sync <= 3'b000;
    else if (i_enable)
      r_sck_sync <= {r_sck_sync[1:0], i_sck};
    else
      r_sck_sync <= 3'b000;
  end

  assign w_sck_r_edge  = ~r_sck_sync[2] &  r_sck_sync[1];
  assign w_sck_f_edge  =  r_sck_sync[2] & ~r_sck_sync[1];
  assign w_sck_edge    = (CPHA ^ CPOL) ? w_sck_f_edge : w_sck_r_edge;
  assign w_sck_edge_op = (CPHA ^ CPOL) ? w_sck_r_edge : w_sck_f_edge;

  always @(posedge i_clk or negedge i_rst_n) begin
    if (!i_rst_n)
      r_transmission_count <= 'h0;
    else if (!i_enable || r_ss_n_sync[1])
      r_transmission_count <= 'h0;
    else if (w_sck_edge) begin
      if (r_transmission_count == WIDTH-1)
        r_transmission_count <= 'h0;
      else
        r_transmission_count <= r_transmission_count + 1'b1;
    end
  end

  always @(posedge i_clk or negedge i_rst_n) begin
    if (!i_rst_n)
      o_rx_data <= 'h0;
    else if (w_sck_edge) begin
      if (LSB)
        o_rx_data <= {i_mosi, o_rx_data[WIDTH-1:1]};
      else
        o_rx_data <= {o_rx_data[WIDTH-2:0], i_mosi};
    end
  end

  always @(posedge i_clk or negedge i_rst_n) begin
    if (!i_rst_n)
      o_rx_data_valid <= 1'b0;
    else if (r_ss_n_sync[1] ||
             (r_transmission_count == 0 && w_sck_edge))
      o_rx_data_valid <= 1'b0;
    else if (w_sck_edge && r_transmission_count == WIDTH-1)
      o_rx_data_valid <= 1'b1;
  end

  assign o_tx_data_hold = (~CPHA & r_ss_n_sync[2] & ~r_ss_n_sync[1]) |
                          (r_transmission_count == 0 && w_sck_edge_op);

  always @(posedge i_clk or negedge i_rst_n) begin
    if (!i_rst_n)
      r_miso_data <= 'h0;
    else if (o_tx_data_hold)
      r_miso_data <= i_tx_data;
    else if (w_sck_edge_op) begin
      if (LSB)
        r_miso_data <= r_miso_data >> 1;
      else
        r_miso_data <= r_miso_data << 1;
    end
  end

  assign o_miso    = LSB ? r_miso_data[0] : r_miso_data[WIDTH-1];
  assign o_miso_oe = ~r_ss_n_sync[2];

endmodule
