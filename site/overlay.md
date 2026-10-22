---
layout: default
title: The overlay and vPC
permalink: /overlay/
eyebrow: Build
summary: Lay the EVPN overlay and VXLAN on the underlay, in order. Features, EVPN route reflectors, the tenant VRF and anycast gateways, the VTEP, then the vPC pair.
---

The overlay rides on the underlay from the previous page, so build the underlay first. The overlay adds two things: a BGP EVPN control plane for the spines to reflect, and VXLAN tunnels between the leaves to carry tenant traffic.

The result is a symmetric IRB fabric. One tenant VRF, `tenant1`, with an L3 VNI. Two Layer 2 segments, red and blue, each with a distributed anycast gateway. A host keeps the same gateway on any leaf, and red talks to blue by routing across the L3 VNI rather than bridging.

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
  <!-- single leaf -->
  <rect x="420" y="230" width="200" height="60" rx="6" fill="none" stroke="currentColor" stroke-width="1.2"/>
  <text x="520" y="255" text-anchor="middle" font-size="12" fill="currentColor">leaf3</text>
  <text x="520" y="275" text-anchor="middle" font-size="11" fill="currentColor" opacity="0.75">VTEP 10.0.1.13</text>
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
<figcaption>The spines reflect EVPN routes between VTEPs. Data rides VXLAN tunnels leaf to leaf. A vPC pair shares one anycast VTEP address, so the rest of the fabric routes to the pair as a single next hop.</figcaption>
</figure>

## The scheme

| Object | Value |
|---|---|
| Tenant VRF | `tenant1`, L3 VNI 50000 (VLAN 2001) |
| Red segment | VLAN 100, L2 VNI 10100, 10.0.100.0/24 |
| Blue segment | VLAN 200, L2 VNI 10200, 10.0.200.0/24 |
| Anycast gateway MAC | 0000.0000.1234 |
| VTEP source | loopback1 (from the underlay) |
| EVPN | iBGP `l2vpn evpn`, spines as route reflectors |

## Build order

### 1. Enable the features

On every switch:

```nxos
feature bgp
feature nv overlay
nv overlay evpn
```

On the leaves, add the segment and interface features. The vPC pair also needs `vpc` and `lacp`.

```nxos
feature vn-segment-vlan-based
feature interface-vlan
feature vpc
feature lacp
```

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
      send-community
      send-community extended
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

interface Vlan2001               ! L3 VNI SVI, routing only
  no shutdown
  vrf member tenant1
  ip forward

interface Vlan100                ! red anycast gateway
  no shutdown
  vrf member tenant1
  ip address 10.0.100.1/24
  fabric forwarding mode anycast-gateway
interface Vlan200                ! blue anycast gateway
  no shutdown
  vrf member tenant1
  ip address 10.0.200.1/24
  fabric forwarding mode anycast-gateway
```

### 4. The VTEP and the EVPN instances

The NVE interface sources from loopback1 and carries the L3 VNI plus the two L2 VNIs. BGP handles host reachability, so each L2 VNI floods broadcast traffic with ingress replication rather than multicast.

```nxos
! leaf
interface nve1
  no shutdown
  host-reachability protocol bgp
  source-interface loopback1
  member vni 50000 associate-vrf
  member vni 10100
    ingress-replication protocol bgp
  member vni 10200
    ingress-replication protocol bgp

evpn
  vni 10100 l2
    rd auto
    route-target import auto
    route-target export auto
  vni 10200 l2
    rd auto
    route-target import auto
    route-target export auto
```

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
      send-community
      send-community extended
  neighbor 10.0.0.2              ! spine2 loopback0
    remote-as 65400
    update-source loopback0
    address-family l2vpn evpn
      send-community
      send-community extended
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

Two details make this correct. The shared VIP must be reachable in the underlay, which is why it gets a `network` statement. And `advertise-pip` with `advertise virtual-rmac` splits the next hop by route type: Type-2 host routes use the shared VIP, Type-5 prefix routes use each leaf's unique primary address. Without that split, a routed prefix learned behind one member could be sent to the other and dropped.

### 7. Verify

```nxos
show bgp l2vpn evpn summary     ! EVPN sessions to both spines, established
show nve peers                  ! VTEP to VTEP, each leaf sees the others
show nve vni                    ! the two L2 VNIs and the L3 VNI, up
show vpc brief                  ! peer adjacency and consistency, the vPC up
```

Red reaching blue is the proof the overlay works. The two hosts sit in different subnets on different leaves, and the traffic routes across the L3 VNI rather than bridging.

<div class="callout">
<strong>On automation.</strong>
The intended way to build this is network as code: an Ansible run against the overlay data model in <a href="https://github.com/{{ site.repo.owner }}/{{ site.repo.name }}/tree/{{ site.repo.branch }}/ansible">ansible/</a>, device-direct over NX-API. That path is a work in progress and does not yet apply cleanly to the current topology, so the CLI above is the source of truth for now.
</div>
