# Homepage KVM Widget via Python + libvirt

Expose basic KVM host and VM stats for [Homepage](https://gethomepage.dev/) using a small Python API running on the libvirt host.

This project is intended for homelab or other trusted internal environments. It is not presented as a hardened multi-user or Internet-facing service.

The widget displays:

- VM count as `running/total`
- host CPU usage
- host memory usage

This uses Homepage `customapi` and links out to Cockpit for VM management.

![Homepage Widget](kvm-widget.png)

## Overview

Homepage does not have a native Cockpit KVM widget, so the clean approach is:

1. run a small Python API on the KVM host
2. query libvirt directly with `virsh`
3. return a small JSON payload
4. point Homepage `customapi` at that endpoint
5. run the API with `systemd` so it survives reboot

## Requirements

On the KVM host:

- Python 3
- `virsh`
- `flask`
- `psutil`

Install Python packages:

```bash
pip install flask psutil
````

## API behavior

The API should return JSON in this format:

```json
{
  "vms": "3/3",
  "resources": {
    "cpu": 12.4,
    "mem": 41.8
  }
}
```

Fields used by Homepage:

* `vms`
* `resources.cpu`
* `resources.mem`

## Security notes

This API only performs read-only `virsh` queries against `qemu:///system` and reports basic host resource usage. It does not create, modify, start, stop, or delete VMs.

That said, it still exposes operational details about the host:

* VM counts
* host CPU usage
* host memory usage

For that reason, this service should be treated as homelab or trusted-LAN only unless you add your own controls in front of it.

Recommended deployment assumptions:

* keep it on a private network
* restrict port `8080` to the Homepage host, VPN clients, or your local subnet
* do not expose it directly to the public Internet
* place it behind a reverse proxy with authentication if wider access is required

Current implementation notes:

* `virsh` is invoked with `--readonly`
* the API currently returns backend error details on failure
* the API currently has no explicit subprocess timeout

The last two points are acceptable tradeoffs for a simple homelab widget, but they are not ideal for a hardened deployment.


## Run the API manually

Start the API on the KVM host:

```bash
python3 kvm_api.py
```

Verify locally:

```bash
curl http://127.0.0.1:8080/api/kvm
curl http://127.0.0.1:8080/healthz
```

## Configure systemd

Create a unit file:

```bash
sudo tee /etc/systemd/system/kvm-api.service >/dev/null <<'EOF'
[Unit]
Description=Homepage KVM API
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=<service-user>
WorkingDirectory=/opt/kvm-api
ExecStart=/usr/bin/python3 /opt/kvm-api/kvm_api.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
```

Replace:

* `<service-user>` with the user that should run the API

If needed, create the working directory and place `kvm_api.py` there:

```bash
sudo mkdir -p /opt/kvm-api
sudo cp kvm_api.py /opt/kvm-api/kvm_api.py
sudo chown -R <service-user>:<service-group> /opt/kvm-api
```

Reload systemd and enable the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now kvm-api.service
```

Check status:

```bash
systemctl status kvm-api.service
```

View logs:

```bash
journalctl -u kvm-api.service -f
```

## Verify the service

Test the API after the service is running:

```bash
curl http://127.0.0.1:8080/api/kvm
curl http://127.0.0.1:8080/healthz
```

## Homepage configuration

Example `services.yaml` entry:

```yaml
- KVM Host:
    icon: https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/png/redhat-linux.png
    href: https://<cockpit-host>:9090/machines
    siteMonitor: http://<kvm-api-host>:8080/healthz
    widget:
      type: customapi
      url: http://<kvm-api-host>:8080/api/kvm
      refreshInterval: 10000
      mappings:
        - field: vms
          label: VMs
        - field: resources.cpu
          label: CPU
          format: percent
        - field: resources.mem
          label: Mem
          format: percent
```

## Network access

If Homepage is running on a different server, the API must be reachable remotely.

Useful checks on the KVM host:

```bash
ss -tulpn | grep 8080
curl http://127.0.0.1:8080/healthz
curl http://<kvm-api-host>:8080/healthz
```

Useful check from the Homepage server:

```bash
curl http://<kvm-api-host>:8080/healthz
```

If needed, open the port in `firewalld`:

```bash
sudo firewall-cmd --add-port=8080/tcp --permanent
sudo firewall-cmd --reload
```

Or restrict access to the Homepage server or local subnet with a more specific rule.

This is the preferred model for this project: expose the service only where Homepage or other trusted clients need it.

## Summary

At the end of the setup you should have:

* a Python API running on the libvirt host
* `virsh` using `qemu:///system` in read-only mode
* a `systemd` service keeping the API alive
* Homepage reading `vms`, `resources.cpu`, and `resources.mem` through `customapi`
* Cockpit available as the click-through UI for deeper VM management
