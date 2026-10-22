---
layout: default
title: BRKDCN-2982 Workshop
permalink: /
# The hero below renders the H1 and lede on the home page, so the layout's
# standard page-header would only duplicate them.
hide_page_header: true
---

<section class="hero">
  <p class="eyebrow">A build-it-yourself fabric lab</p>
  <h1>Nexus <span class="gradient-text">&amp; Isovalent</span> Workshop</h1>
  <p class="lede">This workshop builds a VXLAN (Virtual Extensible LAN) BGP (Border Gateway Protocol) EVPN (Ethernet VPN) fabric in one autonomous system (AS) on Nexus switches, stands a Kubernetes cluster beside it, and lets Cilium advertise pod networks directly into the fabric over BGP. The design adds no tunnel to the host and no static routes. A pod address becomes an ordinary prefix in the fabric's routing table.</p>
  <div class="actions">
    <a class="btn btn-primary" href="{{ '/architecture/' | relative_url }}">How it fits together</a>
    <a class="btn btn-secondary" href="{{ '/underlay/' | relative_url }}">Start the build</a>
    <a class="btn btn-ghost" href="https://github.com/{{ site.repo.owner }}/{{ site.repo.name }}">View on GitHub</a>
  </div>
  <hr class="rule-gradient hero-rule">
</section>

{% include overview-diagram.html %}

## What you will build

You build a data center fabric and a cluster that speak the same routing language.

The fabric is four leaves and two spines, all in one BGP autonomous system (65400). The spines act as route-reflectors. The leaves are VXLAN tunnel endpoints (VTEPs) with a distributed anycast gateway, so a host keeps the same default gateway no matter which leaf it attaches to. Two leaves form a vPC (virtual Port Channel) pair and share an anycast VTEP, so the pair looks like one next hop to the rest of the fabric.

Beside the fabric sits a Kubernetes cluster running Cilium as its CNI (Container Network Interface), with kube-proxy replaced and the BGP control plane turned on. The cluster is its own autonomous system (65001). Each node peers eBGP with the leaf that it attaches to, advertises its pod CIDR, and the leaf re-originates that prefix as an EVPN Type-5 route. The spines then reflect the route, and every tunnel endpoint can reach the pod across VXLAN.

Everything here is code: a Terraform data model for the underlay, an Ansible data model for the overlay, Cilium CRDs (custom resource definitions) for the peering, and a GitOps and CI (continuous integration) pipeline that keeps everything applied.

## The prefix's journey, in one picture

The point of the whole lab is a single path. A pod address leaves the cluster as plain BGP and arrives on every tunnel endpoint as an EVPN route. The cluster carries no EVPN configuration.

```
pod (10.244.x.0/24)
  -> Cilium BGP control plane on the node
  -> eBGP to the node's leaf (cluster AS 65001 -> fabric AS 65400)
  -> leaf imports the prefix into the tenant VRF
  -> leaf re-originates it as an EVPN Type-5 (IP prefix) route
  -> spines reflect it to every other leaf
  -> any VTEP can now route to the pod across VXLAN
```

The leaf is the seam: BGP IPv4 unicast faces the cluster, and `l2vpn evpn` faces the fabric.

## Follow the build

<ul class="card-grid">
  <li>
    <a class="card card-interactive" href="{{ '/architecture/' | relative_url }}">
      <span class="card-kicker">01 · Plan</span>
      <span class="card-title">Architecture</span>
      <p>The single-AS design, the roles each switch plays, and why a leaf can turn a BGP prefix into an EVPN route.</p>
    </a>
  </li>
  <li>
    <a class="card card-interactive" href="{{ '/underlay/' | relative_url }}">
      <span class="card-kicker">02 · Build</span>
      <span class="card-title">The underlay</span>
      <p>Terraform brings up the switches and the iBGP underlay that bootstraps loopback reachability with no IGP (interior gateway protocol).</p>
    </a>
  </li>
  <li>
    <a class="card card-interactive" href="{{ '/overlay/' | relative_url }}">
      <span class="card-kicker">03 · Build</span>
      <span class="card-title">The overlay and vPC</span>
      <p>Ansible lays the l2vpn evpn overlay, the tenant VRF (virtual routing and forwarding), anycast gateways, and the vPC leaf pair, device-direct.</p>
    </a>
  </li>
  <li>
    <a class="card card-interactive" href="{{ '/cilium-bgp/' | relative_url }}">
      <span class="card-kicker">04 · Peer</span>
      <span class="card-title">Cilium BGP</span>
      <p>The cluster becomes its own AS and advertises pod CIDRs into the leaves, which re-originate them as Type-5.</p>
    </a>
  </li>
  <li>
    <a class="card card-interactive" href="{{ '/use-cases/' | relative_url }}">
      <span class="card-kicker">05 · Show</span>
      <span class="card-title">Use cases</span>
      <p>Three worked demos: network policy, Hubble observability, and the end-to-end pod reachability across the fabric.</p>
    </a>
  </li>
  <li>
    <a class="card card-interactive" href="{{ '/pipeline/' | relative_url }}">
      <span class="card-kicker">06 · Operate</span>
      <span class="card-title">The pipeline</span>
      <p>Argo CD pulls the cluster manifests; a self-hosted runner applies the fabric. Both start from this repo.</p>
    </a>
  </li>
</ul>

## Read and run it anywhere

This repository is the portable source of truth for the fabric-as-code and its pipeline. The repository carries no secrets and no live addresses. The committed data models are the reference design, with placeholder endpoints. The operator supplies real device addresses and credentials at run time, so the lab reads and runs against any fabric that matches the design, not just one environment.

<div class="callout">
<strong>What you need to run the lab for real.</strong>
You need six Nexus switches reachable over NX-API (NX-OS API), a Kubernetes cluster running Cilium with the BGP control plane enabled, and <code>kubectl</code>, the <code>cilium</code> CLI (command-line interface), Terraform, and Ansible on your path. Use cases 1 and 2 run on any Cilium cluster; use case 3 requires the fabric underneath. See <a href="{{ '/underlay/' | relative_url }}">the underlay page</a> to begin.
</div>
