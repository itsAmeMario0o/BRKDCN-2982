# The nac-nxos module owns the nxos provider and reads credentials from the
# NXOS_USERNAME / NXOS_PASSWORD environment variables, so there is no provider
# block or password variable here. Set, and never put in a file:
#
#   export NXOS_USERNAME=admin
#   export NXOS_PASSWORD="$LAB_PASSWORD"

variable "switch_urls" {
  description = "Per-device NX-API URL, keyed by device name (spine1, spine2, leaf1..leaf4). Supply real values via a gitignored terraform.tfvars; never commit real endpoints."
  type        = map(string)
}

variable "managed_devices" {
  description = "Which switches the apply touches. Defaults to all; narrow it (for example [\"leaf1\"]) to stage a change on one switch first."
  type        = list(string)
  default     = ["spine1", "spine2", "leaf1", "leaf2", "leaf3", "leaf4"]
}
