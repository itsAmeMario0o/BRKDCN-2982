---
layout: default
title: Validate the path
permalink: /validation/
eyebrow: Prove
summary: Walk a packet from a pod to the internet one hop at a time, with the CLI that confirms each layer is doing its job.
---

## What this proves

A pod on a Kubernetes node sends a packet to the internet. That packet crosses six layers before it leaves: Cilium masquerades it, the node routes it onto its bond, the vPC pair hands it to the fabric, BGP EVPN carries it as a Type-5 route, the border leaf hands it to the firewall, and the ASA translates it and sends it out.

This page validates each hop with one or two commands. Run them top to bottom. If a hop is wrong, you stop exactly where the path breaks.

```
pod 10.244.0.x
  -> Cilium SNAT to the node IP (10.0.50.11)
  -> node default route out bond0
  -> vPC leaf pair (Po10)
  -> tenant VRF default = EVPN Type-5, VXLAN encap
  -> border leaf eBGP to the ASA (AS 65400 <-> 65500)
  -> ASA PAT -> internet
```

## 1. The pod

Confirm the pod has connectivity and note which node it runs on.

```bash
kubectl get pod <pod> -o wide          # note the NODE and pod IP
kubectl exec <pod> -- ip route         # default via the cilium_host
kubectl exec <pod> -- ping -c3 8.8.8.8 # should succeed
```

The pod's default points at Cilium, not at any node interface. The pod never sees the fabric addressing.

## 2. Cilium SNAT (masquerade)

Cilium rewrites the pod source to the node's own IP on the way out, so the fabric only ever sees node addresses. Confirm the node IP is the one Cilium masquerades to.

```bash
kubectl get node <node> -o wide        # INTERNAL-IP is the fabric IP, e.g. 10.0.50.11
cilium config view | grep -i masquerade   # masquerade enabled
```

You verify the SNAT itself at the far end, on the ASA (step 7): the translation there shows the node IP, never the pod IP.

## 3. The node and its bond

The node routes the packet to its default, which is the fabric gateway out `bond0`.

```bash
ip route get 8.8.8.8
#   8.8.8.8 via 10.0.50.1 dev bond0 src 10.0.50.11   <- via the fabric, not OOB
cat /proc/net/bonding/bond0 | grep -E 'Bonding Mode|MII Status'
#   Bonding Mode: load balancing (xor); both slaves MII Status: up
```

If `ip route get` shows the OOB interface instead of `bond0`, egress is leaving through management and never reaches the firewall.

## 4. The vPC leaf pair

The node's two bond members land on `Po10`, a vPC port-channel split across the leaf pair. Confirm the port-channel is up and the node's MAC is learned on it.

```
show port-channel summary interface port-channel10     ! Po10(SU), member (P)
show vpc brief                                          ! Po10 up, consistency success
show mac address-table vlan 50                          ! node MAC on Po10
```

## 5. The tenant VRF default and its Type-5 route

The leaf routes the packet in the tenant VRF. Its default is an EVPN Type-5 route pointing across the fabric to the border, carried in VXLAN.

```
show ip route 0.0.0.0 vrf tenant1
!   0.0.0.0/0 via <border VTEP>, bgp-65400, segid 50000, encap: VXLAN
show bgp l2vpn evpn | include 0.0.0.0|10.244
!   [5]:...:[0.0.0.0]  the default, and [5]:...:[10.244.x.0]  the pod CIDRs
show nve peers                                          ! VTEP adjacencies up
```

The `encap: VXLAN` and `segid 50000` (the L3VNI) are the proof the packet is tunneled, not routed in the underlay.

## 6. The border leaf to the ASA

The border pair peers the firewall over eBGP in a different AS. Confirm the session and that the default came from it.

```
show bgp vrf tenant1 ipv4 unicast summary
!   neighbor <asa-ip>  AS 65500  Established, 1 prefix received (the default)
```

## 7. The ASA

The firewall is the last hop before the internet. Its translation table is the definitive proof the whole chain worked: it shows the node IP being PAT-translated out.

```
show xlate | include <node-ip>
!   ICMP PAT from any:10.0.50.11 to outside:<asa-outside-ip>
show conn address <node-ip>
show route | include 0.0.0.0
!   S* 0.0.0.0 0.0.0.0 via <nat-gateway>, outside
```

Seeing the node IP (never the pod IP) in `show xlate` confirms two things at once: Cilium's SNAT from step 2, and that the firewall is in the path.

## The reverse direction: reaching a pod

The same Type-5 machinery makes pods reachable from the fabric. The leaf under the pod's node advertises the pod CIDR; every other leaf installs it over VXLAN.

```
show bgp l2vpn evpn | include 10.244                    ! pod CIDRs as Type-5
show ip route 10.244.0.0/24 vrf tenant1
!   via <node's VTEP>, segid 50000, encap: VXLAN
```

From the cluster side, confirm Cilium is advertising those prefixes:

```bash
cilium bgp peers                       # sessions to the leaves established
cilium bgp routes advertised ipv4 unicast   # the node's PodCIDR, next hop the node IP
```

## What good looks like

| Hop | Command | Expect |
|-----|---------|--------|
| Pod | `kubectl exec <pod> -- ping 8.8.8.8` | 0% loss |
| Node | `ip route get 8.8.8.8` | via the fabric gateway, dev bond0 |
| Bond | `/proc/net/bonding/bond0` | xor, both slaves up |
| vPC | `show vpc brief` | Po10 up, consistency success |
| Fabric | `show ip route 0.0.0.0 vrf tenant1` | Type-5, encap VXLAN |
| Border | `show bgp vrf tenant1 ipv4 unicast summary` | ASA neighbor Established |
| ASA | `show xlate` | node IP PAT to outside |

---

> The commands above are the current source of truth for validating the path. The [network-as-code pipeline]({{ '/pipeline/' | relative_url }}) is meant to build and verify the fabric automatically, but that automation is a work in progress and does not yet apply to this topology.
