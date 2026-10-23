# Use case 2: Hubble observability

**Turn on Hubble and watch the flows**: every connection, every policy
verdict, and a live service map, without touching the application.

Hubble is Cilium's observability layer. It reads the same eBPF (extended Berkeley
Packet Filter) data path that enforces policy in use case 1, so "why was this
dropped?" has an answer you can see rather than guess.

## What Hubble needs

Hubble is not separate infrastructure. It is `hubble-relay` and `hubble-ui`,
two small pods, enabled on the Cilium install you already have. Any cluster
running Cilium can run it, it is light on resources, and the lab VM has plenty
of headroom. The only thing you set up is a way to reach the UI from your
workstation (a port-forward or an SSH tunnel), the same pattern the other lab
UIs use.

## Key features

- Flow visibility: source/destination identity, port, protocol, verdict.
- The policy verdict on every flow, so the use case 1 drops show up as `DROPPED`.
- The Hubble UI service map: a live graph of who talks to whom.

## Enable it

```bash
cilium hubble enable --ui
cilium status | grep -i hubble        # wait for Hubble: OK and hubble-ui: OK
```

Install the Hubble CLI if you don't have it (one-time, on the control-plane
node). The nodes have no `go`, so pick the architecture with `uname -m` rather
than `go env`:

```bash
HUBBLE_ARCH=amd64; [ "$(uname -m)" = "aarch64" ] && HUBBLE_ARCH=arm64
HUBBLE_VERSION=$(curl -s https://raw.githubusercontent.com/cilium/hubble/master/stable.txt)
curl -L --fail --remote-name-all \
  https://github.com/cilium/hubble/releases/download/${HUBBLE_VERSION}/hubble-linux-${HUBBLE_ARCH}.tar.gz{,.sha256sum}
sha256sum --check hubble-linux-${HUBBLE_ARCH}.tar.gz.sha256sum
sudo tar xzf hubble-linux-${HUBBLE_ARCH}.tar.gz -C /usr/local/bin
rm hubble-linux-${HUBBLE_ARCH}.tar.gz{,.sha256sum}
hubble version
```

Then point the CLI at the relay:

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
