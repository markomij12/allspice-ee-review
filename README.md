# ee-design-review: an AllSpice Action for capacitor voltage derating and power budgets

This is a Docker-based AllSpice Action. It uses the same layout as AllSpice's own `generate-bom` and `generate-netlist` actions:
- `action.yml` with `runs: docker`
- an `entrypoint.py` argparse CLI
- `ALLSPICE_AUTH_TOKEN` from `${{ github.token }}`, plus `--allspice_hub_url ${{ github.server_url }}` and `--source_ref ${{ github.sha }}`

It reviews a design from **BOM + netlist**. It works on py-allspice's own data shapes:
- BOM: `list[dict[str,str]]`
- Netlist: `dict[net, set["REF.PIN"]]`

so its output from the Hub and from local files is the same.

## Checks

| Check | What it does | Severity |
|---|---|---|
| `cap-derating` | For every capacitor it computes the working voltage (max minus min rail voltage across its two nets) and compares it with the rated voltage. The allowed ratio depends on the dielectric. | **error** if working V is above the rating. **warning** if it is above the derating limit or the rating is missing. **info** if a net voltage is unknown. |
| `power-budget` (optional) | Sums the configured load currents of the parts on a regulator's output rail and compares the total with the regulator's maximum current. | **error** above the maximum, **warning** above `margin` (default 80%) |
| `regulator-feedback` (optional) | Finds the top and bottom resistors on the regulator's FB pin in the netlist and computes Vout = Vref·(1+Rtop/Rbot). It compares this with the rail voltage. | **error** if it is more than `tolerance` off (default 5%) |

### Default derating limits (max working/rated)

All limits can be changed in the config under `derating:`. These are common house-rule values, not a standard. Tighten them to your company's policy.

| Dielectric | Limit |
|---|---|
| C0G/NP0, film, polymer, aluminium | 80% |
| X5R, X6S, X7R, X7S, X7T, X8R, Y5V, Z5U, tantalum | 50% |
| Unknown | 50% (most conservative) |

### Where the rating and dielectric come from, in order

1. The `Voltage` / `Dielectric` BOM columns. Column names can be changed under `columns:`.
2. An MPN decode for documented numbering schemes: Samsung `CL…`, Murata `GRM/GRJ/GRT…`, Yageo `CC…`.
3. Free text in `Value` / `Description`, e.g. `10uF 16V X7R` or `6V3`.

### Where the working voltage comes from

1. `rails:` in the config: a net name or regex mapped to worst-case DC volts.
2. `rail_pins:` in the config: a pin such as `U2.4` mapped to volts. This keeps working when KiCad auto-generates net names like `Net-(U2-VCC)`.
3. Net names: `3V3`, `+5V`, `1V8`, `12V`. This is a heuristic and is reported as `name-heuristic` in the JSON. Turn it off with `infer_rails_from_names: false`.
4. Ground nets: `GND*`, `VSS`, or anything in `ground_nets:`.

The check never guesses a voltage for a signal net. If a net's voltage is unknown, the capacitor is reported as `info` and skipped.

## Modes

- **Hub mode** (Altium, OrCAD, DeHDL, System Capture, DxDesigner): `source_path` + `pcb_file`. The action calls `allspice.utils.bom_generation.generate_bom` and `allspice.utils.netlist_generation.generate_netlist`. Netlist net names come from the PCB. See `examples/workflows/ee-review-altium.yml`.
- **Local mode** (KiCad or anything else): `netlist_file` + optional `bom_file`.
  - The netlist can be a KiCad `.net` (sexpr) or JSON `{net: [REF.PIN]}`.
  - The BOM is a CSV. Grouped designators such as `C2-C5, C7` are expanded.
  - If no BOM is given, the component fields are read from the KiCad netlist.
  - See `examples/workflows/ee-review-kicad.yml`, which runs `kicad-cli` in the `kicad/kicad:9.0` image.

## Outputs

- `ee_review.md`: Markdown table of findings, also appended to `$GITHUB_STEP_SUMMARY` if that is set.
- `ee_review.json`: every finding with nets, working V, rated V, ratio, limit, and the source of the rating.
- Exit code: controlled by `fail_on`: `error` (default), `warning`, or `never`.

## Local test results

These were produced locally with `kicad-cli 9.0.9`. The full outputs are in `examples/out/`.

| Design | Data | Result |
|---|---|---|
| **halfmarble/NEAToBOARD** (CERN-OHL-P), `examples/neatoboard_BOM.csv` + `.net` | Real BOM with Samsung and Yageo MPNs. Ratings are decoded from the MPNs, e.g. CL21A106KPFNNNE becomes 10 V X5R. | 12 caps pass (21–33% of rating). **1 warning on power budget:** the ESP32-WROOM-32D needs a supply that can deliver at least 500 mA (Espressif datasheet), and U3 (ME6211C33) is rated 500 mA at VIN = 4.3 V (Microne datasheet). That is 100% of its capacity with no margin, and less from a 3.7 V cell, because that rating is specified at VIN = VOUT + 1 V. |
| **shyver/sensor-node** (MIT), upstream, unmodified | Real BOM: values only, no voltage ratings or MPNs | **9 warnings: "no voltage rating in BOM"** for caps on 3.3, 4.2 and 5.25 V rails. The upstream BOM cannot be checked for derating. That is a real gap, because a fab house would fill it with whatever is in stock. Feedback divider R2 511k / R3 91k → 3.31 V passes (VFB 0.5 V, TI datasheet). Power budget passes: 500 mA of 2 A. |
| **sensor-node, seeded-error copy** (`examples/sensor-node-planted.net`) | The same BOM with `Voltage`/`Dielectric` fields added (**assumed** ratings) and a few deliberately introduced errors | **2 errors, 1 warning:** C2 is rated 2.5 V on the 3.3 V rail (132%). R3 changed to 51k makes U1 output 5.51 V instead of 3.3 V. C3 (assumed 10 V X5R) on the 5.25 V VBUS-derived node is at 52%, above the 50% limit. |

Unit tests: `python -m pytest tests`. There are 6 tests, covering:
- SI and voltage parsing
- MPN decoders
- derating thresholds
- the feedback divider
- an end-to-end run on the planted example

## Not tested / limitations

- **Hub mode was not run.** I did not have an AllSpice Hub token to run it against. The py-allspice 4.3.0 call signatures used were checked by importing the library.
- Working voltage is the DC rail voltage. Ripple, transients and AC bias are not modelled, and DC-bias capacitance loss is not modelled either.
- Power-budget loads and regulator limits come from you in the config, with a `source:` field. The action does not look up datasheets.
- The feedback check assumes a simple 2-resistor divider between the rail and GND, with nothing in parallel such as a feed-forward cap or trim network.

## License

MIT (see `LICENSE`). Example designs keep their own licenses: NEAToBOARD by halfmarble (CERN-OHL-P-2.0), sensor-node by shyver (MIT).

Marko Mijatovic, Penn EE (markomij@engineering.upenn.edu)
