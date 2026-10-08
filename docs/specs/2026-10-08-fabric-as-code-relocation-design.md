# Fabric-as-code relocation - design

Goal: move the fabric-as-code (Terraform underlay, Ansible overlay, Cilium BGP
config) from the operational substrate repo into this repo, behind a small
substrate seam, so this repo is the complete, portable, teachable fabric build.
The operational repo becomes substrate that runs this automation from a sibling
checkout.

See ADR `docs/decisions/0002-fabric-as-code-lives-here.md` for why.

## What moves, what stays

| Moves here (portable fabric-as-code) | Stays in the operational repo (substrate) |
|---|---|
| `terraform/` - netascode `nac-nxos` data model, `main.tf`, vars, tool pins | the lab topology (one realization of the fabric) |
| `ansible/` - `overlay.yml`, templates, `group_vars`, `host_vars`, example inventory | bring-up / teardown / import scripts |
| `cilium/bgp.yaml` - Cilium BGP CRDs (reference design) | `setup-node-peering.sh` - macvlan, host routes, egress SNAT, cilium-config patch |
|  | the real six management endpoints + credentials |

Not moved, not committed anywhere (gitignored, regenerate): vendored Ansible
collections, the Python venv, Terraform state, `.rendered/` output.

## The seam

Only six values are environment-specific: the device management endpoints. The
password is already environment-only. So:

- The six endpoints have a **single source**, each via its tool's native
  override. Terraform: this relocation adds a `switch_urls` map variable (device
  name to URL); `main.tf` reads the committed reference data model, injects each
  device's URL from the variable, and passes the result to the `nac-nxos`
  module's inline `model` input. The committed data model carries no `url:`, so
  it is purely the reference design, and no files are generated. Ansible: the
  endpoints are the `ansible_host` fields of an inventory.
- This repo commits **one example of each, not per-environment variants**:
  `terraform.tfvars.example`, and a committed `inventory.yml` whose hosts are
  placeholders (`spine1.fabric.example`, ...) that doubles as the reference. The
  operator supplies the real six through a gitignored `terraform.tfvars` (real
  `switch_urls`, auto-loaded by Terraform) and their own inventory passed with
  `-i`. The old on-net/forwarded `*.forward.*` twins are dropped: on-net vs
  SSH-forwarded is just different values the operator supplies.
- Credentials come from the environment: `TF_VAR_switch_password` for Terraform
  and the httpapi password for Ansible. Never a file.

This adds one small Terraform variable (`switch_urls`) and a merge in `main.tf`;
everything else reuses each tool's native override (Terraform's auto-loaded
`terraform.tfvars`, Ansible's `-i`), and deletes the duplicated `*.forward.*`
variants rather than relocating them. The old `terraform.tfvars.example` already
documents a `switch_urls` block that was never implemented; this relocation makes
that variable real and corrects the example.

## Layout here after the move

```
BRKDCN-2982/
  terraform/            underlay: data model (reference design), main.tf, vars,
                        .terraform-version, .terraform.lock.hcl,
                        terraform.tfvars.example   (real terraform.tfvars gitignored)
  ansible/              overlay.yml, templates/, group_vars/, host_vars/,
                        inventory.yml              (placeholder hosts; operator overrides with -i)
  cilium/
    bgp.yaml            Cilium BGP CRDs (reference design)
  gitops/               (already here) Argo CD bootstrap + apps
  docs/                 decisions, specs, plans
```

## Invocation from the operational repo

The operational repo references this repo as a sibling checkout through a single
path variable (for example `FABRIC_REPO=../BRKDCN-2982`) and runs the automation
against it, supplying the real endpoints and credentials it holds:

```
terraform -chdir="$FABRIC_REPO/terraform" apply       # with the gitignored tfvars + TF_VAR_switch_password
ansible-playbook -i <operator inventory> "$FABRIC_REPO/ansible/overlay.yml"
```

`setup-node-peering.sh` (staying in the operational repo) applies
`"$FABRIC_REPO/cilium/bgp.yaml"` from the sibling checkout.

## Migration mechanics

One coordinated change across both repos:

1. Copy the `terraform/`, `ansible/`, and `cilium/bgp.yaml` sources into this
   repo. Drop the `*.forward.*` twins. Add the `switch_urls` variable and the
   `model`-merge in `main.tf`, strip inline `url:` from the committed data model,
   and correct `terraform.tfvars.example` to the now-real `switch_urls`. Set the
   committed `inventory.yml` hosts to placeholders. Extend `.gitignore` here for
   the real `terraform.tfvars`, collections, venv, state, and `.rendered/` — there
   is no gitignored real inventory in the repo, the operator passes theirs with
   `-i`.
2. In the operational repo, remove the relocated sources and leave a
   sibling-path pointer plus the gitignored real endpoint files; update the
   bring-up scripts and `setup-node-peering.sh` to run the automation from
   `$FABRIC_REPO`.

History is not rewritten; the files are added here fresh and removed there.

## Testing and success criteria

- From the operational side, `terraform -chdir=$FABRIC_REPO/terraform plan`
  against the live fabric shows **no changes** (the relocated config is identical
  to what is deployed).
- `ansible-playbook ... --check` reports no unexpected changes.
- The operational repo's pyATS verification still passes against the running
  fabric.
- A clean checkout of this repo plus the operator override reproduces the fabric
  with no files living in the operational repo except substrate and the override.
- No secret, credential, or real reachable endpoint appears in this repo.

## Out of scope

The self-hosted GitHub runner / fabric CI lane, the Hubble→OTel→Splunk telemetry
bridge, and any app beyond the GitOps demo. Each is its own later slice.
