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

- The data model (`terraform/*.nac.yaml`) and the Ansible inventory are committed
  here as the **reference design**, with the six endpoints as **example values**
  (placeholder hosts such as `https://spine1.fabric.example`).
- Terraform already exposes the endpoints as the `switch_urls` variable. The
  operator supplies the real six through a gitignored `terraform.tfvars` and an
  operator-supplied Ansible inventory. This repo ships `terraform.tfvars.example`
  and `inventory.example.yml`; the real `terraform.tfvars` and `inventory.yml`
  are gitignored.
- Credentials come from the environment: `TF_VAR_switch_password` for Terraform
  and the httpapi password for Ansible. Never a file.

This is the example-plus-gitignored-override pattern the automation already uses,
carried across the move.

## Layout here after the move

```
BRKDCN-2982/
  terraform/            underlay: data model (reference design), main.tf, vars,
                        .terraform-version, .terraform.lock.hcl,
                        terraform.tfvars.example   (real terraform.tfvars gitignored)
  ansible/              overlay.yml, templates/, group_vars/, host_vars/,
                        inventory.example.yml      (real inventory.yml gitignored)
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
   repo; rename the committed data model / inventory to carry **example**
   endpoints and add `.example` copies of tfvars/inventory; extend `.gitignore`
   here for the real `terraform.tfvars`, real `inventory.yml`, collections, venv,
   state, and `.rendered/`.
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
