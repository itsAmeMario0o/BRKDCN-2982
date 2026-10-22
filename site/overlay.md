---
layout: default
title: The overlay and vPC
permalink: /overlay/
eyebrow: Build
summary: Lay the EVPN overlay and VXLAN on the underlay, in order. Features, EVPN route reflectors, the tenant VRF and anycast gateways, the VTEP, then the vPC pair.
---

The overlay rides on the underlay from the previous page, so build the underlay first. The overlay adds two things: a BGP (Border Gateway Protocol) EVPN (Ethernet VPN) control plane for the spines to reflect, and VXLAN (Virtual Extensible LAN) tunnels between the leaves to carry tenant traffic.

The result is a symmetric IRB (integrated routing and bridging) fabric. One tenant VRF (virtual routing and forwarding), `tenant1`, with an L3 VNI (VXLAN network identifier). Two Layer 2 segments, red and blue, each with a distributed anycast gateway. A host keeps the same gateway on any leaf, and red talks to blue by routing across the L3 VNI rather than bridging.

<figure class="diagram" role="img" aria-label="Leaves are VTEPs. The EVPN control plane runs through the spine route reflectors. A vPC leaf pair shares one anycast VTEP address, so the fabric sees the pair as a single next hop.">
<svg viewBox="0 0 660 320" style="max-width:100%;height:auto">
  <!-- spines -->
  <rect x="200" y="30" width="260" height="42" rx="6" fill="none" stroke="currentColor" stroke-width="1.2"/>
  <text x="330" y="50" text-anchor="middle" font-size="13" fill="currentColor">spine1 &#183; spine2</text>
  <text x="330" y="66" text-anchor="middle" font-size="11" fill="currentColor" opacity="0.75">EVPN route reflectors</text>
  <!-- vPC pair -->
  <rect x="40" y="230" width="250" height="60" rx="6" fill="none" stroke="#02C8FF" stroke-width="1.5"/>
  <text x="165" y="255" text-anchor="middle" font-size="12" fill="currentColor">leaf1 + leaf2, vPC pair</text>
  <text x="165" y="275" text-anchor="middle" font-size="11" fill="#02C8FF">anycast VTEP 10.0.1.100</text>
  <!-- vPC pair B -->
  <rect x="420" y="230" width="200" height="60" rx="6" fill="none" stroke="#02C8FF" stroke-width="1.5"/>
  <text x="520" y="255" text-anchor="middle" font-size="11" fill="currentColor">leaf3 + leaf4, vPC pair</text>
  <text x="520" y="275" text-anchor="middle" font-size="11" fill="#02C8FF">anycast VTEP 10.0.1.101</text>
  <!-- control plane links -->
  <g stroke="currentColor" stroke-width="1" opacity="0.6">
    <line x1="165" y1="230" x2="300" y2="72"/>
    <line x1="520" y1="230" x2="400" y2="72"/>
  </g>
  <text x="205" y="150" text-anchor="middle" font-size="11" fill="currentColor" opacity="0.8" transform="rotate(-50 205 150)">EVPN control plane</text>
  <!-- VXLAN data plane -->
  <line x1="290" y1="260" x2="420" y2="260" stroke="currentColor" stroke-width="1.5" stroke-dasharray="5 4"/>
  <text x="355" y="252" text-anchor="middle" font-size="11" fill="currentColor">VXLAN: L2 VNI + L3 VNI</text>
</svg>
<figcaption>The spines reflect EVPN routes between VTEPs (VXLAN tunnel endpoints). Data rides VXLAN tunnels leaf to leaf. A vPC (virtual Port Channel) pair shares one anycast VTEP address, so the rest of the fabric routes to the pair as a single next hop.</figcaption>
</figure>

## The scheme

| Object | VLAN | VNI | Subnet | Multicast group |
|---|---|---|---|---|
| Tenant VRF `tenant1` | 2001 | 50000 (L3) | routed, no subnet | associate-vrf |
| Red segment | 100 | 10100 (L2) | 10.0.100.0/24 | 239.1.1.100 |
| Blue segment | 200 | 10200 (L2) | 10.0.200.0/24 | 239.1.1.200 |
| Node subnet, pair A | 50 | 10050 (L2) | 10.0.50.0/24 | 239.1.1.50 |
| Node subnet, pair B | 51 | 10051 (L2) | 10.0.51.0/24 | 239.1.1.51 |

Anycast gateway MAC is `0000.0000.1234`, the same fabric-wide. The VTEP sources from loopback1. EVPN runs as iBGP `l2vpn evpn` with the spines as route reflectors.

Each L2 VNI maps to one multicast group in the `239.0.0.0/8` range the underlay reserved for the rendezvous point. The L3 VNI needs no group. It is a routed transit segment between VTEPs and carries no broadcast. The node subnets, VLANs 50 and 51, are where the Kubernetes nodes attach. The [Cilium BGP]({{ '/cilium-bgp/' | relative_url }}) page builds on them.

## How a packet crosses the fabric

Symmetric IRB moves traffic between two subnets on two different leaves in a fixed sequence: bridge, route, route, bridge. The L2 VNIs stay local to each leaf. The routing between them happens over the L3 VNI, a transit segment that only the VTEPs see.

<figure class="diagram" role="img" aria-label="A packet from a red host on leaf1 is bridged to leaf1, routed into the L3 VNI, carried over VXLAN to leaf4, routed out, and bridged to a blue host. The L3 VNI is the transit segment between the two VTEPs.">
<svg viewBox="0 0 700 220" style="max-width:100%;height:auto">
  <defs>
    <marker id="ov-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M0 0 L10 5 L0 10 z" fill="currentColor"/>
    </marker>
  </defs>
  <g font-size="11" fill="currentColor">
    <!-- host A -->
    <rect x="8" y="84" width="96" height="50" rx="6" fill="none" stroke="currentColor" stroke-width="1.2"/>
    <text x="56" y="105" text-anchor="middle">Host A</text>
    <text x="56" y="121" text-anchor="middle" opacity="0.75">red 10.0.100.10</text>
    <!-- leaf1 -->
    <rect x="150" y="70" width="128" height="78" rx="6" fill="none" stroke="currentColor" stroke-width="1.2"/>
    <text x="214" y="92" text-anchor="middle">leaf1 VTEP</text>
    <text x="214" y="109" text-anchor="middle" opacity="0.75">SVI red, tenant1</text>
    <text x="214" y="125" text-anchor="middle" opacity="0.75">source 10.0.1.11</text>
    <!-- overlay pipe -->
    <rect x="300" y="82" width="100" height="54" rx="6" fill="none" stroke="#02C8FF" stroke-width="1.5"/>
    <text x="350" y="104" text-anchor="middle" fill="#02C8FF">VXLAN</text>
    <text x="350" y="120" text-anchor="middle" fill="#02C8FF">L3 VNI 50000</text>
    <!-- leaf4 -->
    <rect x="422" y="70" width="128" height="78" rx="6" fill="none" stroke="currentColor" stroke-width="1.2"/>
    <text x="486" y="92" text-anchor="middle">leaf4 VTEP</text>
    <text x="486" y="109" text-anchor="middle" opacity="0.75">SVI blue, tenant1</text>
    <text x="486" y="125" text-anchor="middle" opacity="0.75">dest 10.0.1.14</text>
    <!-- host Y -->
    <rect x="596" y="84" width="96" height="50" rx="6" fill="none" stroke="currentColor" stroke-width="1.2"/>
    <text x="644" y="105" text-anchor="middle">Host Y</text>
    <text x="644" y="121" text-anchor="middle" opacity="0.75">blue 10.0.200.10</text>
  </g>
  <!-- arrows -->
  <g stroke="currentColor" stroke-width="1.3" fill="none">
    <line x1="104" y1="109" x2="148" y2="109" marker-end="url(#ov-arrow)"/>
    <line x1="278" y1="109" x2="298" y2="109" marker-end="url(#ov-arrow)"/>
    <line x1="400" y1="109" x2="420" y2="109" marker-end="url(#ov-arrow)"/>
    <line x1="550" y1="109" x2="594" y2="109" marker-end="url(#ov-arrow)"/>
  </g>
  <g font-size="10" fill="currentColor" opacity="0.8" text-anchor="middle">
    <text x="126" y="76">bridge</text>
    <text x="289" y="76">route</text>
    <text x="411" y="76">route</text>
    <text x="572" y="76">bridge</text>
  </g>
</svg>
<figcaption>Red to blue across the fabric. leaf1 bridges the frame from Host A, routes it into the L3 VNI, and encapsulates it in VXLAN with the two leaf VTEP loopbacks as the outer source and destination. leaf4 decapsulates, routes into the blue subnet, and bridges to Host Y.</figcaption>
</figure>

## Build order

### 1. Enable the features

On every switch:

```nxos
feature bgp
feature nv overlay
nv overlay evpn
```

On the leaves, add the segment and interface features. The vPC pair also needs `vpc` and `lacp` (Link Aggregation Control Protocol).

```nxos
feature vn-segment-vlan-based
feature interface-vlan
feature vpc
feature lacp
```

Order matters here. `feature nv overlay` has to come before `nv overlay evpn`. Reverse them and NX-OS rejects the command, because the overlay module is not loaded yet.

### 2. Spines as EVPN route reflectors

Each spine reflects `l2vpn evpn` routes between the leaves and keeps all route targets so it does not need per-tenant config.

```nxos
! spine1 (spine2 is identical)
router bgp 65400
  address-family l2vpn evpn
    retain route-target all
  neighbor 10.0.0.11             ! leaf1 loopback0
    remote-as 65400
    update-source loopback0
    address-family l2vpn evpn
      send-community both
      route-reflector-client
  ! repeat for leaf2-4 loopbacks (10.0.0.12 .13 .14)
```

### 3. Tenant VRF, VLANs, and anycast gateways

On each leaf. The anycast gateway MAC is the same fabric-wide, which is what lets a host keep one gateway on any leaf.

```nxos
! leaf
fabric forwarding anycast-gateway-mac 0000.0000.1234

vlan 100
  vn-segment 10100               ! red  -> L2 VNI
vlan 200
  vn-segment 10200               ! blue -> L2 VNI
vlan 2001
  vn-segment 50000               ! tenant -> L3 VNI

vrf context tenant1
  vni 50000
  rd auto
  address-family ipv4 unicast
    route-target both auto
    route-target both auto evpn

interface Vlan2001               ! L3 VNI SVI, routing only, no IP address
  no shutdown
  vrf member tenant1
  ip forward
  no ip redirects

interface Vlan100                ! red anycast gateway
  no shutdown
  vrf member tenant1
  ip address 10.0.100.1/24
  fabric forwarding mode anycast-gateway
  no ip redirects
interface Vlan200                ! blue anycast gateway
  no shutdown
  vrf member tenant1
  ip address 10.0.200.1/24
  fabric forwarding mode anycast-gateway
  no ip redirects
```

The L3 VNI SVI (switched virtual interface) carries no IP address. The SVI is the routing anchor for the tenant VRF, so it needs `ip forward` and `no ip redirects` and nothing else. The anycast gateway SVIs take `no ip redirects` as well, since the gateway address is identical on every leaf and a redirect would point nowhere useful.

### 4. The VTEP and the EVPN instances

The NVE (network virtualization edge) interface sources from loopback1 and carries the L3 VNI plus the L2 VNIs. BGP still handles host and MAC reachability. Broadcast traffic rides the multicast tree the underlay built, so each L2 VNI binds to a `mcast-group` rather than listing every remote VTEP for head-end replication.

```nxos
! leaf
interface nve1
  no shutdown
  host-reachability protocol bgp
  source-interface loopback1
  member vni 50000 associate-vrf
  member vni 10100
    mcast-group 239.1.1.100          ! red
  member vni 10200
    mcast-group 239.1.1.200          ! blue
  member vni 10050
    mcast-group 239.1.1.50           ! node subnet, pair A
  member vni 10051
    mcast-group 239.1.1.51           ! node subnet, pair B

evpn
  vni 10100 l2
    rd auto
    route-target import auto
    route-target export auto
  vni 10200 l2
    rd auto
    route-target import auto
    route-target export auto
  vni 10050 l2
    rd auto
    route-target import auto
    route-target export auto
  vni 10051 l2
    rd auto
    route-target import auto
    route-target export auto
```

The L3 VNI keeps `associate-vrf` and binds to no group. Only the L2 VNIs carry broadcast, so only they need a multicast group. Each leaf binds the same VNI to the same group, which is how their trees line up at the rendezvous point.

### 5. Leaf BGP: EVPN to the spines, advertise the tenant

Each leaf peers both spines for `l2vpn evpn`, loopback to loopback. The tenant VRF advertises its routes into EVPN and redistributes its connected subnets.

```nxos
! leaf
route-map RM-REDIST-DIRECT permit 10

router bgp 65400
  neighbor 10.0.0.1              ! spine1 loopback0
    remote-as 65400
    update-source loopback0
    address-family l2vpn evpn
      send-community both
  neighbor 10.0.0.2              ! spine2 loopback0
    remote-as 65400
    update-source loopback0
    address-family l2vpn evpn
      send-community both
  vrf tenant1
    address-family ipv4 unicast
      advertise l2vpn evpn
      redistribute direct route-map RM-REDIST-DIRECT
      maximum-paths 8
```

### 6. The vPC pair and the anycast VTEP

Two leaves that serve a dual-homed host form a vPC pair and present one VTEP to the fabric. Loopback1 keeps its unique primary address and gains a shared secondary, the anycast VTEP address. The peer keepalive runs out of band over the management VRF. The peer link is a trunk port channel between the two leaves.

```nxos
! leaf1 of the pair; leaf2 mirrors it (swap the keepalive source and destination)
vpc domain 1
  peer-switch
  peer-gateway
  peer-keepalive destination <leaf2-mgmt-ip> source <leaf1-mgmt-ip> vrf management
  delay restore 150
  auto-recovery reload-delay 360
  ip arp synchronize
  ipv6 nd synchronize

interface loopback1
  ip address 10.0.1.100/32 secondary     ! shared anycast VTEP (VIP)

router bgp 65400
  address-family ipv4 unicast
    network 10.0.1.100/32                 ! advertise the VIP into the underlay
  address-family l2vpn evpn
    advertise-pip

interface nve1
  advertise virtual-rmac

interface Ethernet1/3
  switchport
  switchport mode trunk
  channel-group 500 mode active
interface port-channel500
  switchport mode trunk
  spanning-tree port type network
  vpc peer-link
```

Two details make the vPC correct. The shared VIP (virtual IP) must be reachable in the underlay, which is why it gets a `network` statement. And `advertise-pip` with `advertise virtual-rmac` splits the next hop by route type: Type-2 host routes use the shared VIP, Type-5 prefix routes use each leaf's unique primary address. Without that split, a routed prefix learned behind one member could be sent to the other and dropped.

### 7. Verify

```nxos
show bgp l2vpn evpn summary     ! EVPN sessions to both spines, established
show nve peers                  ! VTEP to VTEP, each leaf sees the others
show nve vni                    ! the L2 VNIs with their mcast groups, and the L3 VNI, up
show vpc brief                  ! peer adjacency and consistency, the vPC up
```

Red reaching blue is the proof the overlay works. The two hosts sit in different subnets on different leaves, and the traffic routes across the L3 VNI rather than bridging.

<div class="callout">
<strong>On automation.</strong>
The intended way to build the overlay is network as code: an Ansible run against the overlay data model in <a href="https://github.com/{{ site.repo.owner }}/{{ site.repo.name }}/tree/{{ site.repo.branch }}/ansible">ansible/</a>, device-direct over NX-API (NX-OS API). That path is a work in progress and does not yet apply cleanly to the current topology, so the CLI (command-line interface) above is the source of truth for now.
</div>
