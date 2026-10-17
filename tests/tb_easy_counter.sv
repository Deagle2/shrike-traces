`timescale 1ns/1ps
module tb_easy_counter;
  parameter integer TRIGGER_STEP = 17;
  reg clk = 0;
  always #10 clk = ~clk;
  reg rst_n = 0;
  reg [3:0] read_index = 0;
  integer cycles, i, t, count_expected, direction, attempt;
  reg [15:0] expected;
  ShrikeTracesEasy dut(
    .clk(clk), .rst_n(rst_n), .spi_ss_n(1'b1), .spi_sck(1'b0), .spi_mosi(1'b0),
    .clk_en(), .spi_miso(), .spi_miso_en(), .LED(), .LED_en()
  );
  initial begin
    force dut.analyzer.arm = 1'b0;
    force dut.analyzer.clear = 1'b0;
    force dut.analyzer.rd_index = read_index;
    repeat (3) @(negedge clk);
    rst_n = 1;
    // Check rearming/reset of a stateful DUT as well as the first capture.
    for (attempt = 0; attempt < 2; attempt = attempt + 1) begin
      @(negedge clk);
      force dut.analyzer.clear = 1'b1;
      @(negedge clk);
      force dut.analyzer.clear = 1'b0;
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
        t = (TRIGGER_STEP - 8 + i) % 64;
        count_expected = (t <= 32) ? t : 64-t;
        direction = (t < 32) ? 1 : 0;
        // profile: count[9:2], up_down[1], reset[0]
        expected = (count_expected << 2) | (direction << 1);
        if (dut.analyzer.rd_data !== expected)
          $fatal(1, "attempt %0d sample %0d got %04x expected %04x", attempt, i, dut.analyzer.rd_data, expected);
      end
    end
    $display("PASS: counter trigger step %0d; 16 samples and rearm verified", TRIGGER_STEP);
    $finish;
  end
endmodule
