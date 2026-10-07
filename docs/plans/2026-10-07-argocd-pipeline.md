# Argo CD GitOps Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up Argo CD in the kind/Cilium cluster and have it reconcile a demo app from this repo, pull-based, nothing inbound.

**Architecture:** One Argo CD install in the `argocd` namespace, bootstrapped once by a script on the kind host. A single app-of-apps root Application directory-recurses `gitops/apps/` and applies every manifest there. Today that is one demo app (namespace, Deployment of 2 replicas spread one-per-node, Service).

**Tech Stack:** Argo CD v3.5.4, Kubernetes manifests, bash, kubectl. Repo is public GitHub `itsAmeMario0o/BRKDCN-2982`.

## Global Constraints

- Public repo: no secrets, no live addresses, placeholder values only.
- Pull-based, no inbound: Argo pulls GitHub outbound; the public repo needs no credential.
- Argo CD pinned to `v3.5.4`; install manifest `https://raw.githubusercontent.com/argoproj/argo-cd/v3.5.4/manifests/install.yaml`.
- Bash style (teaching consistency with the operational repo): `set -euo pipefail`, `main "$@"` at the bottom, `[OK]`/`[WARN]`/`[FAIL]` output, quote every variable.
- Cluster node names: `cilium-control-plane`, `cilium-worker`. The operator reaches the kind host via their own transport (the operational repo's SSH jump); this public repo records no addresses or credentials.
- Ponytail: one Argo, one root app, one demo app. No extra Argo machinery.

---

### Task 1: Demo app manifests

**Files:**
- Create: `gitops/apps/demo/namespace.yaml`
- Create: `gitops/apps/demo/deployment.yaml`
- Create: `gitops/apps/demo/service.yaml`

**Interfaces:**
- Produces: a `demo` namespace; a Deployment named `demo` (label `app: demo`, 2 replicas, anti-affinity on `kubernetes.io/hostname`); a ClusterIP Service `demo` on port 80. Task 2's root app applies all three by directory recursion.

- [ ] **Step 1: Write `gitops/apps/demo/namespace.yaml`**

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: demo
```

- [ ] **Step 2: Write `gitops/apps/demo/deployment.yaml`**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: demo
  namespace: demo
  labels:
    app: demo
spec:
  replicas: 2
  selector:
    matchLabels:
      app: demo
  template:
    metadata:
      labels:
        app: demo
    spec:
      affinity:
        podAntiAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            - labelSelector:
                matchLabels:
                  app: demo
              topologyKey: kubernetes.io/hostname
      containers:
        - name: web
          image: nginx:1.27-alpine
          ports:
            - containerPort: 80
          resources:
            requests:
              cpu: 10m
              memory: 16Mi
            limits:
              cpu: 100m
              memory: 64Mi
```

- [ ] **Step 3: Write `gitops/apps/demo/service.yaml`**

```yaml
apiVersion: v1
kind: Service
metadata:
  name: demo
  namespace: demo
  labels:
    app: demo
spec:
  selector:
    app: demo
  ports:
    - port: 80
      targetPort: 80
```

- [ ] **Step 4: Validate the manifests parse and are schema-valid**

Run (on any host with kubectl; the kind host is guaranteed to have it):
`kubectl apply --dry-run=client -f gitops/apps/demo/`
Expected: three lines ending `(dry run)` — `namespace/demo`, `deployment.apps/demo`, `service/demo`, no errors.

- [ ] **Step 5: Commit (local only)**

```bash
git add gitops/apps/demo/
git commit -m "feat(gitops): demo app manifests (ns, deployment, service)"
```

---

### Task 2: App-of-apps root Application

**Files:**
- Create: `gitops/bootstrap/root-app.yaml`

**Interfaces:**
- Consumes: the manifests under `gitops/apps/` from Task 1.
- Produces: an Argo CD `Application` named `root` in namespace `argocd`, tracking `gitops/apps` on `main` with recursion and automated prune + self-heal. Task 3's `install.sh` applies this file.

- [ ] **Step 1: Write `gitops/bootstrap/root-app.yaml`**

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: root
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/itsAmeMario0o/BRKDCN-2982
    targetRevision: main
    path: gitops/apps
    directory:
      recurse: true
  destination:
    server: https://kubernetes.default.svc
    namespace: default
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

- [ ] **Step 2: Validate it parses as an Argo Application**

Run: `kubectl apply --dry-run=client -f gitops/bootstrap/root-app.yaml`
Expected: either `application.argoproj.io/root created (dry run)` if the CRD is present, or an error that the resource mapping is unknown (acceptable before Argo is installed — it confirms the YAML parses). A YAML syntax error is a failure; a missing-CRD message is not.

- [ ] **Step 3: Commit (local only)**

```bash
git add gitops/bootstrap/root-app.yaml
git commit -m "feat(gitops): app-of-apps root Application"
```

---

### Task 3: Bootstrap script

**Files:**
- Create: `gitops/bootstrap/install.sh`

**Interfaces:**
- Consumes: `root-app.yaml` from Task 2 (applied from the script's own directory).
- Produces: a runnable one-shot installer. No outputs other than cluster state.

- [ ] **Step 1: Write `gitops/bootstrap/install.sh`**

```bash
#!/usr/bin/env bash
# Bootstrap Argo CD into the kind cluster and hand it this repo to reconcile.
# Run once on the kind host. Idempotent. Public repo, so no credential is needed.
set -euo pipefail

ARGOCD_VERSION="v3.5.4"
INSTALL_URL="https://raw.githubusercontent.com/argoproj/argo-cd/${ARGOCD_VERSION}/manifests/install.yaml"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

main() {
  kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -
  # Server-side apply: the applicationsets CRD is larger than the 256KB
  # client-side last-applied annotation limit, so plain apply rejects it.
  kubectl apply --server-side -n argocd -f "${INSTALL_URL}"
  kubectl -n argocd rollout status deploy/argocd-repo-server --timeout=180s
  kubectl -n argocd rollout status deploy/argocd-server --timeout=180s
  kubectl apply -f "${SCRIPT_DIR}/root-app.yaml"
  echo "[OK] Argo CD ${ARGOCD_VERSION} installed; root app applied."
  echo "[OK] Watch: kubectl -n argocd get applications"
}

main "$@"
```

- [ ] **Step 2: Make it executable**

Run: `chmod +x gitops/bootstrap/install.sh`

- [ ] **Step 3: Static-check the script**

Run: `bash -n gitops/bootstrap/install.sh && shellcheck gitops/bootstrap/install.sh`
Expected: no output from either (clean). If `shellcheck` is not installed, `bash -n` alone must pass.

- [ ] **Step 4: Commit (local only)**

```bash
git add gitops/bootstrap/install.sh
git commit -m "feat(gitops): Argo CD bootstrap script (pinned v3.5.4)"
```

---

### Task 4: Push, bootstrap, and verify end to end

**Files:** none created. This task pushes the three commits and runs the pipeline.

**Interfaces:**
- Consumes: everything from Tasks 1-3, plus a running kind cluster `cilium` the operator can reach.

- [ ] **Step 1: Confirm with the operator, then push to the public repo**

Pushing publishes to a public repo. Get an explicit yes first, then:
```bash
git push origin main
```
Expected: the three commits land on `origin/main`.

- [ ] **Step 2: Bootstrap Argo CD on the kind host**

On the kind host (reached via the operator's own transport), clone the public
repo fresh and run the bootstrap:
```bash
rm -rf ~/BRKDCN-2982 && git clone https://github.com/itsAmeMario0o/BRKDCN-2982 ~/BRKDCN-2982
cd ~/BRKDCN-2982/gitops/bootstrap && ./install.sh
```
Expected: ends with `[OK] Argo CD v3.5.4 installed; root app applied.`

- [ ] **Step 3: Verify Argo and the demo app converge**

Run: `kubectl -n argocd get applications` then `kubectl -n demo get deploy,pods -o wide`
Expected: application `root` shows `Synced` / `Healthy`; two `demo` pods `Running`, one on `cilium-control-plane` and one on `cilium-worker`.

- [ ] **Step 4: Verify self-heal (drift reverts)**

Run: `kubectl -n demo scale deploy/demo --replicas=1` then wait and re-check `kubectl -n demo get deploy demo`
Expected: within a short interval the Deployment is back to `2/2` without manual action.

- [ ] **Step 5: Verify a Git change reconciles without kubectl**

In the repo, add a label to the demo Deployment, commit, and push (same publish confirmation as Step 1):
```yaml
# gitops/apps/demo/deployment.yaml -> metadata.labels
    app: demo
    demo.lab/managed-by: argocd
```
```bash
git add gitops/apps/demo/deployment.yaml
git commit -m "test(gitops): prove reconcile — add managed-by label"
git push origin main
```
Run: `kubectl -n demo get deploy demo -o jsonpath='{.metadata.labels}'`
Expected: the live Deployment carries `demo.lab/managed-by: argocd`, applied by Argo, no manual `kubectl`.

- [ ] **Step 6: Optional fabric re-proof (only if the fabric is up)**

Get a demo pod IP (`kubectl -n demo get pods -o wide`), then from the `red` endpoint:
`curl -s -m 5 http://<demo-pod-ip>:80 | head -1`
Expected: nginx's default page first line. Proves pod CIDRs reach the fabric as EVPN Type-5.

---

## Notes

- The real schema validation of the manifests happens when Argo syncs (Task 4);
  the `--dry-run=client` checks in Tasks 1-2 are local sanity only.
- `install.sh` is idempotent: re-running re-applies the same pinned objects.
- Secrets never enter this repo. The bootstrap needs no token because the repo
  is public and the cluster pulls outbound.
