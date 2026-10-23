---
layout: default
title: Validate the path
permalink: /validation/
eyebrow: Prove
summary: Walk a packet from a pod through the firewall to the internet one hop at a time, with the CLI that confirms each layer is doing its job.
---

## What this proves

An app pod sends traffic to the internet and it leaves through the firewall. That is not the node's default path. By design the nodes default out their out-of-band interface, which never touches the firewall, because the unlicensed firewall caps throughput near 100 Kbps. Only traffic that an egress-gateway policy selects is pinned to the firewall, source-NATed (changed with network address translation, NAT) to a dedicated egress IP, and routed over the fabric to it.

So this page validates that selected path, one hop at a time. Cilium pins the pod to the gateway node and source-NATs it to the egress IP, a policy route sends that address over the fabric, BGP (Border Gateway Protocol) EVPN (Ethernet VPN) carries it as a Type-5 route, the border leaf hands it to the firewall, and the firewall translates it out. Run the commands top to bottom. If a hop is wrong, you stop exactly where the path breaks.

```
app pod (egress-demo)
  -> Cilium egress gateway pins it to the worker node
  -> SNAT to the egress IP 10.0.51.100 on the worker's bond0
  -> policy route (table 100) sends 10.0.51.100 to the fabric gateway 10.0.51.1
  -> tenant VRF default = EVPN Type-5, VXLAN encap
  -> border leaf eBGP to the firewall (AS 65400 <-> 65500)
  -> firewall PAT -> internet
```

The node's own default traffic takes a different path: straight out the out-of-band interface, never near the fabric or the firewall.

## 1. The pod

Confirm the pod has connectivity and note which node it runs on.

```bash
kubectl get pod <pod> -o wide          # note the NODE and pod IP
kubectl exec <pod> -- ping -c3 8.8.8.8  # should succeed
```

The pod carries the label the egress-gateway policy selects (here `app: egress-demo`). That label, not the node it lands on, is what pins it to the firewall path.

## 2. Cilium egress gateway (SNAT)

The policy pins the selected pods to one gateway node and source-NATs them to a dedicated egress IP, so the firewall sees one stable address rather than a pod or node IP.

```bash
kubectl get ciliumegressgatewaypolicy app-via-firewall -o yaml
#   selectors: app=egress-demo ; egressGateway.nodeSelector: k8s-worker ; egressIP: 10.0.51.100
```

You verify the SNAT itself at the far end, on the firewall (step 7): the translation there shows 10.0.51.100, never the pod IP.

## 3. The gateway node and its policy route

On the gateway node the egress IP is a second address on `bond0`, and a policy route sends traffic from that address over the fabric. The node's own default stays out-of-band, so only the egress IP crosses the fabric.

```bash
ip addr show bond0 | grep 10.0.51.100
#   inet 10.0.51.100/24 scope global secondary bond0
ip rule | grep 10.0.51.100
#   from 10.0.51.100 lookup 100
ip route show table 100
#   default via 10.0.51.1 dev bond0            <- the fabric gateway
ip route get 8.8.8.8 from 10.0.51.100
#   8.8.8.8 from 10.0.51.100 via 10.0.51.1 dev bond0   <- over the fabric
ip route get 8.8.8.8
#   8.8.8.8 via <oob-gateway> dev <oob-nic>     <- the node default, out-of-band
```

The two `ip route get` lines are the point: the egress IP goes to the fabric, the node default goes out-of-band.

## 4. The vPC leaf pair

The gateway node's two bond members land on `Po10`, a vPC (virtual Port Channel) port-channel split across the leaf pair. Confirm the port-channel is up and the node's MAC is learned on it.

```
show port-channel summary interface port-channel10     ! Po10(SU), member (P)
show vpc brief                                          ! Po10 up, consistency success
show mac address-table vlan 51                          ! node MAC on Po10
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

## 6. The border leaf to the firewall

The border pair peers the firewall over eBGP (external BGP) in a different AS (autonomous system). Confirm the session and that the default came from it.

```
show bgp vrf tenant1 ipv4 unicast summary
!   neighbor <firewall-ip>  AS 65500  Established, 1 prefix received (the default)
```

## 7. The firewall

The firewall is the last hop before the internet. Its translation table is the definitive proof the whole chain worked: it shows the firewall translating the egress IP out with PAT (Port Address Translation).

```
show xlate | include 10.0.51.100
!   ICMP PAT from any:10.0.51.100 to outside:<firewall-outside-ip>
show conn address 10.0.51.100
show route | include 0.0.0.0
!   S* 0.0.0.0 0.0.0.0 via <nat-gateway>, outside
```

Seeing 10.0.51.100 (never the pod IP) in `show xlate` confirms the whole path at once: the egress-gateway SNAT from step 2, the policy route from step 3, and that the firewall is in the path. The firewall runs unlicensed, so this path proves enforcement, not bulk throughput.

## The reverse direction: reaching a pod

The same Type-5 machinery makes pods reachable from the fabric, and this part does not depend on the egress gateway. The leaf under the pod's node advertises the pod CIDR (Classless Inter-Domain Routing) range; every other leaf installs it over VXLAN (Virtual Extensible LAN).

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

## Expected results

| Hop | Command | Expect |
|-----|---------|--------|
| Pod | `kubectl exec <pod> -- ping 8.8.8.8` | 0% loss |
| Egress gateway | `kubectl get ciliumegressgatewaypolicy app-via-firewall` | selects the pods, egressIP 10.0.51.100 |
| Gateway node | `ip route get 8.8.8.8 from 10.0.51.100` | via 10.0.51.1, dev bond0 |
| vPC | `show vpc brief` | Po10 up, consistency success |
| Fabric | `show ip route 0.0.0.0 vrf tenant1` | Type-5, encap VXLAN |
| Border | `show bgp vrf tenant1 ipv4 unicast summary` | firewall neighbor Established |
| Firewall | `show xlate` | egress IP 10.0.51.100 PAT to outside |

---

> The commands above are the current source of truth for validating the path. The [network-as-code pipeline]({{ '/pipeline/' | relative_url }}) is meant to build and verify the fabric automatically, but that automation is a work in progress and does not yet apply to this topology.
