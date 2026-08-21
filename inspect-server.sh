#!/bin/bash
echo "===== SYSTEM ====="
hostname; uname -a; cat /etc/os-release 2>/dev/null | head -3
echo "Memory:"; free -h | head -2
echo "Disk:"; df -h / | tail -1
echo "Public IP:"; curl -s ifconfig.me 2>/dev/null || echo unknown

echo ""; echo "===== DOCKER ====="
docker --version 2>/dev/null || echo "NOT INSTALLED"
docker compose version 2>/dev/null || echo "Compose NOT INSTALLED"
echo "--- Running containers:"
docker ps --format "  {{.Names}}  {{.Image}}  {{.Ports}}  {{.Status}}" 2>/dev/null
echo "--- All containers:"
docker ps -a --format "  {{.Names}}  {{.Image}}  {{.Status}}" 2>/dev/null
echo "--- Networks:"
docker network ls 2>/dev/null

echo ""; echo "===== CADDY ====="
systemctl is-active caddy 2>/dev/null || echo "not running"
cat /etc/caddy/Caddyfile 2>/dev/null || echo "Caddyfile not found"

echo ""; echo "===== POSTGRESQL ====="
for c in $(docker ps -a --format '{{.Names}}' 2>/dev/null | grep -iE 'postgres|pg|n8n|db'); do
  echo "Container: $c"
  docker inspect "$c" --format '  Image: {{.Config.Image}}  Ports: {{range $k,$v := .NetworkSettings.Ports}}{{$k}}->{{range $v}}{{.HostPort}}{{end}} {{end}}' 2>/dev/null
done
systemctl is-active postgresql 2>/dev/null || echo "System PostgreSQL: not running"

echo ""; echo "===== N8N ====="
for c in $(docker ps -a --format '{{.Names}}' 2>/dev/null | grep -i n8n); do
  echo "Container: $c"
  docker inspect "$c" --format '  Image: {{.Config.Image}}  Status: {{.State.Status}}  Ports: {{range $k,$v := .NetworkSettings.Ports}}{{$k}}->{{range $v}}{{.HostPort}}{{end}} {{end}}' 2>/dev/null
done

echo ""; echo "===== PORTS IN USE ====="
ss -tlnp 2>/dev/null | grep LISTEN || netstat -tlnp 2>/dev/null | head -20

echo ""; echo "===== FIREWALL ====="
ufw status 2>/dev/null || iptables -L INPUT -n 2>/dev/null | head -15 || echo "no firewall info"

echo ""; echo "===== EXISTING PROJECT FILES ====="
for d in /opt/ai-sales-dashboard /home/*/ai-sales-dashboard /root/ai-sales-dashboard; do
  [ -d "$d" ] && echo "Found: $d" && ls "$d/" 2>/dev/null | head -10
done

echo ""; echo "===== DNS ====="
echo "app.eviraw.com -> $(dig +short app.eviraw.com 2>/dev/null || echo unknown)"
echo "api.eviraw.com -> $(dig +short api.eviraw.com 2>/dev/null || echo unknown)"
echo "n8n.eviraw.com -> $(dig +short n8n.eviraw.com 2>/dev/null || echo unknown)"

echo ""; echo "===== OUTBOUND ====="
curl -sf https://api.openai.com -o /dev/null && echo "OpenAI: OK" || echo "OpenAI: BLOCKED"
curl -sf https://graph.facebook.com -o /dev/null && echo "Meta: OK" || echo "Meta: BLOCKED"

echo ""; echo "===== SSL ====="
ls /etc/letsencrypt/live/ 2>/dev/null || echo "No Let's Encrypt certs"

echo ""; echo "===== DONE ====="
