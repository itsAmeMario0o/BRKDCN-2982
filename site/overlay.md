---
layout: default
title: The overlay and vPC
permalink: /overlay/
eyebrow: Build
summary: Ansible lays the l2vpn evpn overlay on top of the underlay, device-direct over NX-API, with a tenant VRF, anycast gateways, and a vPC leaf pair.
---

## What this leg builds

Ansible builds the EVPN overlay on top of the Terraform underlay. It runs device-direct over NX-API, with no NDFC and no Nexus Dashboard. netascode's own VXLAN Ansible collection is NDFC-only, so it does not fit the no-controller rule here. This leg uses Cisco's device-direct collection (`cisco.nxos`) driven from a YAML data model.

The result is a symmetric IRB fabric for two tenant subnets:

- Tenant VRF `tenant1` with L3 VNI 50000.
- `red` on leaf1: VLAN 100, L2 VNI 10100, 10.0.100.0/24.
- `blue` on leaf2: VLAN 200, L2 VNI 10200, 10.0.200.0/24.
- Distributed anycast gateways (the `.1` in each subnet), so `red` and `blue` route to each other across the fabric over the L3 VNI.
- Spines as EVPN route-reflectors with `retain route-target all`. The fabric is one AS (65400), so there are no eBGP knobs.

## The vPC leaf pair

Two of the leaves carry both segments as distributed anycast and form a vPC pair. Because they share an anycast tunnel endpoint address, the rest of the fabric sees the pair as one next hop. A host dual-homed to the pair, or an endpoint that attaches to either member later, is reachable whichever leaf forwards the traffic. A leaf can also carry both `red` and `blue` as anycast without owning a local endpoint yet, so a host can plug in later with nothing else to change.

## Layout

| Path | Role |
|---|---|
| `ansible.cfg` | Repo-local collections path, NX-API connection defaults. |
| `inventory.yml` | The six switches as placeholder hosts; override with `-i`. |
| `group_vars/all.yml` | The overlay data model: VRF, VNIs, anycast MAC, BGP. |
| `host_vars/leafN.yml` | Which segment and host ports each leaf serves. |
| `templates/overlay_leaf.j2`, `overlay_spine.j2` | Render the data model to NX-OS. |
| `overlay.yml` | The playbook: render, then push with `nxos_config`. |

Local-only and git-excluded: `.venv/`, `collections/`, `.rendered/`.

## Running

Run the underlay first. The overlay's loopback-to-loopback EVPN sessions need fabric-wide loopback reachability, which the underlay provides.

```bash
export NXOS_USERNAME=admin NXOS_PASSWORD=...     # creds from the env, never a file
source .venv/bin/activate                        # ansible-core + cisco.nxos

ansible-playbook -i <your inventory> overlay.yml           # apply
ansible-playbook -i <your inventory> overlay.yml --check   # preview
```

## Verifying

```
show bgp l2vpn evpn summary     # overlay sessions to the spines, established
show nve peers                  # VTEP-to-VTEP, leaf1 sees leaf2
show l2route evpn mac all       # learned host MACs
# end to end: a red endpoint (10.0.100.10) pings a blue endpoint (10.0.200.10)
```

A successful `red`-to-`blue` ping is the proof that symmetric IRB is working: the two hosts sit in different subnets on different leaves, and the traffic routes over the L3 VNI rather than bridging.

<div class="callout">
<strong>The BGP seam, again.</strong>
Terraform owns the underlay neighbors; Ansible owns the overlay neighbors (loopback to loopback, <code>l2vpn evpn</code>) and the tenant VRF address family. They manage disjoint neighbors, so they coexist on the same <code>router bgp</code> and neither disturbs the other on a re-run. It is the one place the two tools overlap, and it is worth knowing before you touch either.
</div>

Source: [`ansible/`](https://github.com/{{ site.repo.owner }}/{{ site.repo.name }}/tree/{{ site.repo.branch }}/ansible).
