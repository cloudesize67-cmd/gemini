"""
NOESIS Tunnel Setup
Cloudflare Tunnel (cloudflared) to expose NOESIS API to phone/mobile interface
"""

# ─── cloudflared tunnel config ───
# Save as: ~/.cloudflared/config.yml  (on your server)
# Requires: cloudflared installed + authenticated

CLOUDFLARED_CONFIG = """
tunnel: noesis-tunnel
credentials-file: /root/.cloudflared/noesis-tunnel.json

ingress:
  - hostname: noesis.your-domain.workers.dev
    service: http://localhost:8000
  - service: http_status:404
"""

# ─── GitHub Actions workflow to auto-start tunnel on deploy ───
GITHUB_ACTIONS_TUNNEL = """
name: NOESIS Deploy + Tunnel

on:
  push:
    branches: [claude/aegis-cognitive-framework-ic5Jo]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Start NOESIS server
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          NOESIS_HMAC_SECRET: ${{ secrets.NOESIS_HMAC_SECRET }}
          PORT: 8000
        run: |
          nohup python server.py &
          sleep 3
          curl http://localhost:8000/health

      - name: Install cloudflared
        run: |
          curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
          sudo dpkg -i cloudflared.deb

      - name: Start tunnel
        env:
          CLOUDFLARE_TUNNEL_TOKEN: ${{ secrets.CLOUDFLARE_TUNNEL_TOKEN }}
        run: |
          cloudflared tunnel --no-autoupdate run --token $CLOUDFLARE_TUNNEL_TOKEN
"""

# ─── Quick tunnel without Cloudflare account (dev/phone testing) ───
# Uses ngrok as fallback
NGROK_QUICKSTART = """
# Install ngrok: npm install -g ngrok  OR  pip install pyngrok

from pyngrok import ngrok
import subprocess
import time
import os

if __name__ == "__main__":
    # Start NOESIS server in background
    server = subprocess.Popen(["python", "server.py"])
    time.sleep(2)

    # Open ngrok tunnel
    ngrok.set_auth_token(os.environ.get("NGROK_AUTH_TOKEN", ""))
    tunnel = ngrok.connect(8000, "http")
    
    print(f"\\nNOESIS accessible at: {tunnel.public_url}")
    print(f"Dashboard: {tunnel.public_url}/dashboard")
    print(f"Analyze: POST {tunnel.public_url}/analyze")
    print(f"MCP endpoint: {tunnel.public_url}/mcp/analyze")
    print("\\nShare this URL with your phone for mobile access.")
    
    try:
        server.wait()
    except KeyboardInterrupt:
        server.terminate()
        ngrok.kill()
"""

print("Tunnel config module loaded.")
print("Options: cloudflared (production) or ngrok (dev/phone testing)")
