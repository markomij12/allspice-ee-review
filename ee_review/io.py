"""Loaders that normalise inputs into py-allspice's Bom / Netlist shapes."""
import csv, json, re
from .units import expand_designators

def load_bom_csv(path, ref_col=None):
    """CSV BOM (KiCad export, AllSpice generate-bom output, or hand-made). Grouped rows are expanded."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return []
    cands = [ref_col] if ref_col else ["Designator", "Reference", "Refs", "References", "RefDes", "Ref"]
    col = next((c for c in cands if c and c in rows[0]), None)
    if not col:
        raise ValueError(f"No designator column in {path}; columns: {list(rows[0])}")
    out = []
    for r in rows:
        for d in expand_designators(r[col]):
            e = dict(r); e["Designator"] = d; out.append(e)
    return out

def _sexpr_nets(text):
    nets = {}
    for m in re.finditer(r'\(net \(code "?\d+"?\) \(name "((?:[^"\\]|\\.)*)"\)', text):
        j = text.find("(net (code", m.end())
        body = text[m.end(): j if j > 0 else len(text)]
        nets[m.group(1)] = {f"{r}.{p}" for r, p in re.findall(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)', body)}
    return nets

def kicad_components(text):
    """Fields of components from a KiCad sexpr netlist (used when no BOM CSV is supplied)."""
    comps = []
    sec = text[text.find("(components"): text.find("(libparts")]
    for blk in re.split(r"\n\s*\(comp ", sec)[1:]:
        ref = re.search(r'\(ref "([^"]+)"\)', blk).group(1)
        row = {"Designator": ref}
        v = re.search(r'\(value "((?:[^"\\]|\\.)*)"\)', blk); row["Value"] = v.group(1) if v else ""
        fp = re.search(r'\(footprint "([^"]*)"\)', blk); row["Footprint"] = fp.group(1) if fp else ""
        for k, val in re.findall(r'\(field \(name "([^"]+)"\) "((?:[^"\\]|\\.)*)"\)', blk):
            row[k] = val
        for k, val in re.findall(r'\(property \(name "([^"]+)"\) \(value "((?:[^"\\]|\\.)*)"\)\)', blk):
            row.setdefault(k, val)
        if re.search(r'\(property \(name "dnp"\)', blk):
            row["DNP"] = "yes"
        comps.append(row)
    return comps

def load_netlist(path):
    """KiCad .net (sexpr) or JSON {net: [REF.PIN, ...]} -> dict[str, set[str]]."""
    text = open(path, encoding="utf-8").read()
    if text.lstrip().startswith("(export"):
        return _sexpr_nets(text)
    data = json.loads(text)
    return {k: set(v) for k, v in data.items()}

def pins_by_ref(netlist):
    """{ref: {pin: net}}"""
    out = {}
    for net, pins in netlist.items():
        for p in pins:
            ref, _, pin = p.partition(".")
            out.setdefault(ref, {})[pin] = net
    return out
