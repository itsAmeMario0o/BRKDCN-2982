# 0001 - GitOps via Argo CD, this repo as the source of truth

Status: accepted
Date: 2026-10-07

## Context

The fabric-as-code for the BRKDCN-2982 lab (the NX-OS VXLAN EVPN underlay and
overlay, the Cilium BGP config, and the pipeline that applies them) was growing
inside an operational repository that provisions the lab substrate (the switches
and the cluster). That operational repo is coupled to its environment and is
rebuilt and destroyed per working session, on purpose. A disposable,
environment-specific repo is the wrong home for the durable, teachable artifact,
and it is the wrong thing for a GitOps controller to treat as the source of truth.

The cluster side of the lab is a kind cluster running Cilium. Kubernetes is
declarative and can pull, so its continuous delivery should be pull-based
reconciliation from Git rather than an external tool pushing manifests in.

## Decision

This repository (public, `itsAmeMario0o/BRKDCN-2982`) is the source of truth
for the fabric-as-code and its pipeline. Argo CD runs inside the kind cluster
and reconciles Kubernetes manifests from this repo's `main` branch, pulling
outbound. Because the repo is public, Argo clones it anonymously with no
credential.

The structure is the app-of-apps pattern: one root Application points at
`gitops/apps/`, and each workload is a folder under it. Today there is one
workload, a demo app, which proves the mechanism end to end.

The operational repo is reduced to substrate. It makes the switches and the
cluster exist and be reachable, then runs this repo's automation against them.
The two are loosely coupled: the operational repo holds a path to a sibling
checkout of this one and runs it at its own HEAD. Nothing here imports or shares
state with the operational repo.

## Consequences

- No secrets and no live targets ever land in this public repo. Real switch
  addresses, the lab host's public address, and credentials stay on the
  operational side or in a gitignored local overlay supplied at run time. This
  repo carries code plus an example data model with placeholder values.
- No inbound connectivity is required. Argo pulls outbound, the same constraint
  the fabric automation already respects.
- Relocating the existing Terraform and Ansible into this repo is deliberately
  deferred. It is a refactor of working automation with no new capability, so it
  waits until it earns its keep. Until then the fabric-as-code is split across
  the two repos, which is a folder-location inconvenience, not a design flaw.
- The pipeline grows by adding a folder under `gitops/apps/`. No controller
  reconfiguration per workload.

## Alternatives considered

- Push-based CD from the planned self-hosted GitHub runner. Rejected for the
  cluster: the cluster can pull, GitOps self-heals on drift, and pull needs no
  inbound. The runner still owns the fabric lane (Terraform and Ansible against
  the switches), which cannot run an in-cluster agent.
- Jenkins as the orchestrator. Rejected earlier in favor of a self-hosted GitHub
  runner; adding Jenkins would be a second orchestrator doing the same job.
- Keeping the fabric-as-code in the operational substrate repo. Rejected: that
  repo is disposable per session and is the wrong source of truth for GitOps.
