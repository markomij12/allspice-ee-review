import os, sys, subprocess
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from ee_review.units import parse_si, find_voltage, expand_designators
from ee_review.parts import decode_mpn, cap_rating
from ee_review.checks import cap_derating, power_budget
from ee_review.rails import heuristic_voltage
HERE = os.path.dirname(os.path.dirname(__file__))

def test_units():
    assert parse_si("4k7") == 4700 and parse_si("51k") == 51000 and abs(parse_si("0.1µF", "F") - 1e-7) < 1e-15
    assert find_voltage("10uF 16V X7R") == 16 and find_voltage("6V3") == 6.3 and find_voltage("22µF") is None
    assert expand_designators("C2-C5, C7") == ["C2", "C3", "C4", "C5", "C7"]

def test_mpn_decode():
    assert decode_mpn("CL21A106KPFNNNE")[:2] == (10, "X5R")       # Samsung 10 uF 10 V X5R
    assert decode_mpn("CL21B105KOFNNNE")[:2] == (16, "X7R")       # Samsung 1 uF 16 V X7R
    assert decode_mpn("CC0805JRNPO9BN120")[:2] == (50, "C0G")     # Yageo 12 pF 50 V NP0
    assert decode_mpn("GRM21BR61A106KE19L")[:2] == (10, "X5R")    # Murata 10 uF 10 V X5R
    assert decode_mpn("RC0603FR-0710KL") == (None, None, None)

def test_rail_names():
    assert heuristic_voltage("/Power/3V3") == 3.3 and heuristic_voltage("+5V") == 5 and heuristic_voltage("VBAT") is None

def _net(v_net="3V3"):
    return {v_net: {"C1.1", "C2.1", "R1.1", "U1.6"}, "GND": {"C1.2", "C2.2", "R2.2"}, "FB": {"R1.2", "R2.1", "U1.4"}}

def test_derating_levels():
    bom = [{"Designator": "C1", "Value": "10uF", "Voltage": "6.3V", "Dielectric": "X5R"},
           {"Designator": "C2", "Value": "100nF", "Voltage": "2.5V", "Dielectric": "X7R"}]
    f = {x["ref"]: x for x in cap_derating(bom, _net(), {})}
    assert f["C1"]["severity"] == "warning"   # 3.3/6.3 = 52% > 50%
    assert f["C2"]["severity"] == "error"     # over absolute rating
    f = {x["ref"]: x for x in cap_derating([dict(bom[0], Dielectric="C0G")], _net(), {})}
    assert f["C1"]["severity"] == "pass"      # 52% < 80% for C0G

def test_feedback_divider():
    bom = [{"Designator": "R1", "Value": "511k"}, {"Designator": "R2", "Value": "51k"}]
    cfg = {"power": {"regulators": [{"ref": "U1", "rail": "3V3", "max_current_ma": 2000, "feedback": {"pin": "4", "vref": 0.5}}], "loads": []}}
    fb = [x for x in power_budget(bom, _net(), cfg) if x["check"] == "regulator-feedback"][0]
    assert fb["severity"] == "error" and abs(fb["vout"] - 5.51) < 0.01

def test_examples_end_to_end():
    r = subprocess.run([sys.executable, "entrypoint.py", "--netlist_file", "examples/sensor-node-planted.net", "--config",
                        "examples/sensor-node.yml", "--output_file", "/tmp/eer.md", "--json_file", "/tmp/eer.json"], cwd=HERE, capture_output=True, text=True)
    assert r.returncode == 1 and "C2" in r.stdout and "5.51 V" in r.stdout
