# Cilium EVPN fabric as code

The NX-OS VXLAN BGP EVPN fabric for the `cilium-evpn-blank` lab, built as
code. This is Slice 1 of the Cilium automation work; the design is in
`docs/specs/2026-09-30-cilium-evpn-fabric-as-code-design.md`.

## Two rules that shape this folder

- **Decoupled.** This is an independent Terraform project. It shares nothing
  with the lab-environment Terraform (`terraform/bootstrap`,
  `terraform/persistent`, `terraform/ad`, `vendor/cloud-cml`). Those build
  the CML VM and make the switches exist; this project treats the switches
  purely as targets.
- **Local state.** The backend is local: `terraform.tfstate` lives in this
  folder and is gitignored (`*.tfstate*`). No remote or Azure blob backend,
  so a full rebuild is self-contained on this machine.

## The design, in one paragraph

Spines share AS 65500; the leaves and the Cilium/Kubernetes nodes share AS
65501. The underlay is eBGP (no OSPF/IS-IS), the overlay is eBGP `l2vpn
evpn` on separate loopback-to-loopback sessions. The spines act as EVPN
route-servers (`retain route-target all`, `set ip next-hop unchanged`), and
the shared leaf AS needs `allowas-in` on the leaves and
`disable-peer-as-check` on the spines. Cilium peers the leaves over iBGP
(same AS). This is the BRKDCN-2982 "eBGP two-AS" EVPN design; see the spec.

## Status: eBGP underlay applied and proven

Terraform owns bring-up and the eBGP underlay. That is built and verified on
the real switches: all eight leaf-spine sessions establish, every switch
learns every loopback fabric-wide, and VTEP-to-VTEP pings cross the fabric
with no loss. A re-plan shows no changes. The `l2vpn evpn` overlay and VXLAN
are the next slice and run from Ansible (`nac-vxlan`), not this root.

### How it connects

The nac-nxos module owns the `nxos` provider: it builds the connection list
from the `url` of each device in the data model and reads credentials from
the `NXOS_USERNAME` and `NXOS_PASSWORD` environment variables. So this root
has no provider block and no password variable. `feature nxapi` is a day-0
bootstrap on the switch (`labs/cilium-evpn-fabric/cilium-evpn-blank.yaml`), not managed here,
because without it the provider cannot connect at all.

### Running it

```
export NXOS_USERNAME=admin
export NXOS_PASSWORD="$LAB_PASSWORD"   # from config/mcp-env/labs.env
terraform init
terraform plan
terraform apply
```

A runner inside the lab reaches the switches at their on-net addresses
(`underlay.nac.yaml`, the committed default). To drive the fabric from the
Mac, open SSH forwards through the CML host and point `yaml_files` at a
forward variant whose URLs are the forwarded localhost ports. See
`terraform.tfvars.example`.

## Files

- `versions.tf`   - Terraform (>= 1.9) and provider requirements, local backend.
- `.terraform-version` - pins this folder to 1.9.8 via tfenv (the module needs
  a provider function from Terraform 1.9).
- `variables.tf`  - `yaml_files` and `managed_devices`. Credentials come from
  the environment, not a variable.
- `main.tf`       - the `netascode/nac-nxos/nxos` module call.
- `underlay.nac.yaml` - the data model: features, loopbacks, L3 point-to-point
  links, and the eBGP underlay for all six switches.
- `terraform.tfvars.example` - the Mac SSH-forward override and staging notes.

## Credentials

The switches use the lab password. Supply it as `NXOS_PASSWORD` from
`LAB_PASSWORD` in `config/mcp-env/labs.env`, the same secret the topology
renders into the switches. Never commit a real credential.
