---
layout: default
title: Architecture
permalink: /architecture/
eyebrow: Plan
summary: One autonomous system for the whole fabric, a cluster that is its own AS, and a leaf that sits on the seam between plain BGP and EVPN.
---

## The whole thing on one page

Six Nexus switches make the fabric: two spines and four leaves. Everything runs in a single BGP (Border Gateway Protocol) autonomous system (AS), 65400. There is no OSPF and no IS-IS. The underlay is iBGP over the point-to-point links, with the spines as route-reflectors, and that is enough to bootstrap reachability between every switch loopback.

On top of the underlay the leaves run a `l2vpn evpn` overlay and VXLAN (Virtual Extensible LAN). Host subnets sit behind distributed anycast gateways, so a server keeps the same gateway address wherever it attaches. Two of the leaves form a vPC (virtual Port Channel) pair and present a shared anycast tunnel endpoint, so the pair looks like a single next hop.

Off to one side is a Kubernetes cluster running Cilium. The cluster is its own autonomous system, 65001, and peers the leaves over eBGP. This peering is the BRKDCN-2982 "AS-per-cluster" model, and it is the reason a leaf can take a pod prefix learned over eBGP and re-originate it into EVPN (Ethernet VPN).

{% include overview-diagram.html %}

## Why a single AS

A single-AS design keeps the fabric quiet. Because every switch shares one AS number, the usual eBGP workarounds disappear. There is no `allowas-in`, no `disable-peer-as-check`, and no next-hop rewriting route-map to maintain. The spines advertise their connected point-to-point `/31` networks so a leaf can resolve another leaf's loopback next hop, and the iBGP sessions carry the loopback routes that the overlay requires.

| Plane | What carries it | Role of the spines |
|---|---|---|
| Underlay | iBGP, IPv4 unicast, over the point-to-point links | Route-reflectors for loopback reachability |
| Overlay | iBGP, `l2vpn evpn`, loopback to loopback | EVPN route-reflectors (`retain route-target all`) |
| Cluster peering | eBGP, IPv4 unicast, node to leaf | Not involved; the leaf is the edge |

## The roles each switch plays

<div class="phase">
  <h3><span class="step-num">S</span> Spines</h3>
  <p>Two spines handle transit and reflection. They reflect both the underlay IPv4 routes and the overlay EVPN routes, and they advertise their connected point-to-point links so next-hop resolution works across the fabric. They terminate no hosts.</p>
</div>

<div class="phase">
  <h3><span class="step-num">L</span> Leaves</h3>
  <p>Four leaves each act as a VXLAN tunnel endpoint (VTEP). They own the distributed anycast gateway for the tenant subnets, carry the tenant VRF (virtual routing and forwarding), and sit on the seam: IPv4 unicast toward hosts and clusters, <code>l2vpn evpn</code> toward the fabric. A leaf is where a pod prefix learned over eBGP becomes an EVPN Type-5 route.</p>
</div>

<div class="phase">
  <h3><span class="step-num">vPC</span> The leaf pair</h3>
  <p>Two of the leaves form a vPC pair that shares an anycast VTEP address. To the rest of the fabric the pair is one next hop, so a dual-homed host or an endpoint behind the pair stays reachable no matter which leaf forwards the traffic.</p>
</div>

<figure class="diagram" role="img" aria-label="Two spines and four leaves in one autonomous system. The same iBGP sessions between each leaf and both spines carry the IPv4 underlay and the l2vpn evpn overlay, and the spines reflect both.">
<svg viewBox="0 0 520 290" style="max-width:100%;height:auto">
  <text x="260" y="20" text-anchor="middle" font-size="12.5" fill="currentColor" opacity="0.7">AS 65400, single autonomous system</text>
  <!-- links -->
  <g stroke="currentColor" stroke-width="1" opacity="0.5">
    <line x1="78" y1="202" x2="200" y2="86"/><line x1="78" y1="202" x2="340" y2="86"/>
    <line x1="190" y1="202" x2="200" y2="86"/><line x1="190" y1="202" x2="340" y2="86"/>
    <line x1="302" y1="202" x2="200" y2="86"/><line x1="302" y1="202" x2="340" y2="86"/>
    <line x1="414" y1="202" x2="200" y2="86"/><line x1="414" y1="202" x2="340" y2="86"/>
  </g>
  <text x="120" y="150" text-anchor="middle" font-size="10.5" fill="#02C8FF" transform="rotate(-42 120 150)">iBGP: underlay + EVPN</text>
  <!-- spines -->
  <rect x="145" y="42" width="110" height="44" rx="6" fill="none" stroke="#02C8FF" stroke-width="1.5"/>
  <text x="200" y="64" text-anchor="middle" font-size="13" fill="currentColor">spine1</text>
  <text x="200" y="79" text-anchor="middle" font-size="10.5" fill="#02C8FF">route reflector</text>
  <rect x="285" y="42" width="110" height="44" rx="6" fill="none" stroke="#02C8FF" stroke-width="1.5"/>
  <text x="340" y="64" text-anchor="middle" font-size="13" fill="currentColor">spine2</text>
  <text x="340" y="79" text-anchor="middle" font-size="10.5" fill="#02C8FF">route reflector</text>
  <!-- leaves -->
  <g font-size="12.5" fill="currentColor">
    <rect x="30" y="202" width="96" height="40" rx="6" fill="none" stroke="currentColor" stroke-width="1.2"/>
    <text x="78" y="226" text-anchor="middle">leaf1</text>
    <rect x="142" y="202" width="96" height="40" rx="6" fill="none" stroke="currentColor" stroke-width="1.2"/>
    <text x="190" y="226" text-anchor="middle">leaf2</text>
    <rect x="254" y="202" width="96" height="40" rx="6" fill="none" stroke="currentColor" stroke-width="1.2"/>
    <text x="302" y="226" text-anchor="middle">leaf3</text>
    <rect x="366" y="202" width="96" height="40" rx="6" fill="none" stroke="currentColor" stroke-width="1.2"/>
    <text x="414" y="226" text-anchor="middle">leaf4</text>
  </g>
</svg>
<figcaption>Two spines, four leaves, one AS. The same iBGP sessions between each leaf and both spines carry the IPv4 underlay and the <code>l2vpn evpn</code> overlay; the spines reflect both, so no leaf peers another leaf directly.</figcaption>
</figure>

## The tenant, in numbers

The overlay builds a symmetric integrated routing and bridging (IRB) fabric for one tenant with two subnets. The values below are the reference design; they are the same ones that the Ansible data model ships with.

| Object | Value |
|---|---|
| Tenant VRF | `tenant1`, L3 VNI 50000 |
| Segment `red` | VLAN 100, L2 VNI 10100, 10.0.100.0/24 |
| Segment `blue` | VLAN 200, L2 VNI 10200, 10.0.200.0/24 |
| Anycast gateway MAC | `0000.0000.1234`, the `.1` in each subnet |
| Fabric AS | 65400 |
| Cluster AS | 65001 |

Because `red` and `blue` route to each other across the fabric over the Layer 3 VNI (VXLAN network identifier), a host in one subnet can reach a host in the other even when they sit on different leaves. That symmetric IRB behavior is what the overlay exists to provide.

## How a node attaches

A node does not attach to a single leaf. The node dual-homes into a vPC pair over one bonded link and peers the pair over eBGP to advertise its pod CIDR.

<figure class="diagram" role="img" aria-label="A Kubernetes node dual-homes into a vPC pair of two leaves. One bonded link splits to both leaves, which share an anycast tunnel endpoint, and the node peers the pair over eBGP.">
<svg viewBox="0 0 520 300" style="max-width:100%;height:auto">
  <!-- peer-link -->
  <line x1="230" y1="73" x2="290" y2="73" stroke="currentColor" stroke-width="1.2" opacity="0.6"/>
  <text x="260" y="40" text-anchor="middle" font-size="10.5" fill="currentColor" opacity="0.7">peer-link Po500</text>
  <!-- leaves -->
  <rect x="100" y="50" width="130" height="46" rx="6" fill="none" stroke="currentColor" stroke-width="1.2"/>
  <text x="165" y="78" text-anchor="middle" font-size="13" fill="currentColor">leaf3</text>
  <rect x="290" y="50" width="130" height="46" rx="6" fill="none" stroke="currentColor" stroke-width="1.2"/>
  <text x="355" y="78" text-anchor="middle" font-size="13" fill="currentColor">leaf4</text>
  <text x="260" y="118" text-anchor="middle" font-size="11" fill="#02C8FF">vPC pair &#183; shared anycast VTEP 10.0.1.101</text>
  <!-- bonded uplink -->
  <g stroke="currentColor" stroke-width="1.3" opacity="0.6">
    <line x1="232" y1="210" x2="175" y2="96"/>
    <line x1="288" y1="210" x2="345" y2="96"/>
  </g>
  <text x="150" y="165" text-anchor="middle" font-size="10.5" fill="currentColor" opacity="0.8" transform="rotate(-62 150 165)">bonded Po10</text>
  <text x="370" y="165" text-anchor="middle" font-size="10.5" fill="#02C8FF" transform="rotate(62 370 165)">eBGP to the pair</text>
  <!-- node -->
  <rect x="195" y="210" width="130" height="50" rx="6" fill="none" stroke="currentColor" stroke-width="1.2"/>
  <text x="260" y="232" text-anchor="middle" font-size="12.5" fill="currentColor">k8s-worker</text>
  <text x="260" y="248" text-anchor="middle" font-size="10" fill="#02C8FF">bond0 &#183; static LAG</text>
</svg>
<figcaption>A node dual-homes into the vPC pair over one bonded link (static LAG, because the virtual NICs cannot negotiate LACP). The pair shares a single anycast tunnel endpoint, so the fabric sees one next hop, and the node peers the pair over eBGP to advertise its pod CIDR.</figcaption>
</figure>

Inside the node, that bond is one of two network paths. The bonded pair carries the fabric; a separate out-of-band interface holds the default route, so image pulls and telemetry skip the rate-limited firewall path.

<figure class="diagram" role="img" aria-label="Inside a node, two NICs bond into bond0 for the fabric, carrying the node address and the egress-gateway IP. A separate out-of-band NIC holds the default route.">
<svg viewBox="0 0 520 300" style="max-width:100%;height:auto">
  <defs>
    <marker id="arch-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M0,0 L10,5 L0,10 z" fill="currentColor"/>
    </marker>
  </defs>
  <!-- node boundary -->
  <rect x="60" y="54" width="300" height="208" rx="12" fill="none" stroke="currentColor" stroke-width="1" opacity="0.4"/>
  <text x="76" y="76" font-size="12" fill="currentColor" opacity="0.8">k8s-worker</text>
  <!-- NICs -->
  <g font-size="11" fill="currentColor">
    <rect x="88" y="98" width="74" height="30" rx="5" fill="none" stroke="currentColor" stroke-width="1.1"/>
    <text x="125" y="117" text-anchor="middle">ens3</text>
    <rect x="88" y="140" width="74" height="30" rx="5" fill="none" stroke="currentColor" stroke-width="1.1"/>
    <text x="125" y="159" text-anchor="middle">ens4</text>
    <rect x="88" y="198" width="74" height="30" rx="5" fill="none" stroke="currentColor" stroke-width="1.1"/>
    <text x="125" y="217" text-anchor="middle">ens2 &#183; OOB</text>
  </g>
  <!-- bond0 -->
  <rect x="210" y="102" width="138" height="64" rx="6" fill="none" stroke="#02C8FF" stroke-width="1.5"/>
  <text x="279" y="121" text-anchor="middle" font-size="12" fill="currentColor">bond0 &#183; MTU 1400</text>
  <text x="279" y="137" text-anchor="middle" font-size="10" fill="currentColor" opacity="0.85">10.0.51.10/24</text>
  <text x="279" y="152" text-anchor="middle" font-size="10" fill="#02C8FF">egress 10.0.51.100</text>
  <!-- NIC to bond -->
  <g stroke="currentColor" stroke-width="1.1" opacity="0.6">
    <line x1="162" y1="113" x2="210" y2="126"/>
    <line x1="162" y1="155" x2="210" y2="144"/>
  </g>
  <!-- fabric uplink -->
  <line x1="279" y1="102" x2="279" y2="34" stroke="currentColor" stroke-width="1.2" opacity="0.7" marker-end="url(#arch-arrow)"/>
  <text x="279" y="24" text-anchor="middle" font-size="10.5" fill="#02C8FF">to the vPC pair / fabric</text>
  <!-- OOB default -->
  <line x1="162" y1="213" x2="470" y2="213" stroke="currentColor" stroke-width="1.2" opacity="0.7" marker-end="url(#arch-arrow)"/>
  <text x="430" y="202" text-anchor="middle" font-size="10.5" fill="currentColor" opacity="0.8">default route</text>
  <text x="430" y="233" text-anchor="middle" font-size="10" fill="currentColor" opacity="0.6">out-of-band</text>
</svg>
<figcaption>Inside a node. Two virtual NICs bond into <code>bond0</code> for the fabric, a static LAG with MTU (maximum transmission unit) 1400 to fit the VXLAN overhead, carrying the node address and the egress-gateway IP 10.0.51.100. A separate out-of-band NIC holds the default route, so pulls and telemetry bypass the rate-limited firewall path.</figcaption>
</figure>

## The seam, stated plainly

The cluster speaks plain eBGP and carries no EVPN configuration. The leaf does the translation: it learns the pod prefix as an ordinary IPv4 route in the tenant VRF, then re-originates it as an EVPN Type-5 (IP prefix) route. The spines reflect that route to every other leaf, and any tunnel endpoint can now forward to the pod across VXLAN.

That one seam is what makes this a Nexus and Isovalent lab, not a single-cluster one. The next pages build the lab from the bottom up: the [underlay]({{ '/underlay/' | relative_url }}) first, then the [overlay and vPC]({{ '/overlay/' | relative_url }}), then the [Cilium peering]({{ '/cilium-bgp/' | relative_url }}) that completes the whole chain.

<div class="callout">
<strong>Design records.</strong>
The reasoning behind the split between this repo and the environment that provisions the switches, and behind the pipeline choices, lives in the <a href="https://github.com/{{ site.repo.owner }}/{{ site.repo.name }}/tree/{{ site.repo.branch }}/docs/decisions">architectural decisions</a>.
</div>
