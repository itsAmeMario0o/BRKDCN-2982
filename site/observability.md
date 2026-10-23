---
layout: default
title: Observability
permalink: /observability/
eyebrow: Operate
summary: Two signals reach Splunk: cluster logs and metrics through an OpenTelemetry Collector, and network flows through Hubble. A policy drop then has a visible answer and a history.
---

## Two signals to Splunk

The cluster sends two signals to Splunk, and together they answer two different questions. Cluster logs and metrics answer "what is the cluster doing?" Network flows answer "what is talking to what, and did policy allow it?" Both signals use one pipeline into Splunk, and both arrive under their own index and sourcetype so a search can separate them.

The second signal connects the observability layer to the rest of the lab. Hubble observes the same extended Berkeley Packet Filter (eBPF) datapath that enforces network policy, so a drop you configured on the [use cases]({{ '/use-cases/' | relative_url }}) page shows up here as a dropped flow. The enforcement and the evidence come from the same place.

<figure class="diagram" role="img" aria-label="Two signals leave the Kubernetes cluster and reach Splunk. The Splunk OpenTelemetry Collector runs as a per-node agent plus a cluster receiver and sends logs and metrics to the Splunk HTTP Event Collector. Separately, a Hubble exporter Deployment runs hubble observe and writes flow JSON to its standard output, which the same OpenTelemetry log pipeline carries to the HTTP Event Collector. Hubble Relay and Hubble UI stay inside the cluster for a live service map.">
<svg viewBox="0 0 660 330" style="max-width:100%;height:auto">
  <defs>
    <marker id="ob-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M0 0 L10 5 L0 10 z" fill="currentColor"/>
    </marker>
  </defs>
  <rect x="20" y="30" width="400" height="285" rx="8" fill="none" stroke="currentColor" stroke-width="1" opacity="0.5"/>
  <text x="34" y="50" font-size="11" fill="currentColor" opacity="0.7">Kubernetes cluster</text>
  <g font-size="11" fill="currentColor">
    <rect x="44" y="64" width="160" height="60" rx="6" fill="none" stroke="currentColor" stroke-width="1.2"/>
    <text x="124" y="86" text-anchor="middle">OTel Collector</text>
    <text x="124" y="102" text-anchor="middle" opacity="0.75">DaemonSet agent</text>
    <text x="124" y="116" text-anchor="middle" opacity="0.75">+ cluster receiver</text>
    <rect x="44" y="172" width="160" height="62" rx="6" fill="none" stroke="currentColor" stroke-width="1.2"/>
    <text x="124" y="194" text-anchor="middle">Hubble exporter</text>
    <text x="124" y="210" text-anchor="middle" opacity="0.75">Deployment,</text>
    <text x="124" y="224" text-anchor="middle" opacity="0.75">hubble observe -&gt; stdout</text>
    <rect x="252" y="118" width="150" height="62" rx="6" fill="none" stroke="#02C8FF" stroke-width="1.4"/>
    <text x="327" y="140" text-anchor="middle" fill="#02C8FF">OTel log pipeline</text>
    <text x="327" y="156" text-anchor="middle" opacity="0.75">one HEC token,</text>
    <text x="327" y="170" text-anchor="middle" opacity="0.75">both signals</text>
    <rect x="44" y="258" width="160" height="42" rx="6" fill="none" stroke="currentColor" stroke-width="1" opacity="0.7"/>
    <text x="124" y="279" text-anchor="middle" opacity="0.85">Hubble Relay + UI</text>
    <text x="124" y="293" text-anchor="middle" font-size="10" opacity="0.7">local service map</text>
  </g>
  <rect x="486" y="118" width="150" height="62" rx="6" fill="none" stroke="currentColor" stroke-width="1.3"/>
  <text x="561" y="146" text-anchor="middle" font-size="11" fill="currentColor">Splunk HEC</text>
  <text x="561" y="163" text-anchor="middle" font-size="11" fill="currentColor" opacity="0.75">index k8s</text>
  <g stroke="currentColor" stroke-width="1.3" fill="none">
    <line x1="204" y1="94" x2="252" y2="132" marker-end="url(#ob-arrow)"/>
    <line x1="204" y1="203" x2="252" y2="166" marker-end="url(#ob-arrow)"/>
  </g>
  <line x1="402" y1="149" x2="486" y2="149" stroke="#02C8FF" stroke-width="1.5" fill="none" marker-end="url(#ob-arrow)"/>
  <g font-size="10" fill="currentColor" opacity="0.85">
    <text x="214" y="112">logs, metrics</text>
    <text x="214" y="192">flow JSON</text>
  </g>
  <text x="408" y="140" font-size="10" fill="#02C8FF">HTTP to :8088</text>
</svg>
<figcaption>Two signals, one pipeline. The OpenTelemetry Collector sends logs and metrics, and the Hubble exporter writes flow JSON to standard output that the same log pipeline (cyan) carries. Only the Collector holds the HTTP Event Collector token. Hubble Relay and the UI stay inside the cluster.</figcaption>
</figure>

## Cluster logs and metrics

The Splunk OpenTelemetry (OTel) Collector handles the first signal. The Collector runs as a DaemonSet, one agent pod on every node, plus a separate cluster receiver for cluster-wide objects. The agent collects each node's container logs and node and pod metrics; the cluster receiver collects events and the state of Kubernetes objects.

Everything it gathers goes to the Splunk HTTP Event Collector (HEC), the token-authenticated HTTP endpoint that Splunk exposes for ingest. The Collector is the only component that holds the HEC token.

## Network flows

The second signal comes from Hubble, the flow-visibility layer built into the Cilium container network interface (CNI). Because Cilium forwards and filters with eBPF, it already processes every packet, and Hubble turns that into a stream of flow records. Each record includes the source and destination identity, the port, and the policy verdict, so a flow is not just "A reached B" but "A reached B, and policy allowed it" or "policy dropped it."

A small exporter Deployment turns that stream into something the pipeline can carry. The Deployment runs:

```bash
hubble observe --follow -o jsonpb
```

That command streams every flow as JSON on standard output. The exporter writes nothing else and keeps no token. Its standard output is container log lines, so the OTel agent already tailing that node picks them up and carries them over the same pipeline into Splunk. One token, in the Collector, covers both signals.

<div class="callout">
<strong>Why the exporter holds no secret.</strong>
The flow records reach Splunk as ordinary container logs, not as a second direct push. The exporter only prints; the OTel agent does the sending. This arrangement keeps the HEC token in one place and leaves nothing sensitive in the exporter's configuration.
</div>

## Hubble locally

Flows are also useful without leaving the cluster. Hubble Relay aggregates the per-node flow streams into one cluster-wide view. Hubble UI draws a live service map from that view, the graph of which workload is talking to which, and updates it as traffic moves.

Reach the UI with a port-forward rather than exposing a service:

```bash
kubectl -n kube-system port-forward svc/hubble-ui 12000:80
# then open http://localhost:12000
```

## In Splunk

The flows arrive under their own sourcetype, separate from the cluster logs, so a search targets them directly. A dashboard reads that sourcetype and shows three things: the verdict breakdown, FORWARDED against DROPPED; the verdicts over time; and the top talkers, the identities generating the most flows.

A verdict count is a one-line search:

```spl
index=k8s sourcetype=cilium:hubble:flows
| stats count by verdict
```

The flow records connect the policy to its evidence. When use case 1 applies a network policy that blocks `demo/frontend` from reaching `demo/database`, that blocked attempt appears here as a DROPPED flow between those two identities. The policy you wrote and the drop you can see are the same event, observed from the eBPF datapath that enforced it.

## A policy drop, end to end

The question operators ask is "why was this blocked?" The answer is visible here. The datapath that enforces policy is the datapath that Hubble observes, so a drop is never a guess; it is a flow record with a verdict and the two identities on it. Hubble UI shows it live, and Splunk keeps the history, so the same answer is there an hour later when someone asks what happened.

## Verify

```bash
# the OTel agents and cluster receiver are running
kubectl -n kube-system get pods -l app.kubernetes.io/name=splunk-otel-collector

# Hubble Relay is up and the exporter is streaming
kubectl -n kube-system get pods -l k8s-app=hubble-relay
kubectl -n kube-system get pods -l k8s-app=hubble-exporter

# flows are arriving in Splunk, broken down by verdict
#   index=k8s sourcetype=cilium:hubble:flows
#   | stats count by verdict

# the live service map, through a port-forward
kubectl -n kube-system port-forward svc/hubble-ui 12000:80
```

If the verdict search returns both FORWARDED and DROPPED counts, both halves are proven: the OTel pipeline is carrying flows, and the eBPF datapath is reporting its policy decisions through to Splunk.
