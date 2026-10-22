---
layout: default
title: Architecture
permalink: /architecture/
eyebrow: Plan
summary: One autonomous system for the whole fabric, a cluster that is its own AS, and a leaf that sits on the seam between plain BGP and EVPN.
---

## The whole thing on one page

Six Nexus switches make the fabric: two spines and four leaves. Everything runs in a single BGP autonomous system, 65400. There is no OSPF and no IS-IS. The underlay is iBGP over the point-to-point links, with the spines acting as route-reflectors, and that is enough to bootstrap reachability between every switch loopback.

On top of the underlay the leaves run a `l2vpn evpn` overlay and VXLAN. Host subnets live behind distributed anycast gateways, so a server keeps the same gateway address wherever it attaches. Two of the leaves form a vPC pair and present a shared anycast tunnel endpoint, so the pair looks like a single next hop.

Off to one side is a Kubernetes cluster running Cilium. It is its own autonomous system, 65001, and it peers the leaves over eBGP. This is the BRKDCN-2982 "AS-per-cluster" model, and it is the reason a leaf can take a pod prefix learned over eBGP and re-originate it into EVPN.

## Why a single AS

A single-AS design keeps the fabric quiet. Because every switch shares one AS number, the usual eBGP workarounds disappear. There is no `allowas-in`, no `disable-peer-as-check`, and no next-hop rewriting route-map to maintain. The spines advertise their connected point-to-point `/31` networks so a leaf can resolve another leaf's loopback next hop, and the iBGP sessions carry the loopback routes the overlay needs.

| Plane | What carries it | Role of the spines |
|---|---|---|
| Underlay | iBGP, IPv4 unicast, over the P2P links | Route-reflectors for loopback reachability |
| Overlay | iBGP, `l2vpn evpn`, loopback to loopback | EVPN route-reflectors (`retain route-target all`) |
| Cluster peering | eBGP, IPv4 unicast, node to leaf | Not involved; the leaf is the edge |

## The roles each switch plays

<div class="phase">
  <h3><span class="step-num">S</span> Spines</h3>
  <p>Two spines, pure transit and reflection. They reflect both the underlay IPv4 routes and the overlay EVPN routes, and they advertise their connected point-to-point links so next-hop resolution works across the fabric. They terminate no hosts.</p>
</div>

<div class="phase">
  <h3><span class="step-num">L</span> Leaves</h3>
  <p>Four leaves, each a VXLAN tunnel endpoint. They own the distributed anycast gateway for the tenant subnets, carry the tenant VRF, and sit on the seam: IPv4 unicast toward hosts and clusters, <code>l2vpn evpn</code> toward the fabric. A leaf is where a pod prefix learned over eBGP becomes an EVPN Type-5 route.</p>
</div>

<div class="phase">
  <h3><span class="step-num">vPC</span> The leaf pair</h3>
  <p>Two of the leaves form a vPC pair that shares an anycast VTEP address. To the rest of the fabric the pair is one next hop, so a dual-homed host or an endpoint behind the pair is reachable whichever leaf forwards it.</p>
</div>

## The tenant, in numbers

The overlay builds a symmetric integrated routing and bridging (IRB) fabric for one tenant with two subnets. The values below are the reference design; they are the same ones the Ansible data model ships with.

| Object | Value |
|---|---|
| Tenant VRF | `tenant1`, L3 VNI 50000 |
| Segment `red` | VLAN 100, L2 VNI 10100, 10.0.100.0/24 |
| Segment `blue` | VLAN 200, L2 VNI 10200, 10.0.200.0/24 |
| Anycast gateway MAC | `0000.0000.1234`, the `.1` in each subnet |
| Fabric AS | 65400 |
| Cluster AS | 65001 |

Because `red` and `blue` route to each other across the fabric over the L3 VNI, a host in one subnet can reach a host in the other even when they sit on different leaves. That symmetric IRB behavior is the thing the overlay exists to provide.

## The seam, stated plainly

The cluster speaks plain eBGP. It neither knows nor cares that the fabric is EVPN. The leaf does the translation: it learns the pod prefix as an ordinary IPv4 route in the tenant VRF, then re-originates it as an EVPN Type-5 (IP prefix) route. The spines reflect that route to every other leaf, and any tunnel endpoint can now forward to the pod across VXLAN.

That one seam is what makes this a Nexus and Isovalent lab, not a single-cluster one. The next pages build it from the bottom up: the [underlay]({{ '/underlay/' | relative_url }}) first, then the [overlay and vPC]({{ '/overlay/' | relative_url }}), then the [Cilium peering]({{ '/cilium-bgp/' | relative_url }}) that lights up the whole chain.

<div class="callout">
<strong>Design records.</strong>
The reasoning behind the split between this repo and the environment that provisions the switches, and behind the pipeline choices, lives in the <a href="https://github.com/{{ site.repo.owner }}/{{ site.repo.name }}/tree/{{ site.repo.branch }}/docs/decisions">architectural decisions</a>.
</div>
