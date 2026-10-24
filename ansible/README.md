# Border firewall automation

The Nexus fabric is Terraform (see [`../terraform`](../terraform)). The border
firewall is not: it is a different platform, and the one Terraform provider that
targets it only reaches ACLs and static routes over an API Cisco has frozen, so
it cannot express this firewall's BGP or NAT. Ansible over SSH can, so the
firewall's own config lives here.

This owns only the firewall side of the seam. The leaf side (the eBGP to AS
65500 and the two `/30` links) is in the Terraform fabric.

## What the playbook manages

`firewall.yml` sets the firewall's data plane:

- the two inside links to the leaf pairs (`10.2.3.2/30`, `10.2.4.2/30`)
- the outside egress interface (DHCP from the lab out-of-band network)
- the tenant object and the egress source NAT behind the outside address
- a permit-any ACL applied globally (the open lab posture)
- BGP 65500 with one neighbor per leaf pair into the fabric AS 65400

## What it does not manage: the bootstrap

Ansible logs in over SSH, and it cannot build its own way in. The firewall's
management plane (a login user, aaa, ssh, host keys) has to exist before the
playbook runs. The lab wires this into the firewall node's day-0 config, so a
rebuilt firewall comes up reachable; the exact set is in
[`firewall-bootstrap.txt`](firewall-bootstrap.txt).

One wrinkle survives day-0: the firewall's password policy makes an
admin-created user change its password at first login, and that interactive
prompt hangs Ansible. Clear it once per rebuild with
[`first-login.py`](first-login.py), which completes the change with the same
password, before the playbook runs.

## Running it

The firewall's management address sits on the lab out-of-band network, so reach
it by forwarding a local port to it through the lab host:

```bash
# localhost:2222 -> firewall management address, through the lab host
ssh -i <lab-key> -p 1122 -L 127.0.0.1:2222:<firewall-oob-ip>:22 -N <lab-host>
```

The playbook reads the firewall user's password from the environment, so it is
never stored in the repo:

```bash
cd ansible
export ASA_PASSWORD="<the ansible user's password>"   # the lab keeps this as ASA_ANSIBLE_PASSWORD
./.venv/bin/python first-login.py          # once per rebuild; no-op after
./.venv/bin/ansible-playbook firewall.yml
```

On a freshly rebuilt lab the order is: bring up the port-forward, run
`first-login.py` once to clear the forced password change, then run the
playbook. On a firewall that is already up, `first-login.py` reports nothing to
do and you can skip straight to the playbook.

`inventory.yml` points at `127.0.0.1:2222` (the forward) and names the host
`firewall`. The venv at `ansible/.venv` is gitignored; it holds `ansible-core`,
the `cisco.asa` collection, and `paramiko` for the SSH transport.

## Idempotency

The playbook is idempotent: a run against a firewall that already matches
reports `changed=0`, and a run against one that has drifted restores the config
and then reports `changed=0` on the next pass. That is the same prove-it bar the
Terraform fabric holds to.
