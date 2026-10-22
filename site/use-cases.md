---
layout: default
title: Use cases
permalink: /use-cases/
eyebrow: Show
summary: Three worked use cases that run on top of the fabric. The first two run on any Cilium cluster; the third is the one this lab exists for.
---

Each use case is self-contained: a short summary, the features it shows, the manifests, and the commands to prove it worked.

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

Use case 3 is the headline. Use cases 1 and 2 are things any Cilium cluster can do; use case 3 is what makes this a fabric lab rather than a single-cluster one. Start there if you only read one.

<div class="callout">
<strong>Prerequisites.</strong>
All three assume the cluster is up: Cilium as the CNI with kube-proxy replaced and the BGP control plane on, plus <code>kubectl</code> and the <code>cilium</code> CLI pointed at it. Use case 3 also needs the <a href="{{ '/underlay/' | relative_url }}">underlay</a> and <a href="{{ '/overlay/' | relative_url }}">overlay</a> converged.
</div>

## Use case 1: Network policies

Default-deny a namespace, then open exactly the paths the app needs, first at L3/L4, then at L7 (HTTP method and path).

Cilium enforces policy in eBPF at the pod's network interface, so this works the same whether the two pods land on the same node or on nodes hanging off different leaves in the fabric.

**What it shows**

- Default-deny: once a pod is selected by any policy, anything not explicitly allowed is dropped.
- L3/L4 segmentation with `CiliumNetworkPolicy`, by pod identity rather than IP.
- L7 HTTP filtering: allow `GET /api/...`, and anything else gets a 403 from the proxy, not the app.
- DNS-aware egress with `toFQDNs`: allow one external name and nothing else.
- A cluster-wide deny that holds across every namespace.

The first two policies are standard Kubernetes `NetworkPolicy`, portable across any CNI. The rest are `CiliumNetworkPolicy` and one `CiliumClusterwideNetworkPolicy`, which add the L7, DNS, and cluster-wide behavior standard policy cannot express.

**The demo app**

One small Python app (standard library only) runs as three tiers through a `ROLE` variable: a `frontend` with a web UI and a probe endpoint, a `backend` that answers any `GET` with 200, and a `database` stand-in. Build it and make it available to the cluster first: `docker build -t connectivity-tester:latest app/`, then push or load the image.

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

The frontend serves a web UI with probe buttons. Forward it and drive the demo from a browser, re-testing after each policy:

```bash
kubectl -n demo port-forward deploy/frontend 8080:8080
# open http://localhost:8080 and run the DNS, TCP, and HTTP probes
```

To drive it from the CLI instead, call the frontend's `/check` endpoint. The image has no `curl`, so use its own Python. This helper returns a JSON verdict for each probe:

```bash
probe() { kubectl exec -n demo deploy/frontend -- \
  python -c "import urllib.request as u,sys;print(u.urlopen('http://localhost:8080/check?'+sys.argv[1]).read().decode())" "$1"; }

probe 'type=http&target=backend&port=8081&path=/api/health'   # baseline: ok, http 200

kubectl apply -f 01-default-deny.yaml
probe 'type=tcp&target=backend&port=8081'      # ok:false, blocked (DNS and TCP both denied)

kubectl apply -f 02-dns-allow.yaml             # names resolve again, TCP still denied
kubectl apply -f 03-l4-allow.yaml
probe 'type=http&target=backend&port=8081&path=/api/health'   # ok:true, http 200 again
probe 'type=tcp&target=database&port=5432'     # ok:false, database stays blocked

kubectl apply -f 04-l7-allow.yaml
probe 'type=http&target=backend&port=8081&path=/api/health'   # ok:true, GET /api/... allowed
probe 'type=http&target=backend&port=8081&path=/private'      # ok:false, http 403 from the proxy

kubectl apply -f 05-fqdn-egress.yaml
probe 'type=https&target=api.github.com&path=/'   # ok:true, the one allowed name
probe 'type=https&target=example.com&path=/'      # ok:false, other names denied

kubectl apply -f 06-clusterwide-deny.yaml      # metadata egress denied cluster-wide
```

**Verify**

```bash
kubectl get networkpolicies,ciliumnetworkpolicies -n demo
kubectl get ciliumclusterwidenetworkpolicies
```

Watch the verdicts land in use case 2: `hubble observe --namespace demo --verdict DROPPED`.

Source: [`use-cases/01-network-policies/`](https://github.com/{{ site.repo.owner }}/{{ site.repo.name }}/tree/{{ site.repo.branch }}/use-cases/01-network-policies).

## Use case 2: Hubble observability

Turn on Hubble and watch the flows: every connection, every policy verdict, and a live service map, without touching the application.

Hubble is Cilium's observability layer. It reads the same eBPF data path that enforces policy in use case 1, so "why was this dropped?" has an answer you can see rather than guess. It is not separate infrastructure. It is `hubble-relay` and `hubble-ui`, two small pods enabled on the Cilium install you already have.

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

Advertise pod CIDRs out of the cluster over eBGP, let the leaves re-originate them as EVPN Type-5 routes, and reach a pod from anywhere on the physical fabric. This is the use case the lab is built for, and it has a page of its own: [Cilium BGP]({{ '/cilium-bgp/' | relative_url }}) walks through the three CRDs, the path a pod prefix takes, and the fabric-side verification.

```
pod (10.244.x.0/24)
  -> Cilium BGP control plane on the node
  -> eBGP to the node's leaf (cluster AS 65001 -> fabric AS 65400)
  -> leaf re-originates the prefix as an EVPN Type-5 route
  -> spines reflect it; any VTEP can route to the pod across VXLAN
```

Source: [`use-cases/03-cilium-bgp/`](https://github.com/{{ site.repo.owner }}/{{ site.repo.name }}/tree/{{ site.repo.branch }}/use-cases/03-cilium-bgp) and [`cilium/bgp.yaml`](https://github.com/{{ site.repo.owner }}/{{ site.repo.name }}/blob/{{ site.repo.branch }}/cilium/bgp.yaml).
