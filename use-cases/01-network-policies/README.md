# Use case 1: Network policies

**Default-deny a namespace, then open exactly the paths the app needs** -
first at L3/L4, then at L7 (HTTP method and path).

Cilium enforces policy in eBPF at the pod's network interface, so this works
the same whether the two pods land on the same node or on nodes hanging off
different leaves in the fabric.

## Key features

- L3/L4 segmentation with `CiliumNetworkPolicy` (identity-based, not IP-based).
- L7 HTTP filtering: allow `GET /public`, deny everything else.
- Default-deny posture: once a pod is selected by any policy, everything not
  explicitly allowed is dropped.

## Manifests

| File | Purpose |
|------|---------|
| `00-demo-app.yaml` | Two deployments (`frontend`, `backend`) and a `backend` service in the `demo` namespace. |
| `01-default-deny.yaml` | An empty-ingress policy selecting all pods in `demo` - drops everything. |
| `02-l4-allow.yaml` | Allow `frontend` to reach `backend` on TCP 8080 only. |
| `03-l7-allow.yaml` | Narrow the same path to HTTP `GET /public`. |

> Manifests land here as the use case is built. The YAML follows the standard
> Cilium policy examples (Apache-2.0, from the Cilium docs); the prose and the
> fabric framing are ours.

## Run it

```bash
kubectl apply -f 00-demo-app.yaml
# baseline: frontend can reach backend
kubectl exec -n demo deploy/frontend -- curl -s backend:8080/public

kubectl apply -f 01-default-deny.yaml
# now it's dropped
kubectl exec -n demo deploy/frontend -- curl -s --max-time 3 backend:8080/public || echo "denied (expected)"

kubectl apply -f 02-l4-allow.yaml
# allowed again on 8080
kubectl exec -n demo deploy/frontend -- curl -s backend:8080/public

kubectl apply -f 03-l7-allow.yaml
# GET /public allowed, POST denied by L7
kubectl exec -n demo deploy/frontend -- curl -s backend:8080/public
kubectl exec -n demo deploy/frontend -- curl -s -XPOST --max-time 3 backend:8080/public || echo "L7 denied (expected)"
```

## Verify

```bash
cilium policy get
kubectl get ciliumnetworkpolicies -n demo
```

Watch the drops land in use case 2 (Hubble) - `hubble observe --namespace demo --verdict DROPPED`.
