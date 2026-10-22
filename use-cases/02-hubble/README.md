# Use case 2: Hubble observability

**Turn on Hubble and watch the flows** - every connection, every policy
verdict, and a live service map, without touching the application.

Hubble is Cilium's observability layer. It reads the same eBPF data path that
enforces policy in use case 1, so "why was this dropped?" has an answer you can
see rather than guess.

## Can this lab run Hubble? Yes.

Hubble is not separate infrastructure. It is `hubble-relay` and `hubble-ui` -
two small pods - enabled on the Cilium install you already have. Any cluster
running Cilium can run it, it is light on resources, and the lab VM has plenty
of headroom. The only thing you set up is a way to reach the UI from your
workstation (a port-forward or an SSH tunnel), the same pattern the other lab
UIs use.

## Key features

- Flow visibility: source/destination identity, port, protocol, verdict.
- The policy verdict on every flow - see the use case 1 drops as `DROPPED`.
- The Hubble UI service map: a live graph of who talks to whom.

## Enable it

```bash
cilium hubble enable --ui
cilium status | grep -i hubble        # wait for Hubble: OK and hubble-ui: OK
```

Install the Hubble CLI if you don't have it (one-time, on the node or your workstation):

```bash
cilium hubble port-forward &          # relay on localhost:4245
export HUBBLE_SERVER=localhost:4245
hubble status
```

## Run it

With the use case 1 app running and its policies applied:

```bash
# all flows in the demo namespace
hubble observe --namespace demo --follow

# just the drops - these line up with the L4/L7 denies from use case 1
hubble observe --namespace demo --verdict DROPPED --follow
```

The UI:

```bash
cilium hubble ui          # opens / prints the local URL; tunnel it from your workstation
```

## Verify

```bash
hubble status             # relay reachable, flows flowing
hubble observe --namespace demo --last 20
```
