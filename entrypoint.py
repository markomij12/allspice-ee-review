#! /usr/bin/env python3
# EE design review: capacitor voltage derating + optional power budget / regulator feedback.
# Follows the layout of AllSpice's py-allspice actions (argparse CLI, ALLSPICE_AUTH_TOKEN env var,
# --allspice_hub_url / --source_ref args, logging to stderr). See README.md.
import argparse, json, logging, os, sys
import yaml
from ee_review import __version__
from ee_review.checks import cap_derating, power_budget
from ee_review.io import kicad_components, load_bom_csv, load_netlist

logger = logging.getLogger("ee_review")
handler = logging.StreamHandler(sys.stderr)
handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
logger.addHandler(handler)
SEV_ORDER = {"error": 3, "warning": 2, "info": 1, "pass": 0}


def from_hub(args, cfg):
    from allspice import AllSpice
    from allspice.utils.bom_generation import generate_bom
    from allspice.utils.netlist_generation import generate_netlist
    token = os.environ.get("ALLSPICE_AUTH_TOKEN")
    if not token:
        logger.critical("Please set the environment variable ALLSPICE_AUTH_TOKEN")
        sys.exit(2)
    client = AllSpice(token_text=token, allspice_hub_url=args.allspice_hub_url) if args.allspice_hub_url else AllSpice(token_text=token)
    owner, name = args.repository.split("/")
    repo = client.get_repository(owner, name)
    columns = cfg.get("hub_bom_columns") or {"Designator": ["Designator"], "Value": ["Value", "Comment"],
                                              "MPN": ["MPN", "Manufacturer Part Number", "PART_NUMBER"],
                                              "Voltage": ["Voltage", "Rated Voltage", "VOLTAGE"],
                                              "Dielectric": ["Dielectric", "Temperature Coefficient", "TC"],
                                              "Description": ["Description"]}
    logger.info("Generating BOM from %s@%s", args.source_path, args.source_ref)
    bom = generate_bom(client, repo, args.source_path, columns, ref=args.source_ref)  # ungrouped -> one row per designator
    logger.info("Generating netlist from %s@%s", args.pcb_file, args.source_ref)
    netlist = generate_netlist(client, repo, args.pcb_file, args.source_ref)
    return bom, netlist


def render_markdown(title, findings, show_pass):
    counts = {s: sum(1 for f in findings if f["severity"] == s) for s in SEV_ORDER}
    lines = [f"# {title}", "", f"**{counts['error']} error(s), {counts['warning']} warning(s), {counts['info']} info, {counts['pass']} pass**", ""]
    for check in sorted({f["check"] for f in findings}):
        rows = sorted([f for f in findings if f["check"] == check and (show_pass or f["severity"] != "pass")],
                      key=lambda f: (-SEV_ORDER[f["severity"]], f["ref"]))
        if not rows:
            continue
        lines += [f"## {check}", "", "| Severity | Ref | Finding |", "|---|---|---|"]
        lines += [f"| {f['severity'].upper()} | {f['ref']} | {f['message'].replace('|', '/')} |" for f in rows]
        lines.append("")
    return "\n".join(lines), counts


def main(argv=None):
    p = argparse.ArgumentParser(prog="ee_design_review", description="Capacitor derating and power-budget review.")
    p.add_argument("repository", nargs="?", help="owner/repo on AllSpice Hub (hub mode)")
    p.add_argument("--source_path", help="Hub mode: project file for BOM (.PrjPcb/.DSN/...)")
    p.add_argument("--pcb_file", help="Hub mode: PCB file for netlist")
    p.add_argument("--source_ref", default="main")
    p.add_argument("--allspice_hub_url")
    p.add_argument("--bom_file", help="Local mode: BOM CSV")
    p.add_argument("--netlist_file", help="Local mode: KiCad .net or JSON netlist")
    p.add_argument("--config", help="YAML config (rails, derating, power)")
    p.add_argument("--output_file", default="ee_review.md")
    p.add_argument("--json_file", default="")
    p.add_argument("--fail_on", default="error", choices=["error", "warning", "never"])
    p.add_argument("--show_pass", default="false")
    p.add_argument("--title", default="EE design review")
    p.add_argument("--log-level", default="INFO")
    args = p.parse_args(argv)
    logger.setLevel(args.log_level.upper())
    logger.info("ee-design-review %s", __version__)
    cfg = yaml.safe_load(open(args.config)) if args.config else {}
    cfg = cfg or {}

    if args.netlist_file:
        netlist = load_netlist(args.netlist_file)
        if args.bom_file:
            bom = load_bom_csv(args.bom_file)
        elif open(args.netlist_file).read(64).lstrip().startswith("(export"):
            bom = kicad_components(open(args.netlist_file).read())
        else:
            p.error("--bom_file is required with a JSON netlist")
    elif args.repository:
        bom, netlist = from_hub(args, cfg)
    else:
        p.error("give --netlist_file (local) or a repository (hub mode)")

    # rail_pins: pin-anchored rail voltages (robust to auto-generated net names like Net-(U2-VCC))
    for pin, v in (cfg.get("rail_pins") or {}).items():
        nets = [n for n, ps in netlist.items() if pin in ps]
        if nets:
            cfg.setdefault("rails", {})[nets[0]] = v
        else:
            logger.warning("rail_pins: %s not found in netlist", pin)
    findings = cap_derating(bom, netlist, cfg) + power_budget(bom, netlist, cfg)
    md, counts = render_markdown(args.title, findings, args.show_pass.lower() == "true")
    with open(args.output_file, "w") as f:
        f.write(md + "\n")
    if args.json_file:
        with open(args.json_file, "w") as f:
            json.dump({"version": __version__, "counts": counts, "findings": findings}, f, indent=2, default=list)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write(md + "\n")
    print(md)
    if args.fail_on == "error" and counts["error"]:
        return 1
    if args.fail_on == "warning" and (counts["error"] or counts["warning"]):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
