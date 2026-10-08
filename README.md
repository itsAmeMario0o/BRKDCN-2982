# BRKDCN-2982: a VXLAN EVPN fabric with Cilium BGP, as code

A hands-on build of a single-AS NX-OS VXLAN BGP EVPN fabric with a Kubernetes
cluster (kind plus Cilium) peered into it over BGP, following the Cisco Live
BRKDCN-2982 design. It is meant to be read and run on its own, as a takeaway
that teaches the fabric, VXLAN, Cilium BGP, and the automation that builds them.

The lab substrate that makes the switches and the cluster exist lives in a
separate operational repo. This repo is the portable, durable source of truth
for the fabric-as-code and its pipeline, independent of whatever provisions the
underlying switches and nodes. It carries no secrets and no live addresses: real targets and
credentials are supplied at run time from the operator's side.

## What is here now

The fabric-as-code and the cluster automation lane:

- `terraform/` - the VXLAN EVPN underlay as a netascode `nac-nxos` data model.
  Endpoints come from the `switch_urls` variable; credentials from the
  environment. The committed data model is the reference design (no `url:`).
- `ansible/` - the EVPN overlay (Jinja templates + data model) run device-direct
  over NX-API. Inventory hosts are placeholders; override with `-i`.
- `cilium/bgp.yaml` - the Cilium AS-per-cluster BGP config (the CRDs that peer
  each node to its leaf).
- `gitops/` - Argo CD bootstrap and the app-of-apps tree. Argo runs in the
  cluster and reconciles these manifests from this repo, pull-based, nothing
  inbound. See `docs/specs/2026-10-07-argocd-pipeline-design.md`.
- `docs/decisions/` - the architectural decisions (start with ADR 0001).

More lands here over time: CI and the observability bridge. Each arrives as its
own slice with its own spec.

## Bootstrap the GitOps pipeline

From the kind host (outbound internet to GitHub and a container registry
required):

```
git clone https://github.com/itsAmeMario0o/BRKDCN-2982
cd BRKDCN-2982/gitops/bootstrap
./install.sh
```

Then watch Argo converge:

```
kubectl -n argocd get applications
kubectl -n demo get deploy,pods -o wide
```
