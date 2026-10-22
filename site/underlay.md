---
layout: default
title: The underlay
permalink: /underlay/
eyebrow: Build
summary: Build the single-AS iBGP underlay in order. Features, loopbacks, point-to-point links, BGP with the spines as route reflectors, then PIM for broadcast traffic.
---

The underlay has two jobs: make every switch loopback reachable from every other switch, and carry the overlay's broadcast traffic. The overlay rides on top of both, so the underlay comes first.

The design is deliberately plain. One autonomous system (AS) for the whole fabric, 65400. iBGP (internal Border Gateway Protocol, BGP) over the point-to-point links, with the two spines as route reflectors. No OSPF, no IS-IS. The spines also advertise their connected `/31` links, so a leaf can resolve the next hop to a remote leaf's VTEP (VXLAN tunnel endpoint) loopback. That point matters for the overlay later.

Broadcast, unknown-unicast, and multicast traffic (BUM) rides a multicast tree. PIM (Protocol Independent Multicast) sparse mode runs across the fabric, and the two spines share one anycast rendezvous point (RP). Each L2 segment maps to a multicast group, so a leaf floods a broadcast once and the fabric replicates it down the tree to the leaves that joined. The overlay page sets the per-segment groups. This page builds the PIM core they depend on.

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

Loopback 0 is the router ID and the BGP peering address. Loopback 1 is the VTEP source the overlay uses. Each spine also carries loopback 254, the shared anycast rendezvous point for PIM. The uplinks are routed `/31` point-to-point links.

| Device | loopback0 | loopback1 | loopback254 | Uplinks |
|---|---|---|---|---|
| spine1 | 10.0.0.1 | n/a | 10.254.254.254 | Eth1/1-1/4: 10.1.1.0, .2, .4, .6 /31 (to leaf1-4) |
| spine2 | 10.0.0.2 | n/a | 10.254.254.254 | Eth1/1-1/4: 10.1.2.0, .2, .4, .6 /31 (to leaf1-4) |
| leaf1 | 10.0.0.11 | 10.0.1.11 | n/a | Eth1/1 10.1.1.1/31, Eth1/2 10.1.2.1/31 |
| leaf2 | 10.0.0.12 | 10.0.1.12 | n/a | Eth1/1 10.1.1.3/31, Eth1/2 10.1.2.3/31 |
| leaf3 | 10.0.0.13 | 10.0.1.13 | n/a | Eth1/1 10.1.1.5/31, Eth1/2 10.1.2.5/31 |
| leaf4 | 10.0.0.14 | 10.0.1.14 | n/a | Eth1/1 10.1.1.7/31, Eth1/2 10.1.2.7/31 |

Both spines share the same loopback 254 address, 10.254.254.254. That is deliberate. A leaf sends its join toward whichever spine is closer, and PIM anycast keeps the two spines in sync, so either one can serve as the rendezvous point.

## Build order

Work top to bottom on each switch. The spine and leaf examples below show the pattern. Repeat it for the rest of the fabric using the addressing table.

### 1. Turn on the features

BGP carries the routes. PIM builds the multicast tree for broadcast traffic. Both go on every switch.

```nxos
feature bgp
feature pim
```

### 2. Loopbacks

The spines need loopback 0 and loopback 254, the anycast rendezvous point. The leaves need loopback 0 and loopback 1, the VTEP source. PIM sparse mode goes on every loopback that the fabric reaches.

```nxos
! spine1
interface loopback0
  ip address 10.0.0.1/32
  ip pim sparse-mode
interface loopback254            ! anycast RP, identical on both spines
  ip address 10.254.254.254/32
  ip pim sparse-mode
```

```nxos
! leaf1
interface loopback0
  ip address 10.0.0.11/32
  ip pim sparse-mode
interface loopback1
  ip address 10.0.1.11/32
  ip pim sparse-mode
```

### 3. Point-to-point links

Routed `/31` links, no switchport. Each spine faces leaf1 through leaf4 on Eth1/1 through Eth1/4. Two settings matter on every fabric link: jumbo MTU (maximum transmission unit) and PIM.

```nxos
! spine1
interface Ethernet1/1          ! to leaf1
  no switchport
  mtu 9216
  ip address 10.1.1.0/31
  ip pim sparse-mode
  no shutdown
interface Ethernet1/2          ! to leaf2
  no switchport
  mtu 9216
  ip address 10.1.1.2/31
  ip pim sparse-mode
  no shutdown
! Eth1/3 -> 10.1.1.4/31 (leaf3), Eth1/4 -> 10.1.1.6/31 (leaf4)
```

```nxos
! leaf1
interface Ethernet1/1          ! to spine1
  no switchport
  mtu 9216
  ip address 10.1.1.1/31
  ip pim sparse-mode
  no shutdown
interface Ethernet1/2          ! to spine2
  no switchport
  mtu 9216
  ip address 10.1.2.1/31
  ip pim sparse-mode
  no shutdown
```

Jumbo MTU is not optional. VXLAN adds 50 bytes of outer headers to every frame. A full 1500-byte tenant frame becomes 1550 bytes on the wire, past the default 1500 limit, and the fabric drops it. Set the fabric links to 9216 so the encapsulated frame always fits.

### 4. BGP underlay

The spines are route reflectors. Each spine makes every leaf a `route-reflector-client`, so the leaves never peer each other directly. The spines advertise their own loopbacks, including the anycast rendezvous point, and their connected `/31` links.

```nxos
! spine1
router bgp 65400
  router-id 10.0.0.1
  address-family ipv4 unicast
    network 10.0.0.1/32
    network 10.254.254.254/32    ! the anycast RP must be reachable fabric-wide
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

Why the spines advertise their `/31` links: a reflected loopback route keeps the next hop of the leaf that originated it, which is that leaf's `/31` uplink address. For leaf1 to install a route to leaf4's VTEP loopback, leaf1 must be able to resolve that next hop. Advertising the transit `/31` links puts those next hops in the table. Without that advertisement, the overlay's VTEP-to-VTEP routes would never resolve. The same advertisement carries 10.254.254.254, so every leaf can reach the rendezvous point.

### 5. PIM anycast rendezvous point

Every multicast group in the fabric shares one rendezvous point, 10.254.254.254, and both spines own that address. A leaf points at it for the whole `239.0.0.0/8` range. The spines run PIM anycast between themselves, so a source registered at one spine is known to the other.

Point every switch at the rendezvous point:

```nxos
! every switch, spines and leaves
ip pim rp-address 10.254.254.254 group-list 239.0.0.0/8
```

Then, on the spines only, pair the two anycast members so they synchronize state. Each spine lists both spine loopback0 addresses as anycast peers.

```nxos
! spine1 and spine2, identical
ip pim anycast-rp 10.254.254.254 10.0.0.1
ip pim anycast-rp 10.254.254.254 10.0.0.2
```

The leaves need nothing beyond the `rp-address` line and PIM on their interfaces. They are receivers and sources on the tree, not rendezvous points.

<figure class="diagram" role="img" aria-label="Both spines share one anycast rendezvous point at 10.254.254.254. A broadcast from a host on leaf1 travels up to a spine, which replicates it down the shared tree to leaf3 and leaf4, the leaves that joined the group. Leaf2 did not join and receives nothing.">
<svg viewBox="0 0 680 320" style="max-width:100%;height:auto">
  <defs>
    <marker id="ul-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M0 0 L10 5 L0 10 z" fill="#02C8FF"/>
    </marker>
  </defs>
  <text x="340" y="22" text-anchor="middle" font-size="12" fill="currentColor" opacity="0.75">Shared multicast tree, group 239.1.1.100</text>
  <!-- spines as one anycast RP -->
  <rect x="210" y="46" width="260" height="52" rx="6" fill="none" stroke="#02C8FF" stroke-width="1.5"/>
  <text x="340" y="68" text-anchor="middle" font-size="12" fill="currentColor">spine1 &#183; spine2</text>
  <text x="340" y="85" text-anchor="middle" font-size="11" fill="#02C8FF">anycast RP 10.254.254.254</text>
  <!-- leaves -->
  <g font-size="12" fill="currentColor">
    <rect x="30" y="240" width="130" height="46" rx="6" fill="none" stroke="currentColor" stroke-width="1.3"/>
    <text x="95" y="262" text-anchor="middle">leaf1</text>
    <text x="95" y="278" text-anchor="middle" font-size="10" opacity="0.75">source, broadcast in</text>
    <rect x="190" y="240" width="130" height="46" rx="6" fill="none" stroke="currentColor" stroke-width="1" opacity="0.45"/>
    <text x="255" y="262" text-anchor="middle" opacity="0.55">leaf2</text>
    <text x="255" y="278" text-anchor="middle" font-size="10" opacity="0.5">did not join</text>
    <rect x="350" y="240" width="130" height="46" rx="6" fill="none" stroke="currentColor" stroke-width="1.3"/>
    <text x="415" y="262" text-anchor="middle">leaf3</text>
    <text x="415" y="278" text-anchor="middle" font-size="10" opacity="0.75">joined</text>
    <rect x="510" y="240" width="130" height="46" rx="6" fill="none" stroke="currentColor" stroke-width="1.3"/>
    <text x="575" y="262" text-anchor="middle">leaf4</text>
    <text x="575" y="278" text-anchor="middle" font-size="10" opacity="0.75">joined</text>
  </g>
  <!-- leaf1 sends up -->
  <line x1="95" y1="240" x2="250" y2="98" stroke="currentColor" stroke-width="1.4" fill="none" marker-end="url(#ul-arrow)"/>
  <text x="140" y="175" font-size="10" fill="currentColor" opacity="0.85" transform="rotate(-42 140 175)">flood once, up</text>
  <!-- spine replicates down to leaf3 and leaf4 -->
  <g stroke="#02C8FF" stroke-width="1.6" fill="none">
    <line x1="400" y1="98" x2="415" y2="240" marker-end="url(#ul-arrow)"/>
    <line x1="440" y1="98" x2="570" y2="240" marker-end="url(#ul-arrow)"/>
  </g>
  <text x="516" y="159" text-anchor="middle" font-size="10" fill="#02C8FF" transform="rotate(48 516 159)">replicate down the tree</text>
</svg>
<figcaption>A broadcast from leaf1 travels up to the anycast rendezvous point once. The spine replicates it down the shared tree only to the leaves that joined the group. Leaf2 never joined, so it receives nothing. This replaces head-end replication, where the source leaf would copy the frame to every other VTEP itself.</figcaption>
</figure>

### 6. Verify

```nxos
show bgp ipv4 unicast summary      ! both spine sessions on each leaf, established
show ip route 10.0.1.14            ! leaf4 VTEP loopback, resolved via a transit /31
show ip pim rp                     ! 10.254.254.254 as the RP for 239.0.0.0/8
show ip pim neighbor               ! a PIM neighbor on every fabric link
show ip mroute                     ! the shared trees once the overlay groups are active
```

Loopback-to-loopback reachability across the fabric is the finish line for this stage. The overlay's EVPN (Ethernet VPN) sessions run loopback to loopback, so they cannot form until the underlay carries those loopbacks everywhere.

<div class="callout">
<strong>On automation.</strong>
The intended way to build the underlay is network as code: a Terraform run against the netascode <code>nac-nxos</code> model in <a href="https://github.com/{{ site.repo.owner }}/{{ site.repo.name }}/tree/{{ site.repo.branch }}/terraform">terraform/</a>. That path is a work in progress and does not yet apply cleanly to the current topology, so the CLI (command-line interface) above is the source of truth for now.
</div>
