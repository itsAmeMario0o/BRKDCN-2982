#!/usr/bin/env bash
# Bootstrap Argo CD into the kind cluster and hand it this repo to reconcile.
# Run once on the kind host. Idempotent. Public repo, so no credential is needed.
set -euo pipefail

ARGOCD_VERSION="v3.5.4"
INSTALL_URL="https://raw.githubusercontent.com/argoproj/argo-cd/${ARGOCD_VERSION}/manifests/install.yaml"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

main() {
  kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -
  kubectl apply -n argocd -f "${INSTALL_URL}"
  kubectl -n argocd rollout status deploy/argocd-repo-server --timeout=180s
  kubectl -n argocd rollout status deploy/argocd-server --timeout=180s
  kubectl apply -f "${SCRIPT_DIR}/root-app.yaml"
  echo "[OK] Argo CD ${ARGOCD_VERSION} installed; root app applied."
  echo "[OK] Watch: kubectl -n argocd get applications"
}

main "$@"
