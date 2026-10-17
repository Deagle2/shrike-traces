`timescale 1ns/1ps
module tb_easy_multiplier;
  reg clk = 0;
  always #10 clk = ~clk;
  reg rst_n = 0;
  reg [3:0] read_index = 0;
  integer cycles, i, stimulus, a, b;
  reg [15:0] expected;
  ShrikeTracesEasy dut(
    .clk(clk), .rst_n(rst_n), .spi_ss_n(1'b1), .spi_sck(1'b0), .spi_mosi(1'b0),
    .clk_en(), .spi_miso(), .spi_miso_en(), .LED(), .LED_en()
  );
  initial begin
    // Exercise the generated DUT/wrapper and real capture core. The existing
    // pin-level SPI testbench separately covers the transport/register path.
    force dut.analyzer.arm = 1'b0;
    force dut.analyzer.clear = 1'b0;
    force dut.analyzer.rd_index = read_index;
    repeat (3) @(negedge clk);
    rst_n = 1;
    @(negedge clk);
    force dut.analyzer.arm = 1'b1;
    @(negedge clk);
    force dut.analyzer.arm = 1'b0;
    cycles = 0;
    while (!dut.analyzer.done && cycles < 300) begin
      @(negedge clk);
      cycles = cycles + 1;
    end
    if (!dut.analyzer.done) $fatal(1, "Capture timed out");
    for (i = 0; i < 16; i = i + 1) begin
      read_index = i;
      #1;
      stimulus = 95 + i;
      a = stimulus >> 4;
      b = stimulus & 15;
      expected = ((a*b) << 8) | stimulus;
      if (dut.analyzer.rd_data !== expected)
        $fatal(1, "sample %0d got %04x expected %04x", i, dut.analyzer.rd_data, expected);
    end
    read_index = 8;
    #1;
    if (dut.analyzer.rd_data !== 16'h2a67) $fatal(1, "Wrong trigger sample");
    $display("PASS: generated multiplier wrapper captures 16 correct samples; index 8 is 6*7=42");
    $finish;
  end
endmodule
