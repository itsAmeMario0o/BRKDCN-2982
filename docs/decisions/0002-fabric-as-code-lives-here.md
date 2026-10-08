# 0002 - The fabric-as-code lives in this repo; the lab is substrate

Status: accepted
Date: 2026-10-08

## Context

ADR 0001 made this repo the source of truth for the GitOps pipeline. The rest of
the fabric-as-code (the NX-OS VXLAN EVPN underlay in Terraform, the EVPN overlay
in Ansible, and the Cilium BGP config) still lived in the operational substrate
repo that provisions the lab. That split is now the thing holding the teaching
repo back: the automation that actually builds the fabric, and teaches it, is
the part people want to read and run, and it belongs with the GitOps pipeline,
not in the disposable environment repo.

The one real obstacle is that the automation needs to know six device management
endpoints and a password, and this repo is public. Everything else in the data
model (loopbacks, point-to-point `/31`s, the single-AS BGP, the VNIs) is the
reference design and is safe, and wanted, in the open.

## Decision

The Terraform underlay, the Ansible overlay, and `cilium/bgp.yaml` move into this
repo and sit beside `gitops/`. This repo becomes the complete, portable
fabric-as-code: readable and runnable on its own against any fabric that matches
the design, not only the one lab.

The operational repo keeps only substrate and lab glue: the lab topology, the
bring-up and teardown scripts, `setup-node-peering.sh` (macvlan, host routes, the
egress SNAT, the Cilium config patch), and the real six management endpoints plus
credentials. It runs this repo's automation from a sibling checkout.

The seam is deliberately small, because only six values are environment-specific:

- The data model and inventory are committed here as the **reference design**,
  with the six management endpoints as **example values** (placeholder hosts).
- The real six endpoints come from a gitignored operator override (Terraform's
  existing `switch_urls` variable via a gitignored tfvars, and an Ansible
  inventory supplied by the operator). Credentials come from the environment
  (`TF_VAR_switch_password` / the Ansible httpapi password), never a file.

This reuses the example-plus-gitignored-override pattern the automation already
uses; it is not a new mechanism.

## Consequences

- The public repo holds the whole fabric build end to end, teachable without the
  lab. It still contains no secrets and no real reachable endpoints.
- A rebuild runs this repo's Terraform and Ansible from the operational side,
  which supplies the six endpoints and the password at invocation time.
- Vendored Ansible collections, the Python venv, and Terraform state stay
  gitignored and regenerate; they do not move.
- `setup-node-peering.sh` stays in the operational repo. It is lab glue (it only
  exists because of the kind host's networking), and it references
  `cilium/bgp.yaml` from the sibling checkout.
- The relocation touches both repos in one coordinated change: files are added
  here and removed from the operational repo, which keeps a sibling-path pointer
  instead.

## Alternatives considered

- Keep the fabric-as-code in the operational repo. Rejected: that repo is
  disposable and environment-specific; it is the wrong home for the durable
  teaching artifact (the same reasoning as ADR 0001).
- Generate the endpoints from the lab topology. Rejected: a generator for a
  six-line list that changes almost never is far more machinery than the problem
  warrants.
- Pass the real data model and inventory as file-path arguments so nothing real
  ever enters the checkout. Rejected as unnecessary: the environment-specific
  surface is six RFC1918 endpoints, not secrets, and the gitignored-override
  pattern already exists and is proven.
