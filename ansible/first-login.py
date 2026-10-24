#!/usr/bin/env python3
"""Clear the firewall's forced first-login password change.

A fresh firewall built from day-0 has the 'ansible' user, but the firewall's
password policy makes an admin-created user change its password at first login.
That interactive prompt hangs Ansible. Run this once after a rebuild, before the
playbook. It completes the change with the same password (the policy allows it,
minimum-changes is 0), so the stored password does not move. If the firewall is
already past first login, it does nothing.

    ASA_PASSWORD=... ./.venv/bin/python first-login.py [host] [port]

Defaults: host 127.0.0.1, port 2222 (the local port-forward from the README).
Needs paramiko, which the venv already has.
"""
import os, sys, time, paramiko

host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
port = int(sys.argv[2]) if len(sys.argv) > 2 else 2222
pw = os.environ["ASA_PASSWORD"]

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(host, port=port, username="ansible", password=pw,
          look_for_keys=False, allow_agent=False, timeout=15)
ch = c.invoke_shell()
time.sleep(2)
buf = ch.recv(8192).decode(errors="replace")

if "old password" in buf.lower() or "first login" in buf.lower():
    def wait(substr, t=10):
        b = ""
        end = time.time() + t
        while time.time() < end:
            if ch.recv_ready():
                b += ch.recv(4096).decode(errors="replace")
                if substr.lower() in b.lower():
                    return
            time.sleep(0.3)
        raise SystemExit(f"did not see prompt {substr!r}")
    ch.send(pw + "\n")            # old
    wait("new password"); ch.send(pw + "\n")   # new == old
    wait("new password"); ch.send(pw + "\n")   # confirm
    time.sleep(2)
    print("forced password change cleared")
else:
    print("no forced change pending; nothing to do")
c.close()
