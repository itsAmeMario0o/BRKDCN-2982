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
tiers through the `ROLE` env var: a `frontend` with a tiny web UI and a probe
endpoint, a `backend` that answers any `GET` with 200, and a `database`
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
kubectl -n demo rollout status deploy/backend deploy/frontend deploy/database

# a short alias for the probes, all run from inside the frontend pod
B="kubectl exec -n demo deploy/frontend -- curl -s --max-time 3"

# baseline, no policy yet: backend and the internet are reachable
$B http://backend:8081/api/health            # 200 ok
$B https://api.github.com | head -c 40        # reachable

kubectl apply -f 01-default-deny.yaml
$B http://backend:8081/api/health || echo "denied (expected): the name does not even resolve"

kubectl apply -f 02-dns-allow.yaml            # names resolve again, but TCP is still denied
kubectl apply -f 03-l4-allow.yaml
$B http://backend:8081/api/health            # 200 ok again

kubectl apply -f 04-l7-allow.yaml
$B http://backend:8081/api/health            # GET /api/... allowed
$B http://backend:8081/private || echo "L7 denied (403, expected)"

kubectl apply -f 05-fqdn-egress.yaml
$B https://api.github.com | head -c 40        # the one allowed name
$B https://example.com || echo "other names denied (expected)"

kubectl apply -f 06-clusterwide-deny.yaml     # metadata egress now denied cluster-wide
```

You can also open the frontend's web UI with a port-forward and click each
probe. To reach the UI under default-deny, allow ingress to the frontend as
well; the probes above need only the egress rules.

## Verify

```bash
kubectl get networkpolicies,ciliumnetworkpolicies -n demo
kubectl get ciliumclusterwidenetworkpolicies
cilium policy get
```

Watch the verdicts land in [use case 2](../02-hubble/):
`hubble observe --namespace demo --verdict DROPPED`.

## A note on the cluster-wide rule

`06-clusterwide-deny.yaml` is a portable pattern worth keeping in any cluster.
A `CiliumClusterwideNetworkPolicy` with an empty `endpointSelector` applies to
every pod in every namespace, and a deny rule always wins, so it is a baseline
guardrail that one namespace's allow rules cannot undo.
