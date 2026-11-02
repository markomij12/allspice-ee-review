"""Design-review checks. Each returns a list of Finding dicts."""
import re
from .io import pins_by_ref
from .parts import cap_rating
from .rails import is_ground, rail_voltage, short
from .units import parse_si

# Default max(working V / rated V) by dielectric. Configurable; these are common
# house-rule values (50% for class-II ceramics and tantalum, 80% for C0G/film/
# polymer/aluminium), not a standard. Unknown dielectric -> most conservative.
DEFAULT_DERATING = {"C0G": 0.8, "FILM": 0.8, "POLYMER": 0.8, "ALUMINUM": 0.8,
                    "X5R": 0.5, "X6S": 0.5, "X7R": 0.5, "X7S": 0.5, "X7T": 0.5, "X8R": 0.5,
                    "Y5V": 0.5, "Z5U": 0.5, "TANTALUM": 0.5, "UNKNOWN": 0.5}

def F(check, severity, ref, msg, **data):
    return {"check": check, "severity": severity, "ref": ref, "message": msg, **data}

def _is_cap(ref, row):
    return bool(re.match(r"^C\d", ref)) and not re.match(r"^CON", ref, re.I)

def _dnp(row):
    return str(row.get("DNP", "")).lower() in ("yes", "true", "1", "dnp", "x")

def cap_derating(bom, netlist, cfg):
    cols = cfg.get("columns", {})
    table = {**DEFAULT_DERATING, **{k.upper(): float(v) for k, v in cfg.get("derating", {}).items()}}
    pins = pins_by_ref(netlist)
    out = []
    for row in bom:
        ref = row["Designator"]
        if not _is_cap(ref, row) or _dnp(row):
            continue
        nets = sorted(set(pins.get(ref, {}).values()))
        if not nets:
            out.append(F("cap-derating", "info", ref, "Capacitor not found in netlist; skipped."))
            continue
        volts = []
        for n in nets:
            if is_ground(n, cfg):
                volts.append((n, 0.0, "ground"))
            else:
                v, basis = rail_voltage(n, cfg)
                volts.append((n, v, basis))
        if any(v is None for _, v, _ in volts):
            unknown = [n for n, v, _ in volts if v is None]
            out.append(F("cap-derating", "info", ref, f"Working voltage unknown (net {', '.join(map(short, unknown))} has no rail voltage); add it under `rails:` to check this part.", nets=nets))
            continue
        vwork = max(v for _, v, _ in volts) - min(v for _, v, _ in volts)
        basis = sorted({b for _, _, b in volts if b and b != "ground"})
        r = cap_rating(row, cols)
        diel = (r["dielectric"] or "UNKNOWN").upper()
        limit = table.get(diel, table["UNKNOWN"])
        base = dict(nets=nets, working_v=round(vwork, 3), voltage_basis=basis, dielectric=diel,
                    value=row.get(cols.get("value", "Value"), ""), rating_source=r["source"])
        if r["rated_v"] is None:
            out.append(F("cap-derating", "warning", ref, f"No voltage rating in BOM (Voltage field, MPN, or value) for a part across {vwork:g} V; cannot verify derating.", rated_v=None, **base))
            continue
        ratio = vwork / r["rated_v"] if r["rated_v"] else float("inf")
        base.update(rated_v=r["rated_v"], ratio=round(ratio, 3), limit=limit)
        if vwork > r["rated_v"]:
            out.append(F("cap-derating", "error", ref, f"Rated {r['rated_v']:g} V but sees {vwork:g} V ({ratio:.0%} of rating): over absolute rating.", **base))
        elif ratio > limit:
            out.append(F("cap-derating", "warning", ref, f"{ratio:.0%} of {r['rated_v']:g} V rating exceeds {limit:.0%} {diel} derating limit (needs >= {vwork / limit:g} V part).", **base))
        else:
            out.append(F("cap-derating", "pass", ref, f"{ratio:.0%} of {r['rated_v']:g} V rating (limit {limit:.0%} {diel}).", **base))
    return out

def _divider_vout(netlist, pins, bom_by_ref, fb_net, out_net, vref):
    """Top resistor: FB<->out_net. Bottom: FB<->GND. Returns (vout, top, bottom) or None."""
    top = bot = None
    for ref, pm in pins.items():
        if not re.match(r"^R\d", ref) or len(pm) != 2:
            continue
        a, b = pm.values()
        if fb_net in (a, b):
            other = b if a == fb_net else a
            val = parse_si(bom_by_ref.get(ref, {}).get("Value", ""), "Ω") or parse_si(bom_by_ref.get(ref, {}).get("Value", "").rstrip("Ωohm"))
            if other == out_net:
                top = (ref, val)
            elif re.search(r"GND", other, re.I):
                bot = (ref, val)
    if top and bot and top[1] and bot[1]:
        return vref * (1 + top[1] / bot[1]), top, bot
    return None

def power_budget(bom, netlist, cfg):
    """Optional. cfg['power'] = {regulators: [...], loads: [...], margin: 0.8}"""
    pcfg = cfg.get("power")
    if not pcfg:
        return []
    out = []
    pins = pins_by_ref(netlist)
    bom_by_ref = {r["Designator"]: r for r in bom}
    margin = float(pcfg.get("margin", 0.8))
    for reg in pcfg.get("regulators", []):
        ref = reg["ref"]
        rail = reg["rail"]
        rail_nets = [n for n in netlist if short(n) == rail or n == rail]
        if not rail_nets:
            out.append(F("power-budget", "warning", ref, f"Rail '{rail}' not found in netlist."))
            continue
        rail_net = rail_nets[0]
        refs_on_rail = {p.partition(".")[0] for p in netlist[rail_net]}
        loads, unknown = [], []
        for ld in pcfg.get("loads", []):
            hit = [r for r in refs_on_rail if re.fullmatch(ld["match"], r) or re.fullmatch(ld["match"], bom_by_ref.get(r, {}).get("MPN", "") or "") or re.fullmatch(ld["match"], bom_by_ref.get(r, {}).get("Value", "") or "")]
            for r in sorted(hit):
                if r != ref:
                    loads.append((r, float(ld["current_ma"]), ld.get("source", "config")))
        total = sum(c for _, c, _ in loads)
        imax = float(reg["max_current_ma"])
        detail = dict(rail=rail, regulator_max_ma=imax, margin=margin, load_ma=round(total, 1),
                      loads=[{"ref": r, "ma": c, "source": s} for r, c, s in loads], regulator_source=reg.get("source"))
        if total > imax:
            out.append(F("power-budget", "error", ref, f"{rail}: budgeted load {total:g} mA exceeds {ref} max {imax:g} mA.", **detail))
        elif total > imax * margin:
            out.append(F("power-budget", "warning", ref, f"{rail}: budgeted load {total:g} mA is {total / imax:.0%} of {ref} max {imax:g} mA (design margin {margin:.0%}).", **detail))
        else:
            out.append(F("power-budget", "pass", ref, f"{rail}: {total:g} mA of {imax:g} mA ({total / imax:.0%}).", **detail))
        fb = reg.get("feedback")
        if fb:
            fb_pin = fb["pin"]
            fb_net = pins.get(ref, {}).get(fb_pin)
            res = _divider_vout(netlist, pins, bom_by_ref, fb_net, rail_net, float(fb["vref"])) if fb_net else None
            if not res:
                out.append(F("regulator-feedback", "warning", ref, f"Could not identify a 2-resistor divider on {ref} pin {fb_pin} (net {fb_net})."))
            else:
                vout, top, bot = res
                target, tol = rail_voltage(rail_net, cfg)[0], float(fb.get("tolerance", 0.05))
                d = dict(vout=round(vout, 3), target_v=target, top=top[0], top_ohm=top[1], bottom=bot[0], bottom_ohm=bot[1], vref=fb["vref"], vref_source=fb.get("source"))
                if target and abs(vout - target) / target > tol:
                    out.append(F("regulator-feedback", "error", ref, f"Divider {top[0]}/{bot[0]} sets {vout:.2f} V but rail {rail} expects {target:g} V (>{tol:.0%} off).", **d))
                else:
                    out.append(F("regulator-feedback", "pass", ref, f"Divider {top[0]}/{bot[0]} sets {vout:.2f} V (rail {rail} {target} V).", **d))
    return out
