terraform {
  # The netascode nac-nxos module calls a provider-defined function
  # (provider::utils::render_device_configs), which needs Terraform >= 1.9.
  # This folder is pinned to 1.9.8 via .terraform-version (tfenv); the other
  # repo roots stay on the global 1.5.7.
  required_version = ">= 1.9.0"

  # Local state on purpose. This project is decoupled from the lab-environment
  # Terraform and rebuilds self-contained on this machine; the state file
  # stays in this folder and is gitignored (*.tfstate*). No remote/blob.
  backend "local" {}

  required_providers {
    # Native NX-OS provider (NX-API / DME). Talks straight to each switch, no
    # Nexus Dashboard. Pinned to the range the nac-nxos v0.3.0 module requires.
    nxos = {
      source  = "CiscoDevNet/nxos"
      version = "~> 0.13.1"
    }
    # Pulled in by the nac-nxos module: render_device_configs lives here.
    utils = {
      source  = "netascode/utils"
      version = ">= 2.0.0"
    }
    local = {
      source  = "hashicorp/local"
      version = ">= 2.7.0"
    }
  }
}
