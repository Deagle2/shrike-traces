# Third-party notices

## shrike-gen

The build generator is included as a pinned Git submodule from
https://github.com/trholding/shrike-gen at commit
`0943514335f9787969c52fb5587fcbea8edb66d9`. It is distributed under the MIT
License. Its upstream license remains in `third_party/shrike-gen/LICENSE`; a
copy is also retained in `LICENSES/MIT-shrike-gen.txt`.

shrike-traces copies the generator into ignored build output. On Windows it
adjusts that disposable copy for date formatting and explicit UTF-8 file I/O.
The pinned submodule itself is unchanged.

## SPI target

`ffpga/src/spi_target.v` is adapted from the SPI target used by Vicharak's
Shrike CORDIC example. The Shrike repository classifies HDL/RTL as hardware and
licenses its hardware designs under CERN Open Hardware Licence v1.2. The exact
upstream license is retained in `LICENSES/CERN-OHL-1.2.txt`.

Upstream documentation location:
https://github.com/vicharak-in/shrike

Modified documentation notice: the SPI target was integrated into shrike-traces
in October 2026 and connected to a new command/status/trace-register layer for
the SLG47910 capture core. shrike-traces' other original files are not assigned
a repository-wide license merely by this notice.

## ISCAS benchmark netlists

`ffpga/src/iscas85_c17.v` is an unmodified structural redistribution of the
historic ISCAS'85 `c17` benchmark from:

- https://github.com/santoshsmalagi/Benchmarks/blob/8a0b4d2ca0e85e9d2425a96212605e5327a22c61/ISCAS85/c17/c17.v
- Original benchmark authors: F. Brglez and H. Fujiwara

The historic netlist has no formal modern license notice. It is excluded from
shrike-traces' CERN-OHL statement. The same treatment applies to the included
ISCAS'89 `s27` and ISCAS'85 `c432` netlists, whose exact source revisions still
need to be recorded. Their harnesses and analyzer integration are original
shrike-traces work.
