# Argo CD GitOps pipeline (Slice 1 of the cluster lane) - design

Goal: stand up Argo CD in the kind/Cilium cluster and have it reconcile a demo
app from this repository, pull-based, with nothing inbound. This proves the
teaching repo works as a GitOps source of truth and gives the repo its first
real content. It is the smallest buildable slice of the cluster automation lane.

See ADR `docs/decisions/0001-gitops-via-argocd.md` for why Argo CD and why this
repo owns the source of truth.

## Scope

In scope: Argo CD installed in the cluster, an app-of-apps root Application, one
demo app (Deployment plus Service), and a bootstrap script that a lab operator
runs once on the kind host. Teaching-oriented layout and a short README.

Out of scope, each its own later slice: relocating the Terraform underlay and
Ansible overlay into this repo; the Hubble to OpenTelemetry to Splunk telemetry
bridge; the self-hosted GitHub runner and the fabric (Terraform and Ansible) CI
lane; Argo SSO, RBAC, projects, ApplicationSets, sync waves, and notifications.

## Prerequisites

- A running kind cluster named `cilium` with Cilium installed (built by the
  operational CML repo). The fabric itself is not required for Argo to run; it
  is only required for the optional fabric-reachability check below.
- `kubectl` on the kind host with access to the cluster.
- Outbound internet from the kind host to GitHub and the container registry
  (already present in the lab).

## Repository layout

```
BRKDCN-2982/
  README.md                         teaching entry; what the repo is, how to bootstrap
  LICENSE
  docs/
    decisions/0001-gitops-via-argocd.md
    specs/2026-10-07-argocd-pipeline-design.md
  gitops/
    bootstrap/
      install.sh                    one-shot: install Argo CD (pinned), apply the root app
      root-app.yaml                 app-of-apps root Application -> gitops/apps/
    apps/
      demo/
        namespace.yaml              the demo namespace
        deployment.yaml             demo app, 2 replicas, one per Cilium node
        service.yaml                ClusterIP service for the demo app
```

## Components

### Argo CD

Installed into the `argocd` namespace from the upstream install manifest pinned
to a specific release tag (confirm the current stable tag at build time). The
bootstrap applies it; after that Argo CD manages itself. It reconciles this
repo's `main` over HTTPS, outbound, anonymously, because the repo is public.

### Root Application (app-of-apps)

`gitops/bootstrap/root-app.yaml` is a single Argo CD `Application` in the
`argocd` namespace pointing at `gitops/apps/` in this repo with directory
recursion and automated sync (prune and self-heal on). It applies every manifest
under `gitops/apps/` directly, so there is one Application object in v1. Argo
orders the apply by kind, creating namespaces before the resources in them.
Adding a workload later means dropping its manifests in a new folder under
`gitops/apps/`; the root app picks it up with no controller change. When per-app
isolation (independent sync and health) starts to matter, promote each folder to
its own child Application.

### Demo app

A trivial web Deployment (a pinned small image such as `nginx:1.27-alpine`) with
two replicas and a `podAntiAffinity` on `kubernetes.io/hostname`, so one replica
lands on `cilium-control-plane` and one on `cilium-worker`. This proves Argo
schedules across both Cilium nodes. A ClusterIP Service fronts it.
`namespace.yaml` creates the `demo` namespace; Argo applies it before the
Deployment and Service.

### Bootstrap script and the operator seam

`gitops/bootstrap/install.sh` runs once on the kind host:

```
set -euo pipefail
kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -n argocd -f <pinned argo-cd install.yaml URL>
kubectl -n argocd rollout status deploy/argocd-repo-server --timeout=180s
kubectl apply -f ./root-app.yaml    # root-app.yaml sits beside install.sh
```

The lab operator flow, from the kind host, needs no secret and no coupling to
the operational repo:

```
git clone https://github.com/itsAmeMario0o/BRKDCN-2982
cd BRKDCN-2982/gitops/bootstrap
./install.sh
```

The operational CML repo's only involvement is ensuring the cluster exists and
is reachable. It is not modified by this slice.

## Data flow

Commit to this repo's `main`. Argo CD (already running in the cluster) notices
on its next poll and reconciles `gitops/apps/`: it creates the `demo` namespace,
the Deployment, and the Service, and keeps them matching Git. A manual edit in
the cluster is reverted by self-heal.

## Testing and success criteria

The slice is done when all of the following hold on the kind host:

1. `kubectl -n argocd get applications` shows the root app `Synced` and
   `Healthy`.
2. `kubectl -n demo get deploy,pods -o wide` shows two demo pods Running, one on
   each Cilium node.
3. Drift heals: `kubectl -n demo scale deploy/demo --replicas=1`, then within a
   short interval the Deployment returns to two replicas on its own.
4. A new commit reconciles without manual `kubectl`: change a label on the demo
   Deployment in Git, push, and the live Deployment carries the new label.
5. Optional fabric re-proof (only with the fabric up): from the `red` endpoint,
   `curl http://<demo-pod-ip>:80` succeeds, since pod CIDRs are advertised into
   the fabric as EVPN Type-5.

Idempotency: re-running `install.sh` is a no-op beyond confirming the objects.

## Notes and constraints

- Public repo: no secrets, no live addresses, placeholder values only.
- No inbound: Argo pulls outbound; this matches the fabric automation.
- Ponytail: one Argo, one root app, one demo app. No extra Argo machinery until a
  second workload demands it.
