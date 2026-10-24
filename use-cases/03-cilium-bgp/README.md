# Use case 3: Cilium BGP

**Advertise pod CIDRs (Classless Inter-Domain Routing ranges) out of the
cluster over eBGP (external Border Gateway Protocol), let the leaves
re-originate them as EVPN (Ethernet VPN) Type-5 routes, and reach a pod from
anywhere on the physical fabric.** No overlay tunnel to the host, no static
routes: the pod network is just another prefix in the fabric's routing table.

This is the use case the lab is built for. Use cases 1 and 2 run on any Cilium
cluster. This one needs a real spine/leaf fabric underneath, which is exactly
what this repo stands up.

## The path a pod prefix takes

```
pod (10.244.x.0/24)
  -> Cilium BGP control plane on the node
  -> eBGP session to the leaf pair (cluster AS 65001 -> fabric)
  -> leaf imports the prefix into the tenant VRF
  -> leaf re-originates it as an EVPN Type-5 (IP prefix) route
  -> spines reflect it to every other leaf
  -> any VTEP can now route to the pod across VXLAN
```

The cluster speaks plain eBGP; it does not know or care that the fabric is
EVPN. The leaf is the seam: BGP IPv4 unicast on the south side, l2vpn evpn on
the north side.

## Key features

- `CiliumBGPClusterConfig`, the cluster's BGP speaker: local AS (autonomous
  system) 65001, peer the leaf pair.
- `CiliumBGPPeerConfig`, timers, graceful restart, and which address families
  to carry.
- `CiliumBGPAdvertisement`, advertise `PodCIDR` (and, optionally, LoadBalancer
  service IPs).
- The fabric side: the leaf redistributes the learned pod prefix into EVPN as a
  Type-5 route, so it is reachable from the other leaf pair across VXLAN (Virtual
  Extensible LAN).

## Manifests

The Cilium BGP CRDs (custom resource definitions) live with the fabric config in this repo. See
[`../../cilium/bgp.yaml`](../../cilium/bgp.yaml) for the applied manifest. The
leaf underlay/overlay that terminates these sessions is in
[`../../terraform/`](../../terraform/).

There is one `CiliumBGPClusterConfig` per node, because each node peers a
different leaf address. The advertisement and peer config are shared. A trimmed
view of one node plus the shared objects:

```yaml
apiVersion: cilium.io/v2
kind: CiliumBGPAdvertisement
metadata:
  name: podcidr
  labels:
    advertise: podcidr
spec:
  advertisements:
    - advertisementType: PodCIDR
---
apiVersion: cilium.io/v2
kind: CiliumBGPPeerConfig
metadata:
  name: peer-leaf
spec:
  families:
    - afi: ipv4
      safi: unicast
      advertisements:
        matchLabels:
          advertise: podcidr
---
apiVersion: cilium.io/v2
kind: CiliumBGPClusterConfig
metadata:
  name: cp-leaf1
spec:
  nodeSelector:
    matchLabels:
      kubernetes.io/hostname: k8s-cp   # that node peers its own leaf
  bgpInstances:
    - name: "as65001"
      localASN: 65001
      peers:
        - name: leaf1
          peerASN: 65400            # the fabric's single AS
          peerAddress: 10.0.50.1    # this node's upstream leaf
          peerConfigRef:
            name: peer-leaf
```

> Node names and peer addresses track the live cluster; the authoritative
> values are in the applied `bgp.yaml`, not this snippet.

## Run it

```bash
kubectl apply -f ../../cilium/bgp.yaml
```

## Verify

Cluster side:

```bash
cilium bgp peers                 # sessions to the leaf pair -> Established
cilium bgp routes advertised ipv4 unicast   # the PodCIDRs leaving the cluster
```

Fabric side (on a leaf):

```
show bgp ipv4 unicast neighbors <node-ip>   # the cluster session, prefixes received
show bgp l2vpn evpn                          # the pod prefix as a Type-5 route
show nve peers                               # VTEP adjacency to the far leaf pair
show ip route vrf <tenant>                   # the pod CIDR installed in the VRF
```

End to end, reach a pod on one leaf pair from a host on the other:

```bash
# from the border-side k8s node (or a host in the far VRF):
ping <pod-ip-on-leaf-pair-a>
```

If the ping crosses the fabric, the whole chain is proven: Cilium advertised it,
the leaf re-originated it into EVPN, the spines reflected it, and VXLAN carried
the data plane.

> Testing from a switch instead of a host? Always set an explicit, unique
> `source` on the ping, for example `ping <remote> vrf <tenant> source
> <a per-leaf loopback in the VRF>`. An unsourced VRF (Virtual Routing and
> Forwarding) ping sources from the anycast gateway SVI (Switched Virtual
> Interface), whose address is identical on every leaf, so the reply never
> comes back and a healthy fabric looks broken. Real pods have their own
> addresses and are not affected.

## Captured output

Real `cilium bgp peers` / `show bgp l2vpn evpn` / ping output lands here once
the fabric is converged, so the use case reads as a record of a working lab
rather than a plan.
