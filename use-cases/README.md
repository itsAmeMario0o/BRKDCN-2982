# Cilium use cases

Three worked use cases that run on top of the VXLAN (Virtual Extensible LAN)
EVPN (Ethernet VPN) fabric in this repo. Each one is self-contained: a short
summary, the key features it shows, the manifests, and the commands to prove it
works.

| # | Use case | What it shows |
|---|----------|---------------|
| 1 | [Network policies](01-network-policies/) | L3/L4 (network and transport layer) and L7 (application layer) segmentation between pods with CiliumNetworkPolicy. |
| 2 | [Hubble observability](02-hubble/) | Flow visibility and the service map with Hubble and the Hubble UI. |
| 3 | [Cilium BGP (the "Network" one)](03-cilium-bgp/) | Pod CIDRs (Classless Inter-Domain Routing ranges) advertised over eBGP (external Border Gateway Protocol) to the leaves and re-originated as EVPN Type-5 routes, so a pod is reachable across the physical fabric. |

Use case 3 is the headline. Use cases 1 and 2 are things any Cilium cluster can
do; use case 3 is what makes this a *fabric* lab rather than a single-cluster
one. Start there if you only read one.

## Prerequisites

All three assume the cluster from the main build is up:

- The kubeadm cluster with Cilium as the CNI (Container Network Interface), with no kube-proxy and the BGP control plane on.
- `kubectl` and the `cilium` CLI on your path, pointed at the cluster.
- For use case 3, the spine/leaf underlay and EVPN overlay already converged.

See the top-level [README](../README.md) for the build.
