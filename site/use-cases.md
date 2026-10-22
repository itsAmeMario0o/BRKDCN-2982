---
layout: default
title: Use cases
permalink: /use-cases/
eyebrow: Show
summary: Three worked use cases that run on top of the fabric. The first two run on any Cilium cluster; the third is the one this lab exists for.
---

Each use case is self-contained: a short summary, the features it shows, the manifests, and the commands to prove it works.

<ul class="card-grid">
  <li>
    <a class="card card-interactive" href="#use-case-1-network-policies">
      <span class="card-kicker">01</span>
      <span class="card-title">Network policies</span>
      <p>L3/L4 and L7 segmentation between pods with CiliumNetworkPolicy.</p>
    </a>
  </li>
  <li>
    <a class="card card-interactive" href="#use-case-2-hubble-observability">
      <span class="card-kicker">02</span>
      <span class="card-title">Hubble observability</span>
      <p>Flow visibility and a live service map with Hubble and the Hubble UI.</p>
    </a>
  </li>
  <li>
    <a class="card card-interactive" href="#use-case-3-cilium-bgp">
      <span class="card-kicker">03</span>
      <span class="card-title">Cilium BGP</span>
      <p>Pod CIDRs re-originated as EVPN Type-5 routes, reachable across the fabric.</p>
    </a>
  </li>
</ul>

Use case 3 is the reason the lab exists. Use cases 1 and 2 are things any Cilium cluster can do; use case 3 is what makes this a fabric lab rather than a single-cluster one. If you read only one, read that one.

<div class="callout">
<strong>Prerequisites.</strong>
All three assume the cluster is up: Cilium as the CNI (Container Network Interface) with kube-proxy replaced and the BGP (Border Gateway Protocol) control plane on, plus <code>kubectl</code> and the <code>cilium</code> CLI pointed at it. Use case 3 also needs the <a href="{{ '/underlay/' | relative_url }}">underlay</a> and <a href="{{ '/overlay/' | relative_url }}">overlay</a> converged.
</div>

## Use case 1: Network policies

Default-deny a namespace, then open exactly the paths the app needs, first at L3/L4 (the network and transport layers), then at L7 (the application layer), by HTTP (Hypertext Transfer Protocol) method and path.

Cilium enforces policy in eBPF (extended Berkeley Packet Filter) at the pod's network interface, so this works the same whether the two pods land on the same node or on nodes hanging off different leaves in the fabric.

**What it shows**

- Default-deny: once a pod is selected by any policy, anything not explicitly allowed is dropped.
- L3/L4 segmentation with `CiliumNetworkPolicy`, by pod identity rather than IP.
- L7 HTTP filtering: allow `GET /api/...`, and anything else gets a 403 from the proxy, not the app.
- DNS-aware egress (DNS, the Domain Name System) with `toFQDNs`: allow one external name and nothing else.
- A cluster-wide deny that holds across every namespace.

The first two policies are standard Kubernetes `NetworkPolicy`, portable across any CNI. The rest are `CiliumNetworkPolicy` and one `CiliumClusterwideNetworkPolicy`, which add the L7, DNS, and cluster-wide behavior standard policy cannot express.

**The demo app**

One small Python app (standard library only) runs as three tiers through a `ROLE` variable: a `frontend` with a web UI, a `backend` that answers any `GET` with 200, and a `database` stand-in. Build it and make it available to the cluster first: `docker build -t connectivity-tester:latest app/`, then push or load the image.

**Manifests**

| File | Kind | Purpose |
|------|------|---------|
| `00-demo-app.yaml` | Namespace, Deployments, Services | The `demo` namespace and the three tiers. |
| `01-default-deny.yaml` | NetworkPolicy | Select all pods in `demo`, drop all ingress and egress. |
| `02-dns-allow.yaml` | NetworkPolicy | Allow egress to CoreDNS on 53, so names resolve. |
| `03-l4-allow.yaml` | CiliumNetworkPolicy | Allow `frontend` to reach `backend` on TCP 8081. |
| `04-l7-allow.yaml` | CiliumNetworkPolicy | Narrow the backend rule to HTTP `GET /api/...`. |
| `05-fqdn-egress.yaml` | CiliumNetworkPolicy | Allow the frontend to reach `api.github.com:443` only. |
| `06-clusterwide-deny.yaml` | CiliumClusterwideNetworkPolicy | Deny every pod egress to the link-local metadata address. |

**Run it**

```bash
kubectl apply -f 00-demo-app.yaml
kubectl -n demo rollout status deploy/backend deploy/frontend deploy/database
```

Each policy changes what the frontend can reach. Apply them one at a time and watch the HTTP status code change. This helper runs curl inside the frontend pod and prints the status code it gets back:

```bash
fe() { kubectl exec -n demo deploy/frontend -- curl -s -o /dev/null -w "%{http_code}\n" --max-time 5 "$1"; }

fe http://backend:8081/api/health        # baseline: 200

kubectl apply -f 01-default-deny.yaml
fe http://backend:8081/api/health        # 000, blocked: the default-deny policy drops it

kubectl apply -f 02-dns-allow.yaml        # names resolve again
kubectl apply -f 03-l4-allow.yaml         # allow frontend to reach backend on 8081
fe http://backend:8081/api/health        # 200 again
fe http://database:5432/                  # 000, the database stays blocked

kubectl apply -f 04-l7-allow.yaml         # allow only GET /api/...
fe http://backend:8081/api/health        # 200
fe http://backend:8081/private            # 403, the Envoy proxy denies the path

kubectl apply -f 05-fqdn-egress.yaml
fe https://api.github.com/                # 200, the one allowed name
fe https://example.com/                   # 000, every other name is denied

kubectl apply -f 06-clusterwide-deny.yaml   # deny metadata egress cluster-wide
```

The frontend also serves a web UI. Run `kubectl -n demo port-forward deploy/frontend 8080:8080` and open `http://localhost:8080` to drive the same DNS, TCP, and HTTP checks from buttons.

**Verify**

```bash
kubectl get networkpolicies -n demo            # the Kubernetes NetworkPolicies (01, 02)
kubectl get ciliumnetworkpolicies -n demo      # the CiliumNetworkPolicies (03, 04, 05)
kubectl get ciliumclusterwidenetworkpolicies   # the cluster-wide policy (06)
```

Watch the verdicts land in use case 2: `hubble observe --namespace demo --verdict DROPPED`.

Source: [`use-cases/01-network-policies/`](https://github.com/{{ site.repo.owner }}/{{ site.repo.name }}/tree/{{ site.repo.branch }}/use-cases/01-network-policies).

## Use case 2: Hubble observability

Turn on Hubble and watch the flows: every connection, every policy verdict, and a live service map, without touching the application.

Hubble is Cilium's observability layer. It reads the same eBPF data path that enforces policy in use case 1, so "why was this dropped?" has an answer you can see rather than guess. Hubble is not extra infrastructure to stand up. It is `hubble-relay` and `hubble-ui`, two small pods you enable on the Cilium install you already have.

**Key features**

- Flow visibility: source and destination identity, port, protocol, and verdict.
- The policy verdict on every flow, so the use case 1 drops show up as `DROPPED`.
- The Hubble UI service map: a live graph of who talks to whom.

**Enable it**

```bash
cilium hubble enable --ui
cilium status | grep -i hubble        # wait for Hubble: OK and hubble-ui: OK
```

On a Helm-managed install, enable Hubble through Helm values instead (`hubble.relay.enabled=true`, `hubble.ui.enabled=true`), so a later `helm upgrade` does not revert it. `cilium hubble enable` edits the ConfigMap directly and Helm can undo it.

```bash
cilium hubble port-forward &          # relay on localhost:4245
export HUBBLE_SERVER=localhost:4245
hubble status
```

**Run it**

With the use case 1 app running and its policies applied:

```bash
# all flows in the demo namespace
hubble observe --namespace demo --follow

# just the drops, which line up with the L4/L7 denies from use case 1
hubble observe --namespace demo --verdict DROPPED --follow
```

The UI:

```bash
cilium hubble ui          # opens or prints the local URL; tunnel it from your workstation
```

**Verify**

```bash
hubble status             # relay reachable, flows flowing
hubble observe --namespace demo --last 20
```

Source: [`use-cases/02-hubble/`](https://github.com/{{ site.repo.owner }}/{{ site.repo.name }}/tree/{{ site.repo.branch }}/use-cases/02-hubble).

## Use case 3: Cilium BGP

Advertise pod CIDRs (Classless Inter-Domain Routing ranges) out of the cluster over eBGP (external BGP), let the leaves re-originate them as EVPN (Ethernet VPN) Type-5 routes, and reach a pod from anywhere on the physical fabric. This is the use case the lab is built for, and it has a page of its own: [Cilium BGP]({{ '/cilium-bgp/' | relative_url }}) walks through the three CRDs (custom resource definitions), the path a pod prefix takes, and the fabric-side verification.

```
pod (10.244.x.0/24)
  -> Cilium BGP control plane on the node
  -> eBGP to the node's leaf (cluster AS 65001 -> fabric AS 65400)
  -> leaf re-originates the prefix as an EVPN Type-5 route
  -> spines reflect it; any VTEP can route to the pod across VXLAN
```

Source: [`use-cases/03-cilium-bgp/`](https://github.com/{{ site.repo.owner }}/{{ site.repo.name }}/tree/{{ site.repo.branch }}/use-cases/03-cilium-bgp) and [`cilium/bgp.yaml`](https://github.com/{{ site.repo.owner }}/{{ site.repo.name }}/blob/{{ site.repo.branch }}/cilium/bgp.yaml).
