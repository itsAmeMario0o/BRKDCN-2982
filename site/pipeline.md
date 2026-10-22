---
layout: default
title: The pipeline
permalink: /pipeline/
eyebrow: Operate
summary: Two delivery lanes, both starting from this repo. Argo CD pulls the cluster manifests; a self-hosted runner applies the fabric. Neither needs anything inbound.
---

## Two lanes, one source of truth

This repository is the source of truth for the fabric-as-code and its pipeline. Two separate lanes keep the running environment matching the repo, because the two halves of the lab reconcile in different ways.

- **The cluster lane is pull-based.** Kubernetes is declarative and can pull, so Argo CD runs inside the cluster and reconciles the manifests from this repo.
- **The fabric lane is push-based.** The Nexus switches cannot run an in-cluster agent, so a CI runner applies Terraform and Ansible against them when the fabric-as-code changes.

## Cluster lane: Argo CD

Argo CD runs inside the cluster and reconciles Kubernetes manifests from this repo's `main` branch, pulling outbound. Because the repo is public, Argo clones it anonymously with no credential. Nothing inbound is required.

The structure is the app-of-apps pattern: one root Application points at `gitops/apps/`, and each workload is a folder under it. There is one workload today, a demo app. The pipeline grows by adding a folder under `gitops/apps/`, with no controller reconfiguration per workload.

The manifests and the bootstrap live in `gitops/`, but Argo CD is not yet deployed on this cluster. The demo app is applied by hand today, the same as the fabric. The commands below are the intended bootstrap, not a step that is already running here.

Bootstrap it from the cluster host (outbound internet to GitHub and a container registry required):

```bash
git clone https://github.com/{{ site.repo.owner }}/{{ site.repo.name }}
cd {{ site.repo.name }}/gitops/bootstrap
./install.sh
```

Then watch Argo converge:

```bash
kubectl -n argocd get applications
kubectl -n demo get deploy,pods -o wide
```

See ADR [0001](https://github.com/{{ site.repo.owner }}/{{ site.repo.name }}/tree/{{ site.repo.branch }}/docs/decisions) for why GitOps, and why this repo is the source of truth rather than the environment that provisions the switches.

## Fabric lane: a self-hosted runner

A self-hosted GitHub Actions runner is the fabric lane, complementing Argo CD rather than replacing it. When the fabric-as-code changes, it applies the Terraform underlay and the Ansible overlay to the switches and verifies the result with pyATS.

The runner lives on the operator's own workstation, where Terraform, Ansible, the SSH key, and the credentials already are. It reaches the switches through the operator's existing forwards, which a workflow pre-step brings up. Because the runner is the operator's machine, it reads the gitignored `terraform.tfvars` and the `NXOS_USERNAME` / `NXOS_PASSWORD` environment variables directly, so no GitHub Actions secrets are defined.

<div class="callout callout-warning">
<strong>The security model for a public-repo runner.</strong>
A self-hosted runner attached to a public repository is a known hazard: a fork could open a pull request carrying a malicious workflow that runs on the runner. The workflow here defines <strong>no</strong> <code>pull_request</code> trigger. It runs only on <code>push</code> to <code>main</code> (paths <code>terraform/**</code>, <code>ansible/**</code>) and on manual <code>workflow_dispatch</code>, so fork code has nothing that executes on the runner. <code>concurrency</code> is limited to one, so two pushes cannot apply to the same fabric at once.
</div>

The apply model is full continuous delivery: a push to `main` runs `terraform init`, `plan`, and `apply`, then `ansible-playbook`, then pyATS, with no manual gate. pyATS runs after the apply and fails the build loudly if the fabric is wrong. When the switch console is not reachable, the pyATS step reports a clean skip rather than failing the apply for the wrong reason.

The fabric lane is still a work in progress. The Terraform and Ansible models do not yet apply cleanly to the current topology, so the fabric is built by hand today. The CLI on the [underlay]({{ '/underlay/' | relative_url }}) and [overlay]({{ '/overlay/' | relative_url }}) pages is the current source of truth. The cluster lane is in the same state: the Argo CD manifests and bootstrap are in `gitops/`, but Argo is not yet running on this cluster, so the cluster workloads are applied by hand too.

See ADR [0003](https://github.com/{{ site.repo.owner }}/{{ site.repo.name }}/tree/{{ site.repo.branch }}/docs/decisions) for the full trade-off, including the one-click gate that is the obvious upgrade path if the no-gate choice changes.

## The docs lane

This site is a third, much smaller lane. A separate workflow builds the Jekyll site under `site/` and publishes it to GitHub Pages on any push to `main` that touches `site/`. It is independent of the fabric apply workflow, so editing a page never touches a switch.

Source: [`gitops/`](https://github.com/{{ site.repo.owner }}/{{ site.repo.name }}/tree/{{ site.repo.branch }}/gitops), the fabric workflow at [`.github/workflows/fabric.yml`](https://github.com/{{ site.repo.owner }}/{{ site.repo.name }}/blob/{{ site.repo.branch }}/.github/workflows/fabric.yml), and the [decisions](https://github.com/{{ site.repo.owner }}/{{ site.repo.name }}/tree/{{ site.repo.branch }}/docs/decisions).
