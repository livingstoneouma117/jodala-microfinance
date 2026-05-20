# Deploy SACCOFinance with Your Domain (Ubuntu + Nginx + Gunicorn)

This guide deploys the current Flask app (`app.py`) from this project.

## 1) Point your domain to the server

Create DNS records at your domain registrar:

- `A` record: `@` -> `YOUR_SERVER_PUBLIC_IP`
- `CNAME` record: `www` -> `@`

Wait for propagation (usually a few minutes, sometimes up to 24 hours).

## 2) SSH into your Ubuntu server

```bash
ssh ubuntu@YOUR_SERVER_PUBLIC_IP
```

## 3) Install system packages

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx
```

## 4) Upload project to server

On your local machine:

```bash
scp -r "C:/Users/USER/OneDrive/Desktop/jodala chama" ubuntu@YOUR_SERVER_PUBLIC_IP:/opt/jodala-chama
```

On the server:

```bash
cd /opt/jodala-chama
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 5) Set production environment variables

```bash
sudo mkdir -p /etc/jodala
sudo tee /etc/jodala/jodala.env >/dev/null << 'EOF'
SECRET_KEY=REPLACE_WITH_A_LONG_RANDOM_SECRET
JWT_EXP_HOURS=24
JWT_ALGORITHM=HS256
DB_PATH=/opt/jodala-chama/sacco.db
PORT=5000
DEBUG=false
EOF
```

Generate a secure secret value:

```bash
python3 - << 'PY'
import secrets
print(secrets.token_urlsafe(64))
PY
```

## 6) Create systemd service

```bash
sudo tee /etc/systemd/system/jodala-chama.service >/dev/null << 'EOF'
[Unit]
Description=Jodala Chama Flask App (Gunicorn)
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/jodala-chama
EnvironmentFile=/etc/jodala/jodala.env
ExecStart=/opt/jodala-chama/.venv/bin/gunicorn --workers 3 --bind 127.0.0.1:5000 app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo chown -R www-data:www-data /opt/jodala-chama
sudo systemctl daemon-reload
sudo systemctl enable jodala-chama
sudo systemctl start jodala-chama
sudo systemctl status jodala-chama --no-pager
```

## 7) Configure Nginx for your domain

Replace `yourdomain.com` with your real domain.

```bash
sudo tee /etc/nginx/sites-available/jodala-chama >/dev/null << 'EOF'
server {
    listen 80;
    listen [::]:80;
    server_name yourdomain.com www.yourdomain.com;

    client_max_body_size 20M;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

sudo ln -s /etc/nginx/sites-available/jodala-chama /etc/nginx/sites-enabled/jodala-chama
sudo nginx -t
sudo systemctl reload nginx
```

## 8) Enable HTTPS (Let's Encrypt)

Use Certbot (Nginx plugin):

```bash
sudo snap install --classic certbot
sudo ln -s /snap/bin/certbot /usr/local/bin/certbot
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
sudo certbot renew --dry-run
```

## 9) Open firewall (if UFW is enabled)

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
sudo ufw status
```

## 10) Verify

```bash
curl -I http://yourdomain.com
curl -I https://yourdomain.com
curl https://yourdomain.com/api/health
```

Expected health response includes JSON with `"status":"ok"`.

## Operational notes

- App logs:
  - `sudo journalctl -u jodala-chama -f`
- Nginx logs:
  - `/var/log/nginx/access.log`
  - `/var/log/nginx/error.log`
- Restart after changes:
  - `sudo systemctl restart jodala-chama`

## What was updated in this project for production

- `auth.py`: JWT secret/algorithm/expiry now read from env vars.
- `database.py`: SQLite path now reads `DB_PATH` env var.
- `app.py`: debug mode now reads `DEBUG` env var.
- `requirements.txt`: added Gunicorn.
