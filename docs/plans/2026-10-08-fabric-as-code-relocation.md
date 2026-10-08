# Fabric-as-code Relocation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the Terraform underlay, Ansible overlay, and Cilium BGP config from the operational repo into this repo, behind a `switch_urls`-variable seam, so this repo is the complete, portable fabric-as-code.

**Architecture:** This repo gains `terraform/`, `ansible/`, `cilium/` beside `gitops/`. The six device endpoints become a `switch_urls` map variable injected into the `nac-nxos` module's inline `model` input; the committed data model carries no `url:`. The operational repo keeps substrate (`setup-node-peering.sh`, topology, scripts) and supplies the real endpoints (gitignored `terraform.tfvars`) and credentials (env), running this automation from a sibling checkout.

**Tech Stack:** Terraform (netascode `nac-nxos` ~> 0.3.0), Ansible (`cisco.nxos` over httpapi), kubectl/Cilium. Two git repos: this one (public `itsAmeMario0o/BRKDCN-2982`) and the operational substrate repo (`$OPS_REPO`).

## Global Constraints

- Public repo: no secrets, no real reachable endpoints, no lab-identifying names. Example/placeholder values only.
- Single endpoint source: the six URLs come only from `switch_urls` (Terraform) and inventory `ansible_host` (Ansible). The committed data model has no `url:`.
- Credentials from env only: `NXOS_USERNAME`/`NXOS_PASSWORD` (Terraform module provider) and the Ansible httpapi password. Never a file.
- Delete, don't relocate, the `*.forward.*` twins.
- Gitignored, regenerate, do not commit: real `terraform.tfvars`, `*.tfstate*`, `.terraform/`, `ansible/collections/`, `ansible/.rendered/`, any venv.
- No history rewrite. Files are added here and removed from the operational repo.
- Source paths below (abbreviated `NAC/`) are the `nac/` fabric-as-code directory in the operational repo.

---

### Task 1: Terraform leg — reference design + `switch_urls` model merge

**Files:**
- Create: `terraform/main.tf`, `terraform/variables.tf`, `terraform/versions.tf`, `terraform/README.md`, `terraform/.terraform-version`, `terraform/.terraform.lock.hcl`, `terraform/underlay.nac.yaml`, `terraform/terraform.tfvars.example`
- Source: copy from `NAC/terraform/` (do NOT copy `underlay.forward.nac.yaml`, `terraform.tfvars`, `.terraform/`, `*.tfstate*`)

**Interfaces:**
- Produces: a Terraform root whose only required input is `var.switch_urls` (map, device name -> URL); creds via `NXOS_USERNAME`/`NXOS_PASSWORD`. Task 5 runs `plan` against it.

- [ ] **Step 1: Copy the Terraform sources**

```bash
mkdir -p terraform
cp NAC/terraform/{versions.tf,README.md,.terraform-version,.terraform.lock.hcl,underlay.nac.yaml} terraform/
# main.tf, variables.tf, terraform.tfvars.example are rewritten below, not copied.
```

- [ ] **Step 2: Strip the six `url:` lines from the committed data model**

The committed `terraform/underlay.nac.yaml` must carry NO `url:` (it is the reference design; URLs come from `switch_urls`). Remove exactly the six `      url: https://...` lines under each `- name:` device.

```bash
sed -i.bak -E '/^      url: https?:\/\//d' terraform/underlay.nac.yaml && rm terraform/underlay.nac.yaml.bak
grep -c 'url:' terraform/underlay.nac.yaml   # expect 0
```

- [ ] **Step 3: Write `terraform/main.tf` (inline model merge)**

```hcl
# NX-OS single-AS VXLAN BGP EVPN underlay (netascode nac-nxos).
# Design: docs/decisions/0001-gitops-via-argocd.md, 0002-fabric-as-code-lives-here.md.
#
# The data model (underlay.nac.yaml) is the reference design and carries no
# device url. The six NX-API endpoints come from var.switch_urls and are merged
# in here, then passed to the module's inline `model` input. The module reads
# credentials from NXOS_USERNAME / NXOS_PASSWORD in the environment.

locals {
  base = yamldecode(file("${path.module}/underlay.nac.yaml"))
  model = {
    nxos = merge(local.base.nxos, {
      devices = [for d in local.base.nxos.devices : merge(d, { url = var.switch_urls[d.name] })]
    })
  }
}

module "nxos" {
  source  = "netascode/nac-nxos/nxos"
  version = "~> 0.3.0"

  model           = local.model
  managed_devices = var.managed_devices
}
```

- [ ] **Step 4: Write `terraform/variables.tf`**

```hcl
# The nac-nxos module owns the nxos provider and reads credentials from the
# NXOS_USERNAME / NXOS_PASSWORD environment variables, so there is no provider
# block or password variable here. Set, and never put in a file:
#
#   export NXOS_USERNAME=admin
#   export NXOS_PASSWORD="$LAB_PASSWORD"

variable "switch_urls" {
  description = "Per-device NX-API URL, keyed by device name (spine1, spine2, leaf1..leaf4). Supply real values via a gitignored terraform.tfvars; never commit real endpoints."
  type        = map(string)
}

variable "managed_devices" {
  description = "Which switches the apply touches. Defaults to all; narrow it (for example [\"leaf1\"]) to stage a change on one switch first."
  type        = list(string)
  default     = ["spine1", "spine2", "leaf1", "leaf2", "leaf3", "leaf4"]
}
```

- [ ] **Step 5: Write `terraform/terraform.tfvars.example` (corrects the stale one)**

```hcl
# Copy to terraform.tfvars (gitignored) and fill in the real NX-API endpoints.
# Credentials are NOT here; export them:
#   export NXOS_USERNAME=admin NXOS_PASSWORD="$LAB_PASSWORD"
#
# switch_urls values are placeholders. In-lab, point them at the switch
# management addresses; from a workstation, at SSH-forwarded localhost ports.

switch_urls = {
  spine1 = "https://spine1.fabric.example"
  spine2 = "https://spine2.fabric.example"
  leaf1  = "https://leaf1.fabric.example"
  leaf2  = "https://leaf2.fabric.example"
  leaf3  = "https://leaf3.fabric.example"
  leaf4  = "https://leaf4.fabric.example"
}

# managed_devices = ["leaf1"]   # narrow the apply to stage one switch first
```

- [ ] **Step 6: Format and validate**

```bash
terraform -chdir=terraform fmt -check
terraform -chdir=terraform init -backend=false
TF_VAR_switch_urls='{spine1="https://x",spine2="https://x",leaf1="https://x",leaf2="https://x",leaf3="https://x",leaf4="https://x"}' \
  terraform -chdir=terraform validate
```
Expected: `fmt` clean, `validate` reports "Success!". (`init -backend=false` pulls the module without configuring state.)

- [ ] **Step 7: Commit**

```bash
git add terraform/
git commit -m "feat(terraform): relocate underlay; switch_urls -> inline model (no inline urls)"
```

---

### Task 2: Ansible leg — reference overlay + placeholder inventory

**Files:**
- Create: `ansible/ansible.cfg`, `ansible/overlay.yml`, `ansible/inventory.yml`, `ansible/group_vars/all.yml`, `ansible/host_vars/leaf1.yml`, `ansible/host_vars/leaf2.yml`, `ansible/host_vars/leaf3.yml`, `ansible/host_vars/leaf4.yml`, `ansible/templates/overlay_leaf.j2`, `ansible/templates/overlay_spine.j2`, `ansible/README.md`
- Source: copy from `NAC/ansible/` (do NOT copy `inventory.forward.yml`, `collections/`, `.rendered/`, any venv)

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: an Ansible root whose committed `inventory.yml` is placeholders; the operator overrides with `-i`. `ansible.cfg` keeps `inventory = ./inventory.yml`, `collections_paths = ./collections`.

- [ ] **Step 1: Copy the Ansible sources**

```bash
mkdir -p ansible
cp -R NAC/ansible/{ansible.cfg,overlay.yml,README.md,group_vars,host_vars,templates,inventory.yml} ansible/
# inventory.yml is converted to placeholders in Step 2; inventory.forward.yml is NOT copied.
```

- [ ] **Step 2: Convert `ansible/inventory.yml` hosts to placeholders**

Replace every real `ansible_host:` value with a placeholder hostname. The file keeps its spine/leaf group structure; only the addresses change.

```yaml
# ansible/inventory.yml -> the hosts block becomes:
        spine1: {ansible_host: spine1.fabric.example}
        spine2: {ansible_host: spine2.fabric.example}
        leaf1:  {ansible_host: leaf1.fabric.example}
        leaf2:  {ansible_host: leaf2.fabric.example}
        leaf3:  {ansible_host: leaf3.fabric.example}
        leaf4:  {ansible_host: leaf4.fabric.example}
```

Verify no real addresses remain:
```bash
grep -E '192\.168|127\.0\.0\.1|10\.[0-9]' ansible/inventory.yml && echo "FAIL: real address" || echo "OK: placeholders only"
```

- [ ] **Step 3: Confirm the playbook parses (syntax only, no connection)**

```bash
cd ansible && ansible-galaxy collection install -r <(echo "collections: [{name: cisco.nxos}]") -p ./collections >/dev/null 2>&1 || true
ansible-playbook -i inventory.yml overlay.yml --syntax-check ; cd ..
```
Expected: `playbook: overlay.yml` with no syntax error. (Collections install is best-effort for the syntax check; they are gitignored and regenerate on the operator side.)

- [ ] **Step 4: Commit**

```bash
git add ansible/
git commit -m "feat(ansible): relocate EVPN overlay; placeholder inventory (operator overrides with -i)"
```

---

### Task 3: Cilium leg, `.gitignore`, and README

**Files:**
- Create: `cilium/bgp.yaml` (copy of `NAC/cilium/bgp.yaml`), `.gitignore`, update `README.md`
- Do NOT copy `NAC/cilium/setup-node-peering.sh` (stays in the operational repo).

**Interfaces:**
- Produces: `cilium/bgp.yaml` at a stable path the operational `setup-node-peering.sh` references from the sibling checkout (Task 4).

- [ ] **Step 1: Copy the Cilium BGP CRDs**

```bash
mkdir -p cilium
cp NAC/cilium/bgp.yaml cilium/
```

- [ ] **Step 2: Write `.gitignore`**

```gitignore
# Terraform
**/.terraform/
*.tfstate
*.tfstate.*
terraform.tfvars
!terraform.tfvars.example
# Ansible
ansible/collections/
ansible/.rendered/
# Python venvs
**/.venv/
```

- [ ] **Step 3: Confirm nothing real would be committed**

```bash
git add -A --dry-run | grep -E 'terraform.tfvars$|tfstate|collections/|\.rendered/|\.venv/' && echo "FAIL: ignored path staged" || echo "OK: ignores hold"
grep -rniE '192\.168|127\.0\.0\.1|20\.114|password *[:=]|BEGIN (RSA|OPENSSH)' terraform/ ansible/ cilium/ 2>/dev/null | grep -v example || echo "OK: no secrets/real endpoints"
```
Expected: both print `OK`.

- [ ] **Step 4: Update `README.md` "What is here now"**

Add a line under the existing content noting the fabric-as-code now lives here:
```markdown
- `terraform/` - the VXLAN EVPN underlay as a netascode data model. Endpoints
  come from the `switch_urls` variable; credentials from the environment.
- `ansible/` - the EVPN overlay (templates + data model) run device-direct.
- `cilium/bgp.yaml` - the Cilium AS-per-cluster BGP config.
```

- [ ] **Step 5: Commit**

```bash
git add cilium/ .gitignore README.md
git commit -m "feat: relocate cilium/bgp.yaml; add .gitignore and README for the fabric-as-code"
```

---

### Task 4: Operational repo — remove relocated sources, rewire to the sibling

**Files (in the operational repo, `$OPS_REPO`):**
- Remove: `labs/cilium-evpn-fabric/nac/terraform/`, `labs/cilium-evpn-fabric/nac/ansible/`, `labs/cilium-evpn-fabric/nac/cilium/bgp.yaml`
- Modify: `labs/cilium-evpn-fabric/nac/cilium/setup-node-peering.sh`
- Create: `labs/cilium-evpn-fabric/nac/README.md` pointer (replace the old one's body)

**Interfaces:**
- Consumes: the sibling checkout at `$FABRIC_REPO` (default `../BRKDCN-2982`).

- [ ] **Step 1: Remove the relocated sources (operational repo)**

```bash
cd "$OPS_REPO"
git rm -r labs/cilium-evpn-fabric/nac/terraform labs/cilium-evpn-fabric/nac/ansible
git rm labs/cilium-evpn-fabric/nac/cilium/bgp.yaml
```

- [ ] **Step 2: Rewire `setup-node-peering.sh` to the sibling `bgp.yaml`**

It currently does `cd "$(dirname "$0")"` then `kubectl apply -f bgp.yaml`. The script runs on the kind host, which already clones this repo at `~/BRKDCN-2982` (the Argo bootstrap). Change the apply to reference that checkout:

```sh
# was: kubectl apply -f bgp.yaml
kubectl apply -f "${FABRIC_REPO:-$HOME/BRKDCN-2982}/cilium/bgp.yaml"
```

Validate: `bash -n setup-node-peering.sh && shellcheck setup-node-peering.sh` (clean).

- [ ] **Step 3: Replace `NAC/README.md` body with a pointer**

```markdown
# Fabric-as-code moved

The Terraform underlay, Ansible overlay, and `cilium/bgp.yaml` now live in the
portable repo **BRKDCN-2982** (a sibling checkout, `FABRIC_REPO=../BRKDCN-2982`).
This directory keeps only lab glue: `cilium/setup-node-peering.sh`, plus the
operator's gitignored real endpoints (`terraform.tfvars`) and inventory.

Run the fabric from the sibling checkout:

    export NXOS_USERNAME=admin NXOS_PASSWORD="$LAB_PASSWORD"
    terraform -chdir="$FABRIC_REPO/terraform" apply      # switch_urls from your gitignored terraform.tfvars
    ansible-playbook -i <your inventory> "$FABRIC_REPO/ansible/overlay.yml"
```

- [ ] **Step 4: Keep the operator's real values on this side (gitignored)**

The real `terraform.tfvars` (real `switch_urls`) and the real Ansible inventory
live under the operator's control and are gitignored. Confirm the operational repo's
`.gitignore` still covers `*.tfvars` (it does) and add an ignore for the operator
inventory if it is kept in-repo. No real endpoints are committed.

- [ ] **Step 5: Commit (operational repo)**

```bash
git add -A labs/cilium-evpn-fabric/nac
git commit -m "refactor(fabric): relocate fabric-as-code to BRKDCN-2982; keep lab glue + sibling pointer"
```

---

### Task 5: Verify end to end (the gate)

**Files:** none. Runs from the operational side against the live fabric.

**Interfaces:**
- Consumes: Tasks 1-4, a reachable fabric, the operator's real `terraform.tfvars` + inventory + `NXOS_*` env.

- [ ] **Step 1: Terraform plan is a no-op (config identical to deployed)**

```bash
export NXOS_USERNAME=admin NXOS_PASSWORD="$LAB_PASSWORD"
cp <operator>/terraform.tfvars "$FABRIC_REPO/terraform/terraform.tfvars"   # gitignored there
terraform -chdir="$FABRIC_REPO/terraform" init
terraform -chdir="$FABRIC_REPO/terraform" plan
```
Expected: `No changes. Your infrastructure matches the configuration.` A non-empty diff means the relocated config drifted from what is deployed — stop and reconcile before proceeding.

- [ ] **Step 2: Ansible check reports no unexpected change**

```bash
ansible-playbook -i <operator inventory> "$FABRIC_REPO/ansible/overlay.yml" --check
```
Expected: no unexpected `changed` tasks (idempotent against the running overlay).

- [ ] **Step 3: pyATS still validates the running fabric**

```bash
cd "$OPS_REPO" && scripts/80-verify-lab.sh cilium-evpn
```
Expected: all testcases pass. (Needs the pyATS console on port 22; if that NSG rule is not open, record it as the one known gap, as in the GitOps slice.)

- [ ] **Step 4: Final cleanliness scan of this repo**

```bash
cd "$FABRIC_REPO"
grep -rniE 'trustsec|\bise\b|\bcml\b|azure|20\.114|192\.168\.255|127\.0\.0\.1' --include='*.tf' --include='*.yaml' --include='*.yml' --include='*.j2' . | grep -v example || echo "OK: clean"
```
Expected: `OK: clean`.

- [ ] **Step 5: Push both repos (gated on operator confirmation)**

Pushing this repo publishes. Confirm, then push this repo and the operational repo on their branches.

---

## Notes

- Tasks 1-3 are additive file work in this repo (subagent-friendly). Task 4 edits the operational repo; Task 5 touches the live fabric and needs credentials and tunnels — run by the controller, not a subagent.
- The success gate is Step 5.1: `terraform plan` showing no changes proves the relocated config equals what is deployed. That is the whole point of the relocation being safe.
