# NX-OS single-AS VXLAN BGP EVPN underlay (netascode nac-nxos).
# Design: docs/decisions/0001-gitops-via-argocd.md, 0002-fabric-as-code-lives-here.md.
#
# The data model (underlay.nac.yaml) is the reference design and carries no
# device url. The six NX-API endpoints come from var.switch_urls and are merged
# in here, then passed to the module's inline `model` input. The module reads
# credentials from NXOS_USERNAME / NXOS_PASSWORD in the environment.

locals {
  base = yamldecode(file("${path.module}/underlay.nac.yaml"))
  model = {
    nxos = merge(local.base.nxos, {
      devices = [for d in local.base.nxos.devices : merge(d, { url = var.switch_urls[d.name] })]
    })
  }
}

module "nxos" {
  source  = "netascode/nac-nxos/nxos"
  version = "~> 0.3.0"

  model           = local.model
  managed_devices = var.managed_devices
}
