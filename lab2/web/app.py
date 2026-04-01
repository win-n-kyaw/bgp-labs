"""
BGP Lab2 Web UI — Live FRR integration via Vagrant SSH.
Run from the lab2/ directory:  python web/app.py
"""

import subprocess
import json
import os
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

ROUTERS = ["r1", "r2", "r3", "r4"]
LAB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

TOPOLOGY = {
    "routers": {
        "r1": {"as": 65001, "loopback": "1.1.1.1", "x": 100, "y": 100},
        "r2": {"as": 65002, "loopback": "2.2.2.2", "x": 500, "y": 100},
        "r3": {"as": 65003, "loopback": "3.3.3.3", "x": 500, "y": 400},
        "r4": {"as": 65004, "loopback": "4.4.4.4", "x": 100, "y": 400},
    },
    "links": [
        {"from": "r1", "to": "r2", "subnet": "10.0.12.0/24", "ips": {"r1": "10.0.12.2", "r2": "10.0.12.3"}},
        {"from": "r1", "to": "r3", "subnet": "10.0.13.0/24", "ips": {"r1": "10.0.13.2", "r3": "10.0.13.4"}},
        {"from": "r1", "to": "r4", "subnet": "10.0.14.0/24", "ips": {"r1": "10.0.14.2", "r4": "10.0.14.5"}},
        {"from": "r2", "to": "r3", "subnet": "10.0.23.0/24", "ips": {"r2": "10.0.23.3", "r3": "10.0.23.4"}},
        {"from": "r2", "to": "r4", "subnet": "10.0.24.0/24", "ips": {"r2": "10.0.24.3", "r4": "10.0.24.5"}},
        {"from": "r3", "to": "r4", "subnet": "10.0.34.0/24", "ips": {"r3": "10.0.34.4", "r4": "10.0.34.5"}},
    ],
}


def vtysh(router, command):
    """Run a vtysh command on a router via vagrant ssh."""
    try:
        result = subprocess.run(
            ["vagrant", "ssh", router, "-c", f"sudo vtysh -c '{command}'"],
            capture_output=True, text=True, timeout=15, cwd=LAB_DIR,
        )
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return f"ERROR: timeout reaching {router}"
    except Exception as e:
        return f"ERROR: {e}"


def vtysh_config(router, config_lines):
    """Push a block of vtysh config commands to a router."""
    commands = "\\n".join(["configure terminal"] + config_lines + ["end"])
    try:
        result = subprocess.run(
            ["vagrant", "ssh", router, "-c",
             f"sudo vtysh -c 'configure terminal' " +
             " ".join(f"-c '{line}'" for line in config_lines) +
             " -c 'end'"],
            capture_output=True, text=True, timeout=15, cwd=LAB_DIR,
        )
        return result.stdout.strip() + result.stderr.strip()
    except subprocess.TimeoutExpired:
        return f"ERROR: timeout reaching {router}"
    except Exception as e:
        return f"ERROR: {e}"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/topology")
def api_topology():
    return jsonify(TOPOLOGY)


@app.route("/api/status")
def api_status():
    """Get BGP summary from all routers."""
    results = {}
    for r in ROUTERS:
        results[r] = {
            "bgp_summary": vtysh(r, "show bgp summary"),
            "bgp_table": vtysh(r, "show bgp ipv4 unicast"),
            "route_maps": vtysh(r, "show route-map"),
            "prefix_lists": vtysh(r, "show ip prefix-list"),
            "running_config": vtysh(r, "show running-config"),
        }
    return jsonify(results)


@app.route("/api/router/<router>/cmd", methods=["POST"])
def api_cmd(router):
    """Run an arbitrary show command on a router."""
    if router not in ROUTERS:
        return jsonify({"error": "unknown router"}), 400
    cmd = request.json.get("cmd", "")
    if not cmd.startswith("show"):
        return jsonify({"error": "only show commands allowed via this endpoint"}), 400
    return jsonify({"router": router, "command": cmd, "output": vtysh(router, cmd)})


@app.route("/api/router/<router>/config", methods=["POST"])
def api_config(router):
    """Push config lines to a router."""
    if router not in ROUTERS:
        return jsonify({"error": "unknown router"}), 400
    lines = request.json.get("lines", [])
    if not lines:
        return jsonify({"error": "no config lines provided"}), 400
    output = vtysh_config(router, lines)
    return jsonify({"router": router, "lines": lines, "output": output})


@app.route("/api/router/<router>/bgp")
def api_bgp(router):
    """Get detailed BGP state for one router."""
    if router not in ROUTERS:
        return jsonify({"error": "unknown router"}), 400
    return jsonify({
        "router": router,
        "bgp_summary": vtysh(router, "show bgp summary"),
        "bgp_table": vtysh(router, "show bgp ipv4 unicast"),
        "ip_route": vtysh(router, "show ip route"),
        "route_maps": vtysh(router, "show route-map"),
        "prefix_lists": vtysh(router, "show ip prefix-list"),
    })


if __name__ == "__main__":
    print("BGP Lab2 Web UI")
    print("Run from lab2/ directory. VMs must be up (vagrant up).")
    print("http://localhost:5000")
    app.run(debug=True, port=5000)
