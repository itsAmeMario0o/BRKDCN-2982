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

## What runs on a node

Cilium runs one `cilium-agent` on every node, as a DaemonSet. The agent does three jobs at once. It is the CNI plugin that wires each pod into the kernel. It compiles and loads the eBPF programs that forward and filter traffic, which is how Cilium replaces kube-proxy and the iptables path. And it runs an embedded BGP speaker that peers the leaf and advertises the node's PodCIDR. Pod traffic leaves the node natively, as routed IP. There is no VXLAN tunnel from the node to the host.

<figure class="diagram" role="img" aria-label="Each node runs cilium-agent, which programs the kernel eBPF datapath and runs an embedded BGP speaker. The speaker peers the leaf and advertises the PodCIDR. Pod traffic leaves the node as native routed IP through the NIC to the leaf.">
<svg viewBox="0 0 640 320" style="max-width:100%;height:auto">
  <defs>
    <marker id="cb-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M0 0 L10 5 L0 10 z" fill="currentColor"/>
    </marker>
  </defs>
  <rect x="20" y="30" width="400" height="275" rx="8" fill="none" stroke="currentColor" stroke-width="1" opacity="0.5"/>
  <text x="34" y="50" font-size="11" fill="currentColor" opacity="0.7">Kubernetes node</text>
  <g font-size="11" fill="currentColor">
    <rect x="44" y="64" width="150" height="46" rx="6" fill="none" stroke="currentColor" stroke-width="1.2"/>
    <text x="119" y="85" text-anchor="middle">Pod: app container</text>
    <text x="119" y="101" text-anchor="middle" opacity="0.75">eth0 (veth)</text>
    <rect x="44" y="196" width="150" height="96" rx="6" fill="none" stroke="currentColor" stroke-width="1.2"/>
    <text x="119" y="216" text-anchor="middle">Linux kernel</text>
    <text x="119" y="233" text-anchor="middle" opacity="0.75">eBPF datapath</text>
    <text x="119" y="249" text-anchor="middle" opacity="0.75">maps: policy, NAT,</text>
    <text x="119" y="263" text-anchor="middle" opacity="0.75">services (no kube-proxy)</text>
    <text x="119" y="283" text-anchor="middle" opacity="0.75">NIC: bond0</text>
    <rect x="228" y="64" width="168" height="170" rx="6" fill="none" stroke="currentColor" stroke-width="1.3"/>
    <text x="312" y="86" text-anchor="middle">cilium-agent</text>
    <text x="312" y="102" text-anchor="middle" opacity="0.75">DaemonSet, one per node</text>
    <text x="252" y="134" opacity="0.9">- CNI plugin</text>
    <text x="252" y="156" opacity="0.9">- eBPF manager</text>
    <text x="252" y="178" fill="#02C8FF">- GoBGP speaker</text>
  </g>
  <rect x="486" y="150" width="134" height="86" rx="6" fill="none" stroke="currentColor" stroke-width="1.2"/>
  <text x="553" y="188" text-anchor="middle" font-size="11" fill="currentColor">leaf (top of rack)</text>
  <text x="553" y="205" text-anchor="middle" font-size="11" fill="currentColor" opacity="0.75">fabric AS 65400</text>
  <g stroke="currentColor" stroke-width="1.3" fill="none">
    <line x1="119" y1="110" x2="119" y2="194" marker-end="url(#cb-arrow)"/>
    <line x1="228" y1="150" x2="196" y2="170" marker-end="url(#cb-arrow)"/>
    <line x1="194" y1="244" x2="486" y2="210" marker-end="url(#cb-arrow)"/>
  </g>
  <line x1="396" y1="150" x2="486" y2="178" stroke="#02C8FF" stroke-width="1.5" fill="none" marker-end="url(#cb-arrow)"/>
  <g font-size="10" fill="currentColor" opacity="0.85">
    <text x="128" y="156">veth</text>
    <text x="226" y="150" text-anchor="end">bpf()</text>
    <text x="330" y="300" text-anchor="middle">pod traffic, native routed IP (no VXLAN)</text>
  </g>
  <text x="408" y="140" font-size="10" fill="#02C8FF">BGP :179, advertise PodCIDR</text>
</svg>
<figcaption>The agent programs the kernel datapath and runs the BGP speaker. The speaker peers the leaf (cyan) and advertises the PodCIDR; pod traffic itself leaves the node as native routed IP.</figcaption>
</figure>

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
