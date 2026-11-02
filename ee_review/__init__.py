"""EE design-review checks for AllSpice Actions: capacitor voltage derating and power budget.

Data model follows py-allspice:
  * BOM     -> list[dict[str, str]]          (allspice.utils.bom_generation.Bom)
  * Netlist -> dict[str, set[str]] net->{"REF.PIN"}  (allspice.utils.netlist_generation.Netlist)
"""
__version__ = "0.1.0"
