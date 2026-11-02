"""Infer capacitor rated voltage and dielectric from BOM fields or well-documented MPN schemes."""
import re
from .units import find_voltage

DIELECTRICS = ["C0G", "NP0", "NPO", "X5R", "X6S", "X7R", "X7S", "X7T", "X8R", "Y5V", "Z5U",
               "TANTALUM", "POLYMER", "ALUMINUM", "ELECTROLYTIC", "FILM"]

# Samsung Electro-Mechanics MLCC part numbering: CL 21 A 106 K P F N N N E
#   [size][dielectric][cap][tol][voltage]...  (Samsung "MLCC Part Numbering" guide)
SAMSUNG_TC = {"A": "X5R", "B": "X7R", "C": "C0G", "F": "Y5V", "X": "X6S", "Y": "X7S", "Z": "X7T", "W": "X5R"}
SAMSUNG_V = {"S": 2.5, "R": 4.0, "Q": 6.3, "P": 10, "O": 16, "A": 25, "L": 35, "B": 50, "C": 100, "D": 200, "E": 250, "G": 500, "H": 630, "I": 1000}
# Murata GRM: GRM 21 B R6 1A 106 K ... ; voltage code 0E=2.5 0G=4 0J=6.3 1A=10 1C=16 1E=25 YA=35 1H=50 2A=100
MURATA_V = {"0E": 2.5, "0G": 4, "0J": 6.3, "1A": 10, "1C": 16, "1E": 25, "YA": 35, "1V": 35, "1H": 50, "2A": 100, "2E": 250}
MURATA_TC = {"5C": "C0G", "R6": "X5R", "R7": "X7R", "C7": "X7S", "C8": "X6S", "D7": "X7T", "F5": "Y5V"}
# Yageo CC series: CC 0805 K R X7R 9 BB 104 ; voltage digit 5=6.3 6=10 7=16 8=25 9=50 0=100
YAGEO_V = {"4": 4, "5": 6.3, "6": 10, "7": 16, "8": 25, "9": 50, "0": 100, "A": 200}


def decode_mpn(mpn):
    """Return (rated_voltage, dielectric, scheme) or (None, None, None)."""
    if not mpn:
        return None, None, None
    p = mpn.strip().upper()
    m = re.match(r"^CL(\d{2})([A-Z])(\d{3}|\dR\d)([A-Z])([A-Z])", p)
    if m and m.group(5) in SAMSUNG_V:
        return SAMSUNG_V[m.group(5)], SAMSUNG_TC.get(m.group(2)), "Samsung CL"
    m = re.match(r"^GR[MJT]\d{2}[0-9A-Z]([A-Z0-9]{2})([0-9A-Z]{2})\d{3}", p)
    if m and m.group(2) in MURATA_V:
        return MURATA_V[m.group(2)], MURATA_TC.get(m.group(1)), "Murata GRM"
    m = re.match(r"^CC\d{4}[A-Z]{2}(NPO|X7R|X5R|Y5V)(\w)", p)
    if m and m.group(2) in YAGEO_V:
        return YAGEO_V[m.group(2)], {"NPO": "C0G"}.get(m.group(1), m.group(1)), "Yageo CC"
    return None, None, None


def dielectric_from_text(*texts):
    for t in texts:
        u = str(t or "").upper()
        for d in DIELECTRICS:
            if re.search(r"(?<![A-Z0-9])" + d + r"(?![A-Z0-9])", u):
                return {"NP0": "C0G", "NPO": "C0G", "ELECTROLYTIC": "ALUMINUM"}.get(d, d)
    return None


def cap_rating(row, cols):
    """Returns dict(rated_v, dielectric, source)."""
    rated = diel = None
    src = []
    v = row.get(cols.get("voltage", "Voltage"), "")
    if v:
        rated = find_voltage(v) or find_voltage(v + "V")
        if rated:
            src.append("Voltage field")
    d = row.get(cols.get("dielectric", "Dielectric"), "")
    if d:
        diel = dielectric_from_text(d)
    mpn = row.get(cols.get("mpn", "MPN"), "")
    mv, md, scheme = decode_mpn(mpn)
    if rated is None and mv:
        rated = mv
        src.append(f"MPN decode ({scheme})")
    if diel is None and md:
        diel = md
    if rated is None:
        rated = find_voltage(row.get(cols.get("value", "Value"), ""))
        if rated:
            src.append("Value text")
    if diel is None:
        diel = dielectric_from_text(row.get(cols.get("value", "Value"), ""), row.get(cols.get("description", "Description"), ""))
    return {"rated_v": rated, "dielectric": diel, "source": ", ".join(src) or None}
