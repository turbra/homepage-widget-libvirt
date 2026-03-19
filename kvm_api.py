#!/usr/bin/env python3
from flask import Flask, jsonify
import subprocess
import psutil

app = Flask(__name__)

VIRSH_URI = "qemu:///system"


def run_command(command: list[str]) -> str:
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def get_vm_counts() -> tuple[int, int]:
    base_cmd = ["virsh", "--readonly", "-c", VIRSH_URI]

    total_output = run_command(base_cmd + ["list", "--all", "--name"])
    total_vms = [line.strip() for line in total_output.splitlines() if line.strip()]

    running_output = run_command(base_cmd + ["list", "--state-running", "--name"])
    running_vms = [line.strip() for line in running_output.splitlines() if line.strip()]

    return len(running_vms), len(total_vms)


def get_host_resources() -> tuple[float, float]:
    cpu = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory().percent
    return cpu, mem


@app.route("/api/kvm", methods=["GET"])
def kvm_stats():
    try:
        running, total = get_vm_counts()
        cpu, mem = get_host_resources()

        return jsonify(
            {
                "vms": f"{running}/{total}",
                "resources": {
                    "cpu": round(cpu, 1),
                    "mem": round(mem, 1),
                },
            }
        ), 200

    except subprocess.CalledProcessError as e:
        return jsonify(
            {
                "error": "Failed to query libvirt via virsh",
                "details": e.stderr.strip() if e.stderr else str(e),
            }
        ), 500
    except Exception as e:
        return jsonify(
            {
                "error": "Unexpected error",
                "details": str(e),
            }
        ), 500


@app.route("/healthz", methods=["GET"])
def healthz():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)