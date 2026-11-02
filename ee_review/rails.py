"""Net -> worst-case DC voltage. Explicit config wins; name heuristics are a labelled fallback."""
import re

GROUND_RE = re.compile(r"(^|/)(A|D|P|SIG|CHASSIS)?GND\w*$|(^|/)(VSS|0V|EARTH)$", re.I)

def short(net):
    return net.rsplit("/", 1)[-1]

def is_ground(net, cfg):
    names = set(cfg.get("ground_nets", []))
    return short(net) in names or net in names or bool(GROUND_RE.search(net))

def heuristic_voltage(net):
    """'3V3'->3.3, '+5V'->5, '12V0'->12, 'VCC_1V8'->1.8. Returns None for anything else (e.g. VBAT)."""
    n = short(net).upper()
    m = re.search(r"(?<![0-9])(\d+)V(\d+)(?![0-9])", n)
    if m:
        return float(f"{m.group(1)}.{m.group(2)}")
    m = re.search(r"(?<![0-9.])(\d+(?:\.\d+)?)V(?![0-9A-Z])", n)
    if m:
        return float(m.group(1))
    return None

def rail_voltage(net, cfg):
    """Returns (volts, basis) where basis is 'config' or 'name-heuristic'."""
    rails = cfg.get("rails", {})
    for pat, v in rails.items():
        if short(net) == pat or net == pat or re.fullmatch(pat, short(net)) or re.fullmatch(pat, net):
            return float(v), "config"
    if cfg.get("infer_rails_from_names", True):
        v = heuristic_voltage(net)
        if v is not None:
            return v, "name-heuristic"
    return None, None
