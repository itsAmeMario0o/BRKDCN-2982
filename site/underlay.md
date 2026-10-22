---
layout: default
title: The underlay
permalink: /underlay/
eyebrow: Build
summary: Build the single-AS iBGP underlay in order. Features, loopbacks, point-to-point links, then BGP with the spines as route reflectors.
---

The underlay has one job: make every switch loopback reachable from every other switch. The overlay rides on top of that reachability, so the underlay comes first.

The design is deliberately plain. One autonomous system for the whole fabric, 65400. iBGP over the point-to-point links, with the two spines as route reflectors. No OSPF, no IS-IS. The spines also advertise their connected `/31` links, so a leaf can resolve the next hop to a remote leaf's VTEP loopback. That last point matters later, and it is the only non-obvious piece.

<figure class="diagram" role="img" aria-label="Two spines act as BGP route reflectors for four leaves. Each leaf runs iBGP to both spines over point-to-point /31 links, all in AS 65400.">
<svg viewBox="0 0 660 300" style="max-width:100%;height:auto">
  <text x="330" y="22" text-anchor="middle" font-size="13" fill="currentColor" opacity="0.7">AS 65400, single autonomous system</text>
  <!-- spines -->
  <rect x="180" y="40" width="130" height="44" rx="6" fill="none" stroke="#02C8FF" stroke-width="1.5"/>
  <text x="245" y="60" text-anchor="middle" font-size="13" fill="currentColor">spine1</text>
  <text x="245" y="76" text-anchor="middle" font-size="11" fill="#02C8FF">route reflector</text>
  <rect x="350" y="40" width="130" height="44" rx="6" fill="none" stroke="#02C8FF" stroke-width="1.5"/>
  <text x="415" y="60" text-anchor="middle" font-size="13" fill="currentColor">spine2</text>
  <text x="415" y="76" text-anchor="middle" font-size="11" fill="#02C8FF">route reflector</text>
  <!-- leaves -->
  <g font-size="12" fill="currentColor">
    <rect x="40" y="220" width="120" height="40" rx="6" fill="none" stroke="currentColor" stroke-width="1.2"/>
    <text x="100" y="244" text-anchor="middle">leaf1</text>
    <rect x="200" y="220" width="120" height="40" rx="6" fill="none" stroke="currentColor" stroke-width="1.2"/>
    <text x="260" y="244" text-anchor="middle">leaf2</text>
    <rect x="340" y="220" width="120" height="40" rx="6" fill="none" stroke="currentColor" stroke-width="1.2"/>
    <text x="400" y="244" text-anchor="middle">leaf3</text>
    <rect x="500" y="220" width="120" height="40" rx="6" fill="none" stroke="currentColor" stroke-width="1.2"/>
    <text x="560" y="244" text-anchor="middle">leaf4</text>
  </g>
  <!-- links: every leaf to both spines -->
  <g stroke="currentColor" stroke-width="1" opacity="0.55">
    <line x1="100" y1="220" x2="230" y2="84"/><line x1="100" y1="220" x2="400" y2="84"/>
    <line x1="260" y1="220" x2="235" y2="84"/><line x1="260" y1="220" x2="405" y2="84"/>
    <line x1="400" y1="220" x2="255" y2="84"/><line x1="400" y1="220" x2="410" y2="84"/>
    <line x1="560" y1="220" x2="260" y2="84"/><line x1="560" y1="220" x2="415" y2="84"/>
  </g>
  <text x="150" y="160" text-anchor="middle" font-size="11" fill="currentColor" opacity="0.8" transform="rotate(-38 150 160)">iBGP, /31</text>
</svg>
<figcaption>Every leaf peers iBGP to both spines over a point-to-point /31. The spines reflect each leaf's loopbacks to the others, so no leaf-to-leaf session is needed.</figcaption>
</figure>

## Addressing

Loopback 0 is the router ID and the BGP peering address. Loopback 1 is the VTEP source the overlay will use. The uplinks are routed `/31` point-to-point links.

| Device | loopback0 | loopback1 | Uplinks |
|---|---|---|---|
| spine1 | 10.0.0.1 | n/a | Eth1/1-1/4: 10.1.1.0, .2, .4, .6 /31 (to leaf1-4) |
| spine2 | 10.0.0.2 | n/a | Eth1/1-1/4: 10.1.2.0, .2, .4, .6 /31 (to leaf1-4) |
| leaf1 | 10.0.0.11 | 10.0.1.11 | Eth1/1 10.1.1.1/31, Eth1/2 10.1.2.1/31 |
| leaf2 | 10.0.0.12 | 10.0.1.12 | Eth1/1 10.1.1.3/31, Eth1/2 10.1.2.3/31 |
| leaf3 | 10.0.0.13 | 10.0.1.13 | Eth1/1 10.1.1.5/31, Eth1/2 10.1.2.5/31 |
| leaf4 | 10.0.0.14 | 10.0.1.14 | Eth1/1 10.1.1.7/31, Eth1/2 10.1.2.7/31 |

## Build order

Work top to bottom on each switch. The spine and leaf examples below show the pattern. Repeat it for the rest of the fabric using the addressing table.

### 1. Turn on BGP

```nxos
feature bgp
```

### 2. Loopbacks

The spines need only loopback 0. The leaves also need loopback 1, the VTEP source.

```nxos
! spine1
interface loopback0
  ip address 10.0.0.1/32
```

```nxos
! leaf1
interface loopback0
  ip address 10.0.0.11/32
interface loopback1
  ip address 10.0.1.11/32
```

### 3. Point-to-point links

Routed `/31` links, no switchport. Each spine faces leaf1 through leaf4 on Eth1/1 through Eth1/4.

```nxos
! spine1
interface Ethernet1/1          ! to leaf1
  no switchport
  ip address 10.1.1.0/31
  no shutdown
interface Ethernet1/2          ! to leaf2
  no switchport
  ip address 10.1.1.2/31
  no shutdown
! Eth1/3 -> 10.1.1.4/31 (leaf3), Eth1/4 -> 10.1.1.6/31 (leaf4)
```

```nxos
! leaf1
interface Ethernet1/1          ! to spine1
  no switchport
  ip address 10.1.1.1/31
  no shutdown
interface Ethernet1/2          ! to spine2
  no switchport
  ip address 10.1.2.1/31
  no shutdown
```

### 4. BGP underlay

The spines are route reflectors. Each spine makes every leaf a `route-reflector-client`, so the leaves never peer each other directly. The spines advertise their own loopback and their connected `/31` links.

```nxos
! spine1
router bgp 65400
  router-id 10.0.0.1
  address-family ipv4 unicast
    network 10.0.0.1/32
    network 10.1.1.0/31
    network 10.1.1.2/31
    network 10.1.1.4/31
    network 10.1.1.6/31
  neighbor 10.1.1.1             ! leaf1
    remote-as 65400
    address-family ipv4 unicast
      route-reflector-client
  neighbor 10.1.1.3             ! leaf2
    remote-as 65400
    address-family ipv4 unicast
      route-reflector-client
  ! repeat for 10.1.1.5 (leaf3) and 10.1.1.7 (leaf4)
```

Each leaf peers both spines and advertises its two loopbacks.

```nxos
! leaf1
router bgp 65400
  router-id 10.0.0.11
  address-family ipv4 unicast
    network 10.0.0.11/32
    network 10.0.1.11/32
  neighbor 10.1.1.0             ! spine1
    remote-as 65400
    address-family ipv4 unicast
  neighbor 10.1.2.0             ! spine2
    remote-as 65400
    address-family ipv4 unicast
```

Why the spines advertise their `/31` links: a reflected loopback route keeps the next hop of the leaf that originated it, which is that leaf's `/31` uplink address. For leaf1 to install a route to leaf4's VTEP loopback, leaf1 must be able to resolve that next hop. Advertising the transit `/31` links puts those next hops in the table. Without it, the overlay's VTEP-to-VTEP routes would never resolve.

### 5. Verify

```nxos
show bgp ipv4 unicast summary      ! both spine sessions on each leaf, established
show ip route 10.0.1.14            ! leaf4 VTEP loopback, resolved via a transit /31
```

Loopback-to-loopback reachability across the fabric is the finish line for this stage. The overlay's EVPN sessions run loopback to loopback, so they cannot form until the underlay carries those loopbacks everywhere.

<div class="callout">
<strong>On automation.</strong>
The intended way to build this is network as code: a Terraform run against the netascode <code>nac-nxos</code> model in <a href="https://github.com/{{ site.repo.owner }}/{{ site.repo.name }}/tree/{{ site.repo.branch }}/terraform">terraform/</a>. That path is a work in progress and does not yet apply cleanly to the current topology, so the CLI above is the source of truth for now.
</div>
