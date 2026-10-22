---
layout: default
title: Architectural decisions
permalink: /decisions/
eyebrow: Reference
summary: The decisions that shaped the repo and its pipeline, each recorded with its context, the call, and the alternatives that were weighed and set aside.
---

The full records live in the repo under `docs/decisions/`. Each one states the context, the decision, its consequences, and the alternatives considered, so a choice is not silently reversed later.

## 0001 — GitOps via Argo CD, this repo as the source of truth

The fabric-as-code was growing inside the operational repo that provisions the switches and the cluster, a repo that is rebuilt and destroyed per session on purpose. A disposable, environment-specific repo is the wrong home for a durable teaching artifact and the wrong thing for a GitOps controller to treat as truth. So this public repo became the source of truth, and Argo CD reconciles its manifests from inside the cluster, pulling outbound with no credential and nothing inbound.

Read: [`docs/decisions/0001-gitops-via-argocd.md`](https://github.com/{{ site.repo.owner }}/{{ site.repo.name }}/blob/{{ site.repo.branch }}/docs/decisions/0001-gitops-via-argocd.md)

## 0002 — The fabric-as-code lives in this repo; the lab is substrate

With the pipeline here, the rest of the fabric-as-code still lived in the operational repo: the Terraform underlay, the Ansible overlay, and the Cilium BGP config. That split was the thing holding the teaching repo back. The automation that builds the fabric, and teaches it, moved here beside `gitops/`, so the repo is readable and runnable on its own against any fabric that matches the design. The only environment-specific surface is six management endpoints and a password, supplied at run time, never committed.

Read: [`docs/decisions/0002-fabric-as-code-lives-here.md`](https://github.com/{{ site.repo.owner }}/{{ site.repo.name }}/blob/{{ site.repo.branch }}/docs/decisions/0002-fabric-as-code-lives-here.md)

## 0003 — Fabric CI/CD on a self-hosted GitHub Actions runner

Argo CD covers everything inside Kubernetes, but not the switches, which cannot run an in-cluster agent. The fabric needs its own lane that applies Terraform and Ansible when the fabric-as-code changes. Because a self-hosted runner on a public repo is a known hazard, the workflow defines no `pull_request` trigger and runs only on push to `main` and manual dispatch, so untrusted fork code never executes on the runner. pyATS runs after each apply as the backstop that makes a bad change visible.

Read: [`docs/decisions/0003-fabric-ci-self-hosted-runner.md`](https://github.com/{{ site.repo.owner }}/{{ site.repo.name }}/blob/{{ site.repo.branch }}/docs/decisions/0003-fabric-ci-self-hosted-runner.md)

<div class="callout">
<strong>Specs and plans.</strong>
The design specs behind these decisions, and the step-by-step plans that carried them out, are under <a href="https://github.com/{{ site.repo.owner }}/{{ site.repo.name }}/tree/{{ site.repo.branch }}/docs">docs/specs/</a> and <a href="https://github.com/{{ site.repo.owner }}/{{ site.repo.name }}/tree/{{ site.repo.branch }}/docs">docs/plans/</a>.
</div>
