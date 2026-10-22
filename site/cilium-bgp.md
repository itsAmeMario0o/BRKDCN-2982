---
layout: default
title: Cilium BGP
permalink: /cilium-bgp/
eyebrow: Peer
summary: The cluster becomes its own autonomous system and advertises pod CIDRs into the leaves, which re-originate them as EVPN Type-5 routes.
---

## The idea

Advertise pod CIDRs out of the cluster over eBGP, let the leaves re-originate them as EVPN Type-5 routes, and reach a pod from anywhere on the physical fabric. There is no overlay tunnel to the host and no static routes. The pod network is just another prefix in the fabric's routing table.

This is the use case the lab is built for. The two [other use cases]({{ '/use-cases/' | relative_url }}) run on any Cilium cluster. This one needs a real spine-leaf fabric underneath, which is exactly what the [underlay]({{ '/underlay/' | relative_url }}) and [overlay]({{ '/overlay/' | relative_url }}) stand up.

## The path a pod prefix takes

```
pod (10.244.x.0/24)
  -> Cilium BGP control plane on the node
  -> eBGP session to the leaf (cluster AS 65001 -> fabric)
  -> leaf imports the prefix into the tenant VRF
  -> leaf re-originates it as an EVPN Type-5 (IP prefix) route
  -> spines reflect it to every other leaf
  -> any VTEP can now route to the pod across VXLAN
```

The cluster speaks plain eBGP; it does not know or care that the fabric is EVPN. The leaf is the seam: BGP IPv4 unicast on the south side, `l2vpn evpn` on the north side.

## The three CRDs

Cilium's BGP control plane is configured with three custom resources. They live with the fabric config, in [`cilium/bgp.yaml`](https://github.com/{{ site.repo.owner }}/{{ site.repo.name }}/blob/{{ site.repo.branch }}/cilium/bgp.yaml).

- `CiliumBGPClusterConfig` is the cluster's BGP speaker: local AS 65001, peering the leaf. There is one per node, because each node peers a different leaf address.
- `CiliumBGPPeerConfig` sets timers, graceful restart, and which address families to carry. It is shared.
- `CiliumBGPAdvertisement` says what to advertise: `PodCIDR`, and optionally LoadBalancer service IPs. It is shared.

A trimmed view of one node plus the shared objects:

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
      kubernetes.io/hostname: <node>   # that node peers its own leaf
  bgpInstances:
    - name: "as65001"
      localASN: 65001
      peers:
        - name: leaf1
          peerASN: 65400            # the fabric's single AS
          peerAddress: 10.2.1.1     # this node's upstream leaf
          peerConfigRef:
            name: peer-leaf
```

<div class="callout">
<strong>Values track the live cluster.</strong>
Node names and peer addresses track the cluster they run against. The authoritative values are in the applied <code>bgp.yaml</code>, not this snippet.
</div>

## Run it

```bash
kubectl apply -f cilium/bgp.yaml
```

## Verify

Cluster side:

```bash
cilium bgp peers                              # sessions to the leaf -> Established
cilium bgp routes advertised ipv4 unicast     # the PodCIDRs leaving the cluster
```

Fabric side, on a leaf:

```
show bgp ipv4 unicast neighbors <node-ip>   # the cluster session, prefixes received
show bgp l2vpn evpn                          # the pod prefix as a Type-5 route
show nve peers                               # VTEP adjacency to the far leaf pair
show ip route vrf <tenant>                   # the pod CIDR installed in the VRF
```

End to end, reach a pod on one leaf pair from a host on the other:

```bash
# from a host in the far VRF:
ping <pod-ip-on-leaf-pair-a>
```

If the ping crosses the fabric, the whole chain is proven: Cilium advertised the prefix, the leaf re-originated it into EVPN, the spines reflected it, and VXLAN carried the data plane.

<div class="callout callout-warning">
<strong>Testing from a switch instead of a host?</strong>
Always set an explicit, unique <code>source</code> on the ping, for example <code>ping &lt;remote&gt; vrf &lt;tenant&gt; source &lt;a per-leaf loopback in the VRF&gt;</code>. An unsourced VRF ping sources from the anycast gateway SVI, whose address is identical on every leaf, so the reply never comes back and a healthy fabric looks broken. Real pods have their own addresses and are not affected.
</div>

Source: [`cilium/bgp.yaml`](https://github.com/{{ site.repo.owner }}/{{ site.repo.name }}/blob/{{ site.repo.branch }}/cilium/bgp.yaml).
