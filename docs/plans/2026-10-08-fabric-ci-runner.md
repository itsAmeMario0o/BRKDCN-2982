# Fabric CI/CD Runner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a self-hosted GitHub Actions runner that, on a push to `main` touching the fabric-as-code, applies the Terraform underlay and Ansible overlay to the live switches and verifies with pyATS.

**Architecture:** One workflow (`.github/workflows/fabric.yml`) triggered only by `push` to `main` (paths `terraform/**`, `ansible/**`) and manual `workflow_dispatch` — never by pull requests, so fork code cannot run. One job on a `self-hosted` runner (the operator's workstation), serialized by a `concurrency` group, that auto-applies then verifies. All lab-specific detail (credentials, endpoints, the forward and verify commands) comes from the runner's environment, never from this repo.

**Tech Stack:** GitHub Actions, a self-hosted runner, Terraform, Ansible, pyATS.

## Global Constraints

- Public repo: no secrets, no credentials, no real endpoints, no lab-identifying names. Operator specifics come from runner environment variables.
- No GitHub Actions secrets are defined; the runner reads `NXOS_USERNAME`/`NXOS_PASSWORD` and the gitignored `terraform.tfvars` from its own environment.
- Trigger only on `push` to `main` + `workflow_dispatch`; never `pull_request`.
- Auto-apply with `concurrency` = 1; pyATS fails the build loudly, or skips cleanly when the console is unreachable.
- Runner label: `self-hosted`. Runner lives on the operator's workstation, persistent.
- Operator environment contract (set on the runner, never committed):
  `NXOS_USERNAME`, `NXOS_PASSWORD`; `terraform.tfvars` present in `terraform/`;
  `FABRIC_INVENTORY` (path to the Ansible inventory); optional `FABRIC_ACCESS_SCRIPT`
  (brings up the SSH forwards), `FABRIC_VERIFY_SCRIPT` (pyATS verify), and
  `FABRIC_CONSOLE_HOSTPORT` (host:port the verify guard probes).

---

### Task 1: The workflow

**Files:**
- Create: `.github/workflows/fabric.yml`

**Interfaces:**
- Produces: a workflow named `fabric` on the `self-hosted` runner. Consumes the operator environment contract above.

- [ ] **Step 1: Write `.github/workflows/fabric.yml`**

```yaml
name: fabric

on:
  push:
    branches: [main]
    paths:
      - 'terraform/**'
      - 'ansible/**'
  workflow_dispatch:

# Never run two applies against the same fabric at once; do not cancel a
# mid-apply run.
concurrency:
  group: fabric-apply
  cancel-in-progress: false

jobs:
  apply:
    runs-on: [self-hosted]
    steps:
      - uses: actions/checkout@v4

      - name: Bring up fabric access
        # Operator-provided hook, kept out of this public repo: points at the
        # operator's script that opens the SSH forwards to the switches. No-op
        # if unset (the fabric is assumed already reachable).
        run: |
          if [ -n "${FABRIC_ACCESS_SCRIPT:-}" ] && [ -x "${FABRIC_ACCESS_SCRIPT}" ]; then
            "${FABRIC_ACCESS_SCRIPT}"
          else
            echo "FABRIC_ACCESS_SCRIPT not set; assuming the fabric is already reachable"
          fi

      - name: Terraform apply (underlay)
        working-directory: terraform
        # switch_urls from the gitignored terraform.tfvars; NXOS_USERNAME /
        # NXOS_PASSWORD from the runner environment. No GitHub secrets.
        run: |
          terraform init -input=false
          terraform plan -input=false -out tfplan
          terraform apply -input=false tfplan

      - name: Ansible overlay
        working-directory: ansible
        run: |
          : "${FABRIC_INVENTORY:?set FABRIC_INVENTORY to the operator inventory path}"
          ansible-playbook -i "${FABRIC_INVENTORY}" overlay.yml

      - name: pyATS verify (reachable-or-skip)
        # Fails the build if the fabric is wrong. Skips cleanly (does not fail
        # the apply) when the console is unreachable, so the known console gate
        # does not turn every run red for the wrong reason.
        run: |
          if [ -z "${FABRIC_VERIFY_SCRIPT:-}" ]; then
            echo "verify skipped: FABRIC_VERIFY_SCRIPT not set"; exit 0
          fi
          probe="${FABRIC_CONSOLE_HOSTPORT:-}"
          if [ -n "$probe" ]; then
            host="${probe%:*}"; port="${probe##*:}"
            if ! nc -z -w5 "$host" "$port" 2>/dev/null; then
              echo "verify skipped: console unreachable at ${probe}"; exit 0
            fi
          fi
          "${FABRIC_VERIFY_SCRIPT}"
```

- [ ] **Step 2: Validate the workflow YAML parses**

Run (use `actionlint` if installed, otherwise a YAML parse):
`actionlint .github/workflows/fabric.yml` or
`python3 -c 'import sys,yaml; yaml.safe_load(open(".github/workflows/fabric.yml"))' && echo OK`
Expected: no errors / `OK`.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/fabric.yml
git commit -m "feat(ci): fabric apply+verify workflow (push to main, self-hosted, auto-apply)"
```

---

### Task 2: Register the runner on the operator workstation

**Files:** none in this repo. Operator-side setup, done once.

**Interfaces:**
- Consumes: a runner registration token from the repo's Settings > Actions > Runners.
- Produces: a `self-hosted` runner online and polling for this repo.

- [ ] **Step 1: Register and install the runner**

On the operator workstation (replace `<REG_TOKEN>` with a fresh token from the
repo's Settings > Actions > Runners; the token is never committed):

```bash
mkdir -p actions-runner && cd actions-runner
# download the runner package for the workstation OS from the repo's runner page, then:
./config.sh --url https://github.com/<owner>/<repo> --token <REG_TOKEN> --labels self-hosted --unattended
./svc.sh install && ./svc.sh start
```

- [ ] **Step 2: Provide the runner environment (never committed)**

Ensure the runner service's environment has `NXOS_USERNAME` / `NXOS_PASSWORD`,
a `terraform/terraform.tfvars` with the real `switch_urls`, `FABRIC_INVENTORY`
pointing at the operator Ansible inventory, and (optionally)
`FABRIC_ACCESS_SCRIPT`, `FABRIC_VERIFY_SCRIPT`, `FABRIC_CONSOLE_HOSTPORT`.

- [ ] **Step 3: Confirm the runner is online**

Repo Settings > Actions > Runners shows the runner `Idle` with the `self-hosted`
label.

- [ ] **Step 4: Require approval for outside collaborators**

Repo Settings > Actions > General > Fork pull request workflows: require approval
for all outside collaborators. (Defense in depth; the workflow has no
`pull_request` trigger regardless.)

---

### Task 3: Verify end to end

**Files:** none.

**Interfaces:**
- Consumes: Task 1 and Task 2; a reachable fabric and the runner environment.

- [ ] **Step 1: Trigger the workflow with a no-op push to main**

```bash
git commit --allow-empty -m "ci: trigger fabric run"
git push origin main
```
Expected: the `fabric` workflow starts on the `self-hosted` runner (repo Actions tab).

- [ ] **Step 2: Confirm the run is green**

The run executes the access, terraform `plan`/`apply`, and ansible steps against
the live fabric. With the console gate closed, the pyATS step prints
`verify skipped: console unreachable ...` and the run is green. With the console
reachable, pyATS runs and a wrong fabric turns the run red.

- [ ] **Step 3: Confirm fork isolation**

A pull request (from a fork) starts no run on the runner (no `pull_request`
trigger). Confirm the Actions tab shows no self-hosted run for the PR.

---

## Notes

- The whole lab-specific surface lives in the runner's environment, so the
  workflow stays generic and public-safe.
- `terraform apply` against live switches is ungated by design (ADR 0003); the
  pyATS step is the backstop. The upgrade path to a one-click gate is a GitHub
  Environment protection rule on the apply step.
