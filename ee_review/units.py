import re
_SI = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "μ": 1e-6, "m": 1e-3, "k": 1e3, "K": 1e3, "M": 1e6, "G": 1e9, "R": 1.0, "": 1.0}

def parse_si(text, unit=""):
    """'4.7k' -> 4700, '0.1µF' -> 1e-7, '4k7' -> 4700, '51k' -> 51000. Returns None if unparseable."""
    if text is None:
        return None
    t = str(text).strip().replace(" ", "")
    if unit:
        t = re.sub(re.escape(unit) + r"$", "", t, flags=re.I)
    m = re.fullmatch(r"(\d+)([pnuµμmkKMGR])(\d+)", t)  # 4k7 / 2R2 style
    if m:
        return float(f"{m.group(1)}.{m.group(3)}") * _SI[m.group(2)]
    m = re.fullmatch(r"(\d+(?:\.\d+)?)([pnuµμmkKMGR]?)", t)
    if m:
        return float(m.group(1)) * _SI[m.group(2)]
    return None

def find_voltage(text):
    """First voltage token in free text: '10uF 16V X7R' -> 16.0, '6V3' -> 6.3. None if absent."""
    if not text:
        return None
    s = str(text)
    m = re.search(r"(?<![\w.])(\d+)V(\d+)(?!\w)", s)  # 6V3
    if m:
        return float(f"{m.group(1)}.{m.group(2)}")
    m = re.search(r"(?<![\w.])(\d+(?:\.\d+)?)\s*(k?)V(?:DC)?(?![a-zA-Z])", s)
    if m:
        return float(m.group(1)) * (1000 if m.group(2) else 1)
    return None

def expand_designators(text):
    """'C1, C6' / 'C2-C5, C7' / 'R1 R2' -> ['C1', 'C6', ...]"""
    out = []
    for tok in re.split(r"[,\s;]+", str(text or "").strip()):
        if not tok:
            continue
        m = re.fullmatch(r"([A-Za-z_#]+)(\d+)-(?:[A-Za-z_#]+)?(\d+)", tok)
        if m:
            out += [f"{m.group(1)}{i}" for i in range(int(m.group(2)), int(m.group(3)) + 1)]
        else:
            out.append(tok)
    return out
