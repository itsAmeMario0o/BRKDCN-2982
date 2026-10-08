# VXLAN EVPN underlay as code

The NX-OS single-AS VXLAN BGP EVPN underlay, built from a netascode `nac-nxos`
data model. Terraform owns bring-up and the BGP underlay (features, loopbacks,
the point-to-point links, and the iBGP sessions that carry loopback
reachability). The `l2vpn evpn` overlay and VXLAN are the Ansible leg
(`../ansible`); the Cilium BGP peering is `../cilium/bgp.yaml`.

Design: `docs/decisions/0002-fabric-as-code-lives-here.md` and the spec beside
it.

## The design, in one paragraph

One AS for the whole fabric (`65400`). The underlay is iBGP over the
point-to-point links with the spines as route-reflectors, which bootstraps
loopback reachability with no OSPF or IS-IS. The spines also advertise their
connected P2P `/31`s so a leaf can resolve another leaf's loopback next hop.
Because it is a single AS there are no eBGP knobs: no `allowas-in`, no
`disable-peer-as-check`, no next-hop route-map. The Kubernetes/Cilium cluster is
its own AS (`65001`) and peers the leaves over eBGP (BRKDCN-2982
"AS-per-cluster"), which is what lets a leaf re-originate pod routes as EVPN
Type-5.

## How it connects

The `nac-nxos` module owns the `nxos` provider. The committed data model
(`underlay.nac.yaml`) is the reference design and carries **no** device `url`.
The six NX-API endpoints come from the `switch_urls` variable; `main.tf` injects
each device's URL and passes the result to the module's inline `model` input.
Credentials come from the `NXOS_USERNAME` and `NXOS_PASSWORD` environment
variables, so there is no provider block and no password variable. `feature
nxapi` is a day-0 bootstrap on each switch (not managed here), because without
it the provider cannot connect at all.

## Running it

```
export NXOS_USERNAME=admin
export NXOS_PASSWORD=...                 # never put this in a file
cp terraform.tfvars.example terraform.tfvars   # fill in the real switch_urls (gitignored)
terraform init
terraform plan
terraform apply
```

`switch_urls` is a map of device name to NX-API URL. Point it at the switch
management addresses, or at SSH-forwarded localhost ports when driving the
fabric from a workstation. `managed_devices` narrows an apply to stage one
switch first (for example `["leaf1"]`).

## Files

- `versions.tf` - Terraform (>= 1.9) and provider requirements, local backend.
- `.terraform-version` - pins this folder to 1.9.8 via tfenv (the module needs a
  provider function from Terraform 1.9).
- `variables.tf` - `switch_urls` (required) and `managed_devices`. Credentials
  come from the environment, not a variable.
- `main.tf` - reads the data model, injects `switch_urls`, calls the
  `netascode/nac-nxos/nxos` module with the merged `model`.
- `underlay.nac.yaml` - the data model: features, loopbacks, point-to-point
  links, and the single-AS iBGP underlay for all six switches (no `url`).
- `terraform.tfvars.example` - a template for the real `switch_urls`.

## State and credentials

State is local (`terraform.tfstate`, gitignored). Never commit state, a real
credential, or a real endpoint. Supply `switch_urls` through the gitignored
`terraform.tfvars` and the password through `NXOS_PASSWORD` in the environment.
