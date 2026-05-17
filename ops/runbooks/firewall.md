# Runbook — Origin firewall (Cloudflare IPs only)

Implements NFR-SEC-009 and SP-7 (origin firewall).

## Why

Origin VPS should not be reachable from any non-Cloudflare IP on ports 80/443. SSH is allowed only from a Tailscale subnet.

## Initial setup

```bash
# Fetch CF IPv4 and IPv6 ranges.
curl -s https://www.cloudflare.com/ips-v4 -o cf-v4.txt
curl -s https://www.cloudflare.com/ips-v6 -o cf-v6.txt

# Apply via Hetzner Cloud Firewall (terraform/hcloud API).
# Allow: 22/tcp from <tailscale subnet>; 80,443/tcp from CF ranges; deny all else.
```

## Automation

Cron daily (`/etc/cron.daily/cf-refresh`):

```bash
#!/usr/bin/env bash
set -euo pipefail
DIFF=$(diff -q <(curl -s https://www.cloudflare.com/ips-v4) /etc/cf/v4 || true)
if [ -n "$DIFF" ]; then
  curl -s https://www.cloudflare.com/ips-v4 > /etc/cf/v4
  curl -s https://www.cloudflare.com/ips-v6 > /etc/cf/v6
  /usr/local/bin/hcloud-firewall-sync.sh # uses hcloud API to update rules
fi
```

## Verification

```bash
# From a non-CF IP this MUST fail:
curl --connect-timeout 3 -I https://<origin-ip>/  # expect connection refused or timeout

# From Cloudflare (i.e., via the public domain) this MUST succeed:
curl -I https://nds-lab.example/
```
