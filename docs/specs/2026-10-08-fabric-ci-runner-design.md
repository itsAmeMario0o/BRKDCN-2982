# Fabric CI/CD runner - design

Goal: a self-hosted GitHub Actions runner that, when the fabric-as-code changes
on `main`, applies the Terraform underlay and the Ansible overlay to the live
switches and verifies the result with pyATS. This is the fabric lane; Argo CD
(ADR 0001) already owns the cluster lane. Together they are the two halves of
the pipeline.

See ADR `docs/decisions/0003-fabric-ci-self-hosted-runner.md` for why.

## Scope

In scope: one workflow (`.github/workflows/fabric.yml`), the runner registration
and service on the operator's workstation, and a short operator runbook. The
pipeline stages: bring up the SSH forwards, `terraform init`/`plan`/`apply`, the
Ansible overlay, pyATS verification.

Out of scope, each its own slice: the Hubble to OpenTelemetry to Splunk
telemetry bridge; any application beyond the GitOps demo; a one-click approval
gate on the apply (the upgrade path if the auto-apply choice changes); turning
the pyATS console gate on (an operator-side network change).

## Security model (public repo)

The repository is public, so the workflow must never run untrusted fork code on
the runner:

- Triggers are `push` to `main` (paths `terraform/**`, `ansible/**`) and manual
  `workflow_dispatch`. There is no `pull_request` trigger.
- Only collaborators can push to `main`, so the runner only ever runs code that
  reached `main`. A fork PR has nothing that executes on the runner.
- The repository setting requires approval for all outside collaborators' runs,
  as defense in depth.

## Pipeline (auto-apply)

A push to `main` under the watched paths runs one job on the self-hosted runner,
serialized by a `concurrency` group so two pushes cannot apply at once:

1. **Checkout** this repo.
2. **Bring up the SSH forwards** to the switch management endpoints (an operator
   pre-step; the forwards are the runner's path to the fabric).
3. **Terraform** `init`, `plan`, then `apply`. `switch_urls` comes from the
   gitignored `terraform.tfvars`; credentials from `NXOS_USERNAME` /
   `NXOS_PASSWORD` in the environment.
4. **Ansible** `ansible-playbook overlay.yml -i <operator inventory>` for the
   EVPN overlay.
5. **pyATS verify.** Runs after the apply and fails the build if the fabric is
   wrong. If the switch console is not reachable (the operator-side console gate
   is closed), the step reports `verify skipped: console unreachable` and does
   not fail the apply for the wrong reason. It becomes a real gate once the
   console is reachable.

## Runner placement and the seam

The runner is the operator's own workstation, registered to this repo, labelled
`self-hosted`, run as a persistent service. It already carries Terraform,
Ansible, the SSH key, and the credentials, so nothing is installed for it, and it
outlives lab rebuilds.

Because the runner is the operator's machine, secrets stay off GitHub entirely.
No GitHub Actions secrets are defined. The runner reads the gitignored
`terraform.tfvars` and the `NXOS_*` environment variables directly, and the
Ansible inventory is supplied with `-i`. This is the same seam the fabric-as-code
already uses; the runner adds no new secret surface.

## Testing and success criteria

- A push to `main` that touches `terraform/**` or `ansible/**` starts the
  workflow on the self-hosted runner (visible in the repo's Actions tab).
- The job runs `terraform plan` and `apply`, then the Ansible overlay, against
  the live fabric, and both complete.
- With the console gate closed, pyATS reports a clean skip and the run is green;
  with it open, pyATS runs and a wrong fabric turns the run red.
- A fork pull request triggers nothing on the runner.
- `concurrency` prevents a second run from applying while the first is mid-apply.

## Runner setup outline

On the operator's workstation, once:

- Download the GitHub Actions runner, register it to this repository with a
  registration token from the repo's Settings > Actions > Runners, give it the
  `self-hosted` label, and install it as a service so it polls GitHub outbound.
- Ensure the shell the service runs under has `NXOS_USERNAME` / `NXOS_PASSWORD`
  in its environment and the gitignored `terraform.tfvars` in place, and that the
  SSH key and forwards are available.

No registration token, address, or credential is recorded in this repo.
