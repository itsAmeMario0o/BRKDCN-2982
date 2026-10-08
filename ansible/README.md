# Overlay leg: l2vpn evpn + VXLAN, device-direct

Ansible builds the EVPN overlay on top of the Terraform underlay. It is
device-direct over NX-API (no NDFC, no Nexus Dashboard). netascode's own VXLAN
Ansible collection (`cisco.nac_dc_vxlan`) is NDFC-only, so it does not fit the
no-controller rule; this leg uses Cisco's device-direct collection
(`cisco.nxos`) driven from a YAML data model.

## What it builds

A symmetric IRB fabric for two tenant subnets:

- Tenant VRF `tenant1` with L3 VNI 50000.
- `red` (VLAN 100, L2 VNI 10100, 10.0.100.0/24) on leaf1.
- `blue` (VLAN 200, L2 VNI 10200, 10.0.200.0/24) on leaf2.
- Distributed anycast gateways (`.1` in each subnet), so red and blue route to
  each other across the fabric over the L3 VNI.
- Spines as EVPN route-reflectors: `retain route-target all`. The whole fabric
  is one AS (65400, single-AS BRKDCN-2982 model), so there are no eBGP knobs.

## Layout

| Path | Role |
|---|---|
| `ansible.cfg` | Repo-local collections path, NX-API connection defaults. |
| `inventory.yml` | The six switches as placeholder hosts; override with `-i`. |
| `group_vars/all.yml` | The overlay data model: VRF, VNIs, anycast MAC, BGP. |
| `host_vars/leafN.yml` | Which segment and host ports each leaf serves. |
| `templates/overlay_leaf.j2`, `overlay_spine.j2` | Render the data model to NX-OS. |
| `overlay.yml` | The playbook: render, then push with `nxos_config`. |

Local-only, git-excluded: `.venv/`, `collections/`, `.rendered/`.

## Running

```
export NXOS_USERNAME=admin NXOS_PASSWORD=...     # creds from the env, never a file
source .venv/bin/activate                        # ansible-core + cisco.nxos

ansible-playbook -i <your inventory> overlay.yml           # apply
ansible-playbook -i <your inventory> overlay.yml --check   # preview
```

Run the Terraform underlay first; the overlay's loopback-to-loopback BGP
sessions need fabric-wide loopback reachability, which the underlay provides.

## Verifying

```
show bgp l2vpn evpn summary     # overlay sessions to the spines, established
show nve peers                  # VTEP-to-VTEP, leaf1 sees leaf2
show l2route evpn mac all       # learned host MACs
# end to end: red-endpoint (10.0.100.10) pings blue-endpoint (10.0.200.10)
```

## A note on the BGP seam

Both legs touch `router bgp`: Terraform owns the underlay neighbors (the
point-to-point sessions, ipv4 unicast), Ansible owns the overlay neighbors
(loopback to loopback, l2vpn evpn) and the tenant VRF address family. They
manage disjoint neighbors, so they coexist, but it is the one place the two
tools overlap. Re-running one leg does not disturb the other's neighbors.
