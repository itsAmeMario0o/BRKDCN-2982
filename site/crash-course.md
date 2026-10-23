---
layout: default
title: Crash course
permalink: /crash-course/
eyebrow: Run it
summary: The whole lab as a fast demo. Each step is one command and the reason behind it, end to end in about 35 minutes.
---

This page runs the whole lab as a fast demo: each step is one command and the reason it matters, nothing more. Walk it end to end in about 35 minutes, or hand it to another engineer who needs to run the same path. Each section links to the full page that explains it.

## Before you start

You need switch access (SSH or console to a spine and a leaf), a `kubectl` context on the cluster, and the `cilium` and `hubble` command-line interfaces (CLIs) on your path. Reset use case 1 to a clean baseline:

```bash
kubectl delete ns demo --ignore-not-found
kubectl apply -f use-cases/01-network-policies/00-demo-app.yaml
kubectl -n demo rollout status deploy/frontend deploy/backend deploy/database
```

## 1. Fabric underlay

On leaf1:

```
show ip bgp summary
```

**Why.** The whole fabric runs one autonomous system (AS), 65400, with the spines as Border Gateway Protocol (BGP) route reflectors. Internal BGP alone bootstraps loopback reachability, so the fabric uses no OSPF and no IS-IS. Fewer protocols mean fewer failure modes. See [Underlay]({{ '/underlay/' | relative_url }}).

## 2. VXLAN overlay

On leaf1:

```
show nve vni
show nve peers
```

**Why.** Virtual Extensible LAN (VXLAN) carries tenant traffic in tunnels. The Layer 2 VXLAN network identifiers (VNIs) carry bridged segments and the Layer 3 VNI (50000) carries routing. The NVE peers are the VXLAN tunnel endpoints (VTEPs). This layer stretches and routes tenant networks across the physical fabric. See [Overlay]({{ '/overlay/' | relative_url }}).

## 3. EVPN control plane

On leaf1:

```
show bgp l2vpn evpn summary
```

**Why.** Ethernet VPN (EVPN) is the control plane for VXLAN. Type-2 routes carry MAC and IP reachability and Type-5 routes carry IP prefixes, so the fabric advertises endpoints instead of flooding and learning them.

## 4. vPC and the anycast rendezvous point

On leaf3, then a spine:

```
show vpc brief        ! leaf3: the pair shares one anycast VTEP
show ip pim rp        ! spine: the anycast rendezvous point
```

**Why.** A virtual port channel (vPC) makes a leaf pair one logical next hop for a dual-homed host, so either leaf can forward its traffic. Broadcast traffic uses multicast here, and the anycast rendezvous point (RP) gives that multicast a redundant meeting point that both spines share.

## 5. The cluster

```
kubectl get nodes -o wide
cilium status
cilium bgp peers
```

**Why.** Cilium is the container network interface (CNI) and runs the data path in the extended Berkeley Packet Filter (eBPF), which replaces kube-proxy and the iptables chain. The cluster is its own AS (65001) and peers the leaves over external BGP. That session is the seam between Kubernetes and the fabric. See [Cilium BGP]({{ '/cilium-bgp/' | relative_url }}).

## 6. Use case 1, network policy

```bash
# python:3.12-slim has no curl; probe with the Python stdlib, same status codes
fe() { kubectl exec -n demo deploy/frontend -- python3 -c '
import sys, socket, urllib.request, urllib.error
socket.setdefaulttimeout(5)
try:
    print(urllib.request.urlopen(sys.argv[1]).status)
except urllib.error.HTTPError as e:
    print(e.code)
except Exception:
    print("000")
' "$1"; }

fe http://backend:8081/api/health                      # 200 baseline
kubectl apply -f use-cases/01-network-policies/01-default-deny.yaml
fe http://backend:8081/api/health                      # 000 blocked
kubectl apply -f use-cases/01-network-policies/02-dns-allow.yaml
kubectl apply -f use-cases/01-network-policies/03-l4-allow.yaml
fe http://backend:8081/api/health                      # 200 frontend to backend opened
fe http://database:5432/                               # 000 database still blocked
kubectl apply -f use-cases/01-network-policies/04-l7-allow.yaml
fe http://backend:8081/api/health                      # 200 GET /api/* allowed
fe http://backend:8081/private                         # 403 the path is denied
```

**Why.** Cilium enforces policy in eBPF by pod identity, not by IP address, so the rule holds wherever the pod schedules. Layer 7 rules run through an Envoy proxy that Cilium injects. The backend answers every GET with 200, so the 403 proves the policy acts, not the application. See [Use cases]({{ '/use-cases/' | relative_url }}).

## 7. Use case 2, Hubble

Install the Hubble CLI first if the node does not have it (see [Use cases]({{ '/use-cases/' | relative_url }}#use-case-2-hubble)), then:

```bash
cilium hubble port-forward &
hubble observe --namespace demo --verdict DROPPED --last 5
```

**Why.** Hubble reads the same eBPF data path that enforces the policy, so every allow and deny is visible with source and destination identity, port, and verdict. There is no sidecar and no change to the application.

## 8. Cilium BGP: pods as fabric routes

```bash
cilium bgp routes advertised ipv4 unicast
```

On leaf3:

```
show bgp l2vpn evpn | include 10.244
```

**Why.** The node advertises its pod CIDR (classless inter-domain routing block) over BGP, and the leaf re-originates it as an EVPN Type-5 route. The pod network becomes an ordinary route in the fabric, reachable across VXLAN, with no tunnel to the host and no static routes. This path is the core result of the lab.

## 9. Egress gateway, identity at the firewall

```bash
kubectl run egress-app --image=busybox --labels app=egress-demo \
  --restart=Never -it --rm -- ping -c 3 8.8.8.8
```

On the border firewall:

```
show xlate | include 10.0.51.100
```

**Why.** The Cilium egress gateway source-NATs (changes the source with network address translation) the selected pods to a fixed egress IP on a gateway node, and policy-routes that address through the firewall. The app reaches the firewall with a stable identity, 10.0.51.100, that a firewall rule governs, wherever its pods run. The firewall here is unlicensed and caps near 100 Kbps, so this path proves control, not throughput. See [EgressGW]({{ '/egress-gateway/' | relative_url }}).

## 10. Observability, Hubble and Splunk

```bash
cilium hubble ui
```

Open the `hubble_fabric_observability` dashboard in Splunk. The verdict breakdown is a built-in panel, so you run no search.

**Why.** Hubble gives real-time flow visibility, and Splunk keeps the history and the dashboards that a security team already uses. One exporter ships Hubble flows into the same OpenTelemetry (OTel) pipeline that carries cluster logs and metrics. The Flow verdicts panel shows FORWARDED against DROPPED, and a use-case-1 drop appears there, which connects enforcement to observability. See [Observability]({{ '/observability/' | relative_url }}).

## 11. GitOps

```bash
kubectl -n argocd get applications      # the root application reports Synced and Healthy
```

**Why.** Argo CD reconciles the cluster side from Git. Change the repo and the cluster follows, and a manual change self-heals on the next sync. The fabric side uses Terraform and Ansible, which is still a work in progress, so the switch CLI is the source of truth there today. See [Pipeline]({{ '/pipeline/' | relative_url }}).
