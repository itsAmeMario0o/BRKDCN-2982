---
layout: default
title: Egress gateway through the firewall
permalink: /egress-gateway/
eyebrow: Peer
summary: Send one app's internet egress through the firewall as a fixed source IP, so a firewall rule can govern that app by address. Cilium egress gateway pins the source IP, a policy route carries it over the fabric to the firewall.
---

## The problem

A firewall can only govern what it can name. Pods are the wrong thing to name. A pod IP comes from the cluster's own CIDR, it changes on every restart, and the firewall never sees it because the node masquerades pod traffic behind the node address before it leaves. So a security policy keyed on "this app" has nothing stable to match.

The fix is to give one app a fixed, routable source address and send its egress through the firewall. Cilium egress gateway does the pinning. The fabric and a policy route do the steering. After that, a firewall rule keyed on one IP governs the whole app, wherever its pods land.

This is a Cilium use case that needs the fabric underneath, like [Cilium BGP]({{ '/cilium-bgp/' | relative_url }}). The pod prefixes already reach the fabric as EVPN Type-5 routes. Egress gateway adds a return path for selected traffic: out through a border node, across the fabric, to the firewall at the edge.

## The path

<figure class="diagram" role="img" aria-label="An app pod on the control-plane node sends traffic to the internet. Cilium forwards it to the worker node, the egress gateway, which source-NATs it to 10.0.51.100. A policy route sends that address over the fabric to the firewall, which applies a rule keyed on 10.0.51.100 and forwards to the internet. The node's own management traffic leaves on a separate out-of-band path and never touches the firewall.">
<svg viewBox="0 0 720 340" style="max-width:100%;height:auto">
  <defs>
    <marker id="eg-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M0 0 L10 5 L0 10 z" fill="currentColor"/>
    </marker>
    <marker id="eg-arrow-cyan" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M0 0 L10 5 L0 10 z" fill="#02C8FF"/>
    </marker>
  </defs>
  <g font-size="11" fill="currentColor">
    <!-- app pod -->
    <rect x="16" y="40" width="130" height="60" rx="6" fill="none" stroke="currentColor" stroke-width="1.2"/>
    <text x="81" y="64" text-anchor="middle">app pod</text>
    <text x="81" y="81" text-anchor="middle" opacity="0.75">on cp node</text>
    <text x="81" y="95" text-anchor="middle" opacity="0.75">10.244.0.x</text>
    <!-- worker gateway -->
    <rect x="200" y="30" width="170" height="80" rx="6" fill="none" stroke="#02C8FF" stroke-width="1.5"/>
    <text x="285" y="54" text-anchor="middle">worker node</text>
    <text x="285" y="71" text-anchor="middle" opacity="0.8">egress gateway</text>
    <text x="285" y="90" text-anchor="middle" fill="#02C8FF">SNAT to 10.0.51.100</text>
    <text x="285" y="104" text-anchor="middle" opacity="0.7" font-size="10">bond0 on the fabric</text>
    <!-- fabric -->
    <rect x="200" y="150" width="170" height="54" rx="6" fill="none" stroke="currentColor" stroke-width="1.1" opacity="0.7"/>
    <text x="285" y="173" text-anchor="middle">fabric</text>
    <text x="285" y="190" text-anchor="middle" opacity="0.75" font-size="10">table 100: via 10.0.51.1</text>
    <!-- firewall -->
    <rect x="430" y="150" width="150" height="54" rx="6" fill="none" stroke="#02C8FF" stroke-width="1.5"/>
    <text x="505" y="173" text-anchor="middle">firewall</text>
    <text x="505" y="190" text-anchor="middle" fill="#02C8FF" font-size="10">rule matches 10.0.51.100</text>
    <!-- internet -->
    <rect x="610" y="150" width="94" height="54" rx="6" fill="none" stroke="currentColor" stroke-width="1.2"/>
    <text x="657" y="181" text-anchor="middle">internet</text>
    <!-- OOB -->
    <rect x="20" y="228" width="160" height="56" rx="6" fill="none" stroke="currentColor" stroke-width="1" opacity="0.5" stroke-dasharray="5 4"/>
    <text x="100" y="251" text-anchor="middle" opacity="0.7">node management</text>
    <text x="100" y="268" text-anchor="middle" opacity="0.6" font-size="10">out of band, skips firewall</text>
  </g>
  <!-- flows -->
  <line x1="146" y1="70" x2="198" y2="70" stroke="currentColor" stroke-width="1.4" fill="none" marker-end="url(#eg-arrow)"/>
  <text x="172" y="60" text-anchor="middle" font-size="10" fill="currentColor" opacity="0.8">egress</text>
  <line x1="285" y1="110" x2="285" y2="148" stroke="#02C8FF" stroke-width="1.6" fill="none" marker-end="url(#eg-arrow-cyan)"/>
  <line x1="370" y1="177" x2="428" y2="177" stroke="#02C8FF" stroke-width="1.6" fill="none" marker-end="url(#eg-arrow-cyan)"/>
  <line x1="580" y1="177" x2="608" y2="177" stroke="currentColor" stroke-width="1.4" fill="none" marker-end="url(#eg-arrow)"/>
  <polyline points="215,110 215,132 100,132 100,226" stroke="currentColor" stroke-width="1" fill="none" opacity="0.45" stroke-dasharray="5 4" marker-end="url(#eg-arrow)"/>
  <text x="128" y="126" text-anchor="middle" font-size="9.5" fill="currentColor" opacity="0.6">node default</text>
</svg>
<figcaption>The app pod runs on the control-plane node, but its egress is pinned to the worker. The worker source-NATs it to 10.0.51.100 and a policy route sends that address over the fabric to the firewall, which matches a rule on 10.0.51.100 before forwarding to the internet. The node's own management traffic takes the out-of-band path and never reaches the firewall.</figcaption>
</figure>

## Build order

### 1. Turn on egress gateway in Cilium

Egress gateway needs the eBPF masquerade path. Enable both and let the agents restart.

```bash
cilium config set enable-ipv4-egress-gateway true
cilium config set enable-bpf-masquerade true
kubectl -n kube-system rollout restart ds/cilium
```

One restart gotcha: the operator registers the egress policy custom resource. If the agents report `waiting for Cilium Operator to register CRD`, restart the operator too.

```bash
kubectl -n kube-system rollout restart deploy/cilium-operator
```

### 2. Pin the egress IP on the gateway node

The worker node is the gateway, because it attaches to the border leaf pair that reaches the firewall. Give its fabric interface, bond0, a second address, 10.0.51.100. That address is the identity the firewall will match.

```bash
# on the worker node
ip address add 10.0.51.100/24 dev bond0
```

### 3. Steer that address to the firewall

By default the node sends everything out its out-of-band interface, which does not reach the firewall. Only 10.0.51.100 should go over the fabric. A policy route does that: a rule that matches the source address and a dedicated table whose default route points at the fabric gateway, 10.0.51.1.

```bash
# on the worker node
ip rule add from 10.0.51.100 lookup 100
ip route add default via 10.0.51.1 dev bond0 table 100
```

Now the split is clean. Traffic sourced from 10.0.51.100 follows table 100 to the firewall. Everything else the node sends, including its management traffic, keeps the out-of-band default and never touches the firewall. Persist both the address and the rule in the node's network configuration so they survive a reboot.

### 4. Write the egress policy

The `CiliumEgressGatewayPolicy` ties it together: which pods it selects, which node is the gateway, and which source IP to use. This selects pods labeled `app: egress-demo`, routes their internet-bound traffic through the worker, and sources it from 10.0.51.100.

```yaml
apiVersion: cilium.io/v2
kind: CiliumEgressGatewayPolicy
metadata:
  name: app-via-firewall
spec:
  selectors:
    - podSelector:
        matchLabels:
          app: egress-demo
  destinationCIDRs:
    - 0.0.0.0/0
  excludedCIDRs:
    - 10.0.0.0/8              # keep fabric-internal traffic off the gateway
    - 192.168.255.0/24        # keep out-of-band traffic off the gateway
  egressGateway:
    nodeSelector:
      matchLabels:
        kubernetes.io/hostname: k8s-worker
    egressIP: 10.0.51.100
```

The `excludedCIDRs` matter. Without them, pod-to-pod traffic inside the fabric and the cluster's own management traffic would also be pulled through the gateway and masqueraded, which breaks both. The policy should only catch traffic actually leaving for the internet.

## Verify

Apply the policy, run a pod that matches the label, and send it to the internet.

```bash
kubectl apply -f egress-policy.yaml
kubectl run egress-app --image=busybox --labels app=egress-demo \
  --restart=Never -it --rm -- ping -c 4 8.8.8.8
```

On the firewall, read the translation table. The app's traffic appears sourced from 10.0.51.100, not from a node address or a pod CIDR.

```
show xlate | include 10.0.51.100
! ICMP PAT from inside:10.0.51.100 to outside:<edge-address> ...
```

That one line is the proof. The app's packets reach the firewall carrying 10.0.51.100, so a firewall rule keyed on 10.0.51.100 governs the app. Move the pod to the other node, restart it, scale it: the egress identity does not change, because it belongs to the gateway, not the pod.

<div class="callout callout-warning">
<strong>This path proves control, not throughput.</strong>
The firewall in this lab runs unlicensed, which caps its forwarding at roughly 100 Kbps. That is enough to prove the app egresses through the firewall as 10.0.51.100 and that a rule governs it. It is not a path for bulk traffic. Telemetry and other high-volume flows stay on the out-of-band network, which the policy deliberately excludes.
</div>

<div class="callout">
<strong>On automation.</strong>
The intended way to apply the node-side policy route and the Cilium policy is network as code, alongside the rest of the cluster config. That path is a work in progress and does not yet apply cleanly to the current topology, so the CLI above is the source of truth for now.
</div>
