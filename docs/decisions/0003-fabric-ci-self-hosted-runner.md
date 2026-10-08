# 0003 - Fabric CI/CD on a self-hosted GitHub Actions runner

Status: accepted
Date: 2026-10-08

## Context

ADR 0001 put the cluster's continuous delivery on Argo CD, which pulls
manifests from this repo and reconciles them in the cluster. That covers
everything that runs inside Kubernetes, but not the switches. The NX-OS fabric
cannot run an in-cluster agent, and Terraform and Ansible against live switches
are push-style actions. So the fabric needs its own lane: something that, when
the fabric-as-code changes, applies the Terraform underlay and the Ansible
overlay to the switches and verifies the result.

This repo is public. A self-hosted runner attached to a public repository is a
known hazard: anyone can fork it, open a pull request carrying a malicious
workflow or code, and have it execute on the runner, which holds switch
credentials and can reach the lab. GitHub itself recommends self-hosted runners
only on private repositories. Any design here has to make untrusted fork code
unable to run on the runner.

## Decision

A self-hosted GitHub Actions runner is the fabric CI/CD lane, complementing Argo
CD (cluster) rather than replacing it.

- **Trigger (the security model).** The workflow runs only on `push` to `main`
  (paths `terraform/**`, `ansible/**`) and on manual `workflow_dispatch`. It
  defines no `pull_request` trigger, so a fork PR has nothing that runs on the
  runner. The repository is also set to require approval for all outside
  collaborators' workflow runs. The runner therefore only ever executes code a
  collaborator pushed to `main`.
- **Apply model.** Full auto-apply. A push to `main` runs `terraform init`,
  `plan`, `apply`, then `ansible-playbook`, then pyATS verification, with no
  manual gate. `concurrency` is limited to one so two pushes cannot apply to the
  same fabric at once. pyATS runs after the apply and fails the build loudly if
  the fabric is wrong.
- **Runner placement.** On the operator's workstation, registered to this repo,
  labelled `self-hosted`, run as a persistent service. It already has Terraform,
  Ansible, the SSH key, and the credentials, so there is nothing to install, and
  it survives lab rebuilds. It reaches the switches through the operator's SSH
  forwards, which a workflow pre-step brings up.
- **Secrets stay off GitHub.** Because the runner is the operator's own machine,
  it reads the gitignored `terraform.tfvars` (`switch_urls`) and the
  `NXOS_USERNAME` / `NXOS_PASSWORD` environment variables directly. No GitHub
  Actions secrets are defined.

## Consequences

- Fork and pull-request code never runs on the runner, which is the one property
  a public-repo self-hosted runner must have.
- A push to `main` reconfigures the live fabric with no gate. This is the chosen
  behavior; the pyATS step is the backstop that makes a bad apply visible rather
  than silent.
- The runner's apply only works while the operator's SSH forwards are up, and the
  pyATS step needs the switch console reachable (an operator-side network gate).
  Until that console is reachable, the pyATS step reports a clean skip rather than
  failing the apply for the wrong reason.
- No credential or endpoint enters this repo or GitHub; the seam is the same one
  the fabric-as-code already uses (`switch_urls` tfvars, `NXOS_*` env, an operator
  inventory passed with `-i`).

## Alternatives considered

- **A private automation repo or mirror for the runner.** The safest per
  GitHub's guidance, but it reintroduces the second-repo-and-sync problem that
  ADR 0002 deliberately removed. Rejected: the trigger-only-on-main model closes
  the same hole without a second repo.
- **An in-lab runner (a dedicated host or the cluster node).** It would reach the
  switches directly with no forwards, but the lab is rebuilt per session, so the
  runner would re-register every rebuild and need its toolchain reinstalled each
  time; putting it on the cluster node also mixes switch credentials and
  auto-apply onto the node that runs the live cluster. Rejected for the
  per-rebuild toil and the blast radius.
- **A gated or plan-only apply.** Lower risk, but the operator explicitly chose
  full continuous delivery. Recorded here so the trade-off is not silently
  reversed later; the one-click gate (a GitHub Environment protection rule) is the
  obvious upgrade path if that choice changes.
