---
layout: default
title: The underlay
permalink: /underlay/
eyebrow: Build
summary: Terraform brings the switches up and builds the single-AS iBGP underlay that carries loopback reachability, with no IGP in sight.
---

## What this leg owns

Terraform builds the underlay from a netascode `nac-nxos` data model. It owns bring-up and the BGP underlay: the features, the loopbacks, the point-to-point links, and the iBGP sessions that make every switch loopback reachable from every other. The `l2vpn evpn` overlay and VXLAN are the [Ansible leg]({{ '/overlay/' | relative_url }}); the Cilium peering is [its own page]({{ '/cilium-bgp/' | relative_url }}).

## The design, in one paragraph

One AS for the whole fabric (65400). The underlay is iBGP over the point-to-point links with the spines as route-reflectors, which bootstraps loopback reachability with no OSPF or IS-IS. The spines also advertise their connected `/31` networks so a leaf can resolve another leaf's loopback next hop. Because it is a single AS, there are no eBGP knobs: no `allowas-in`, no `disable-peer-as-check`, no next-hop route-map. The cluster is its own AS (65001) and peers the leaves over eBGP, which is what lets a leaf re-originate pod routes as EVPN Type-5.

## How it connects

The `nac-nxos` module owns the `nxos` provider. The committed data model, `underlay.nac.yaml`, is the reference design and carries no device `url`. The six NX-API endpoints come from the `switch_urls` variable, and `main.tf` injects each device's URL before passing the merged model to the module. Credentials come from the `NXOS_USERNAME` and `NXOS_PASSWORD` environment variables, so there is no provider block and no password variable anywhere in the code.

<div class="callout callout-warning">
<strong>One day-0 prerequisite.</strong>
<code>feature nxapi</code> has to be on each switch before Terraform can connect at all. It is a bootstrap step on the device, not something this leg manages, because without it the provider cannot reach the box.
</div>

## Running it

Credentials come from the environment, never a file. The real endpoints go in a gitignored `terraform.tfvars`.

```bash
export NXOS_USERNAME=admin
export NXOS_PASSWORD=...                        # never put this in a file
cp terraform.tfvars.example terraform.tfvars    # fill in real switch_urls (gitignored)
terraform init
terraform plan
terraform apply
```

`switch_urls` is a map of device name to NX-API URL. Point it at the switch management addresses, or at forwarded localhost ports when you drive the fabric from a workstation. `managed_devices` narrows an apply to stage one switch first, for example `["leaf1"]`.

## What is in the folder

| Path | Role |
|---|---|
| `versions.tf` | Terraform (>= 1.9) and provider requirements, local backend. |
| `.terraform-version` | Pins the folder to 1.9.8 via tfenv; the module needs a provider function from Terraform 1.9. |
| `variables.tf` | `switch_urls` (required) and `managed_devices`. Credentials come from the environment, not a variable. |
| `main.tf` | Reads the data model, injects `switch_urls`, calls the `netascode/nac-nxos/nxos` module with the merged model. |
| `underlay.nac.yaml` | The data model: features, loopbacks, point-to-point links, and the single-AS iBGP underlay for all six switches (no `url`). |
| `terraform.tfvars.example` | A template for the real `switch_urls`. |

## Verifying

After the apply, the loopbacks should be reachable fabric-wide and the underlay sessions up:

```
show bgp ipv4 unicast summary      # underlay sessions to the spines, established
show ip bgp neighbors              # the P2P sessions and reflected loopbacks
show ip route 10.0.0.0/24          # every leaf and spine loopback resolvable
```

Loopback-to-loopback reachability is the whole point of this leg. The overlay's EVPN sessions run loopback to loopback, so they cannot come up until the underlay has carried those loopbacks everywhere.

<div class="callout">
<strong>The BGP seam.</strong>
Both legs touch <code>router bgp</code>. Terraform owns the underlay neighbors (the point-to-point sessions, IPv4 unicast); Ansible owns the overlay neighbors (loopback to loopback, <code>l2vpn evpn</code>) and the tenant VRF address family. They manage disjoint neighbors, so re-running one leg does not disturb the other.
</div>

## State and credentials

State is local (`terraform.tfstate`, gitignored). Never commit state, a real credential, or a real endpoint. Supply `switch_urls` through the gitignored `terraform.tfvars` and the password through `NXOS_PASSWORD` in the environment.

Source: [`terraform/`](https://github.com/{{ site.repo.owner }}/{{ site.repo.name }}/tree/{{ site.repo.branch }}/terraform) and ADR [0002]({{ '/decisions/' | relative_url }}).
