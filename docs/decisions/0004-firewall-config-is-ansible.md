# 0004 - The border firewall is configured with Ansible, not Terraform

Status: accepted
Date: 2026-10-23

## Context

ADR 0002 put the fabric-as-code in this repo, and the fabric is all Terraform:
the underlay, vPC, the VXLAN EVPN overlay, and the leaf side of the border seam
(the eBGP to the firewall and the two point-to-point links). ADR 0003 and its
later note record the overlay moving off Ansible and onto Terraform, so the
Nexus fabric is a single toolchain.

The border firewall is the one piece that Terraform cannot reach. It is a
different platform. The one Terraform provider that targets it,
`CiscoDevNet/ciscoasa`, drives the firewall over an API the vendor has frozen
(supported only through older releases, no longer developed), and even then it
covers network objects, ACLs, and static routes, not BGP or NAT. The firewall's
job here is exactly BGP and egress NAT, so that provider cannot express it.

## Decision

Configure the firewall with Ansible, over SSH, using the `cisco.asa` collection.
It lives in `ansible/` next to the Terraform.

This does not walk back ADR 0003. The Nexus fabric stays Terraform-only. Ansible
comes back scoped to the firewall alone, because it is a platform Terraform has
no working path to. Two tools, split by platform, not by layer.

## Consequences

- A second toolchain, kept deliberately narrow: one playbook for one device.
- Ansible drives the firewall over SSH and cannot build its own way in, so the
  firewall needs a day-0 management bootstrap (a login user, aaa, ssh, host
  keys) before the playbook can run. That bootstrap is recorded in
  `ansible/firewall-bootstrap.txt`, not managed by the playbook.
- The playbook is held to the same prove-it bar as the Terraform: a matching run
  reports no change, a drifted run restores the config and then reports no
  change.
