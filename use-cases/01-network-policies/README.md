# Use case 1: Network policies

Default-deny a namespace, then open exactly the paths the app needs. Start at
L3/L4 (the network and transport layers), move to L7 (the application layer),
by HTTP (Hypertext Transfer Protocol) method and path, then add two things only
Cilium can do: DNS-aware egress (DNS, the Domain Name System) and a cluster-wide
guardrail.

Cilium enforces policy in eBPF (extended Berkeley Packet Filter) at the pod's network interface, so this works
the same whether the two pods share a node or sit on nodes behind different
leaves in the fabric.

## What it shows

- Default-deny: once a pod is selected by any policy, anything not explicitly
  allowed is dropped.
- L3/L4 segmentation by pod identity, not IP address.
- L7 HTTP filtering: allow `GET /api/...`, and everything else gets a 403 from
  the proxy, not the app.
- DNS-aware egress with `toFQDNs`: allow one external name and nothing else.
- A cluster-wide deny that holds across every namespace.

Two of the policies are standard Kubernetes `NetworkPolicy` (portable across any
CNI, Container Network Interface); the rest are `CiliumNetworkPolicy` and one `CiliumClusterwideNetworkPolicy`,
which add the L7, DNS, and cluster-wide behavior that standard policy cannot
express.

## The demo app

One small Python app in [`app/`](app/), standard library only, run as three
tiers through the `ROLE` env var: a `frontend` with a tiny web UI, a
`backend` that answers any `GET` with 200, and a `database`
stand-in that just holds its port open. Because the backend answers everything,
a 403 you see later is the policy talking, not the app.

Build it and make it reachable by the cluster before you apply anything:

```bash
docker build -t connectivity-tester:latest app/
# then make the image available to your cluster: push it to a registry the
# cluster can pull from, or load it onto the nodes with your tooling.
```

## Manifests

Apply them in order. Each step changes exactly one thing.

| File | Kind | Purpose |
|------|------|---------|
| `00-demo-app.yaml` | Namespace, Deployments, Services | The `demo` namespace and the three tiers. |
| `01-default-deny.yaml` | NetworkPolicy | Select all pods in `demo`, drop all ingress and egress. |
| `02-dns-allow.yaml` | NetworkPolicy | Allow egress to CoreDNS on 53, so names resolve again. |
| `03-l4-allow.yaml` | CiliumNetworkPolicy | Allow `frontend` to reach `backend` on TCP 8081. |
| `04-l7-allow.yaml` | CiliumNetworkPolicy | Narrow the backend rule to HTTP `GET /api/...` only. |
| `05-fqdn-egress.yaml` | CiliumNetworkPolicy | Allow the frontend to reach `api.github.com:443` and nothing else outside. |
| `06-clusterwide-deny.yaml` | CiliumClusterwideNetworkPolicy | Deny every pod egress to the link-local metadata address. |

The policy YAML here is original to this repo.

## Run it

```bash
kubectl apply -f 00-demo-app.yaml
kubectl -n demo rollout status deploy/frontend deploy/backend deploy/database

# run curl from inside the frontend pod and print just the HTTP status
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

The frontend also serves a web UI. Run `kubectl -n demo port-forward deploy/frontend 8080:8080` and open `http://localhost:8080` to drive the same checks from buttons. Under default-deny you must also allow ingress to the frontend to reach the UI; the curl checks above need only the egress rules.

## Verify

```bash
kubectl get networkpolicies -n demo            # the Kubernetes NetworkPolicies (01, 02)
kubectl get ciliumnetworkpolicies -n demo      # the CiliumNetworkPolicies (03, 04, 05)
kubectl get ciliumclusterwidenetworkpolicies   # the cluster-wide policy (06)
cilium policy get
```

Watch the verdicts land in [use case 2](../02-hubble/):
`hubble observe --namespace demo --verdict DROPPED`.

## A note on the cluster-wide rule

`06-clusterwide-deny.yaml` is a portable pattern worth keeping in any cluster.
A `CiliumClusterwideNetworkPolicy` with an empty `endpointSelector` applies to
every pod in every namespace, and a deny rule always wins, so it is a baseline
guardrail that one namespace's allow rules cannot undo.
