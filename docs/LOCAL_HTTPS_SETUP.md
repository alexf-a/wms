# Local HTTPS Setup Guide

This guide explains how to test the WMS app locally in production mode (`DEBUG=False`) with HTTPS using Caddy as a reverse proxy. This setup allows you to test HTTPS-only features (secure cookies, HSTS, SSL redirects) without deploying to production.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Detailed Setup](#detailed-setup)
- [Mobile Device Access](#mobile-device-access)
- [Network Changes](#network-changes)
- [Troubleshooting](#troubleshooting)
- [Cleanup](#cleanup)

## Prerequisites

- Docker and Docker Compose installed
- Poetry for Python dependency management
- macOS (instructions are macOS-specific for some commands)

## Quick Start

```bash
# 1. Create HTTPS environment file
cp .env.local.https.example .env.local.https

# 2. Update LOCAL_IP in .env.local.https
# Find your IP: ipconfig getifaddr en0
# Edit .env.local.https and replace 192.168.x.x with your actual IP

# 3. Add domain to /etc/hosts
sudo sh -c 'echo "127.0.0.1 dev.wms.local" >> /etc/hosts'

# 4. Fill in database and AWS credentials in .env.local.https
# Copy from .env.local or deploy/containers.json

# 5. Start the HTTPS server
make local-https

# 6. Access the app
# Desktop: https://dev.wms.local:8443
# Mobile: https://192.168.68.54:8443 (after installing CA - see below)
```

## Detailed Setup

### 1. Environment Configuration

Create your HTTPS environment file:

```bash
cp .env.local.https.example .env.local.https
```

Edit `.env.local.https` and configure:

- **LOCAL_IP**: Your Mac's local network IP address
  ```bash
  # Find your IP address:
  ipconfig getifaddr en0  # Wi-Fi
  ipconfig getifaddr en1  # Ethernet
  ```
  
- **Database credentials**: Copy from your `.env.local` or `deploy/containers.json`
- **AWS credentials**: Copy from your `.env.local` or `deploy/containers.json`

**Important**: Ensure `DEBUG=False` is set in the file. This is required for production mode testing.

### 2. Add Domain to /etc/hosts

The local domain `dev.wms.local` needs to resolve to localhost:

```bash
sudo sh -c 'echo "127.0.0.1 dev.wms.local" >> /etc/hosts'
```

To verify the entry was added:

```bash
grep dev.wms.local /etc/hosts
```

You should see: `127.0.0.1 dev.wms.local`

### 3. Start the Local HTTPS Server

```bash
make local-https
```

On first run, this will:
- Validate your environment configuration
- Check for the `/etc/hosts` entry (warns if missing)
- Build and start the Docker containers
- Automatically install Caddy's root CA certificate on your Mac
- Start both the Django app and Caddy reverse proxy

### 4. Access the Application

**Desktop Browser:**
- Navigate to: `https://dev.wms.local:8443`
- You should not see any certificate warnings (CA was installed automatically)

**Mobile Device:**
- See the [Mobile Device Access](#mobile-device-access) section below

## Mobile Device Access

To access the HTTPS site from your phone or tablet on the same network, you need to install Caddy's root CA certificate on your mobile device.

### Export the CA Certificate

```bash
make caddy-export-ca
```

This will:
1. Extract the Caddy root CA certificate to `deploy/caddy-root-ca.crt`
2. Generate a QR code (both PNG file and ASCII in terminal)
3. Print installation instructions

### iOS Installation

1. **Scan the QR code** displayed in your terminal, or visit `http://192.168.68.54:8000/caddy-ca/download` in Safari
2. A popup will appear asking to download the configuration profile - tap **Allow**
3. Go to **Settings → General → VPN & Device Management**
4. Tap the **Caddy Local Authority** profile
5. Tap **Install** (you may need to enter your passcode)
6. Tap **Install** again to confirm
7. Go to **Settings → General → About → Certificate Trust Settings**
8. Enable full trust for **Caddy Local Authority Root**
9. Tap **Continue** to confirm

Now you can visit `https://192.168.68.54:8443` in Safari without certificate warnings.

### Android Installation

1. **Scan the QR code** displayed in your terminal, or visit `http://192.168.68.54:8000/caddy-ca/download` in Chrome
2. Download the `caddy-root-ca.crt` file
3. Go to **Settings → Security → Encryption & credentials**
4. Tap **Install a certificate** or **Install from storage**
5. Select **CA certificate**
6. Navigate to and select the downloaded `caddy-root-ca.crt` file
7. Name it **Caddy Local CA** and tap **OK**

Now you can visit `https://192.168.68.54:8443` in Chrome without certificate warnings.

## Network Changes

When you switch networks (e.g., from Wi-Fi to Ethernet, or to a different Wi-Fi network), your local IP address changes.

### Update LOCAL_IP

1. Find your new IP address:
   ```bash
   ipconfig getifaddr en0  # Wi-Fi
   ipconfig getifaddr en1  # Ethernet
   ```

2. Edit `.env.local.https` and update:
   - `LOCAL_IP=192.168.x.x` (new IP)
   - `ALLOWED_HOSTS=dev.wms.local,localhost,192.168.x.x` (new IP)
   - `CSRF_TRUSTED_ORIGINS=https://dev.wms.local:8443,https://localhost:8443,https://192.168.x.x:8443` (new IP)

3. Restart the server:
   ```bash
   make local-https-down
   make local-https
   ```

4. Re-export the CA certificate for mobile devices:
   ```bash
   make caddy-export-ca
   ```

## Troubleshooting

### Certificate Warnings in Browser

**Desktop:**
- Check if Caddy CA is trusted: Run `make caddy-trust` again
- Try clearing browser cache and hard refresh

**Mobile:**
- Ensure you completed all trust steps (especially iOS Certificate Trust Settings)
- Reinstall the CA certificate

### Port Already in Use

If ports 8080 or 8443 are already in use:

```bash
# Check what's using the ports
lsof -i :8080
lsof -i :8443

# Stop any conflicting services or use docker-compose down to stop Caddy
```

### /etc/hosts Entry Not Working

Verify the entry exists and is correct:

```bash
grep dev.wms.local /etc/hosts
```

Should show: `127.0.0.1 dev.wms.local`

If incorrect, edit manually:
```bash
sudo nano /etc/hosts
```

### Caddy Volume Issues

If you see errors about missing CA certificate:

```bash
# Check if volume exists
docker volume ls | grep caddy_data

# If missing, Caddy will recreate it on next start
make local-https
```

If you deleted volumes with `docker-compose down -v`, you'll need to:
1. Remove the trust sentinel: `rm .caddy-trusted`
2. Restart and re-trust: `make local-https`
3. Re-export for mobile: `make caddy-export-ca`

### CA Certificate Extraction Fails

```bash
# Verify Caddy volume exists
docker volume inspect caddy_data

# Check if CA was generated
docker run --rm -v caddy_data:/data alpine find /data -name root.crt

# If path is different, update the Makefile or report an issue
```

### Django App Not Accessible

Check container status:
```bash
docker-compose ps
docker-compose logs web
docker-compose logs caddy
```

Verify containers are on the same network:
```bash
docker network inspect wms_wms-network
```

### Browser HSTS Cache Issues

If you previously accessed the site over HTTP and now can't access over HTTPS:

**Chrome/Edge:**
- Navigate to `chrome://net-internals/#hsts`
- Delete domain security policies for `dev.wms.local` and your local IP

**Firefox:**
- Clear browsing history, select "Everything" timeframe
- Check "Site Preferences" and "Active Logins"

**Safari:**
- Safari → Preferences → Privacy → Manage Website Data
- Search for `dev.wms.local` and remove

## Cleanup

To stop the HTTPS server and remove all artifacts:

```bash
make local-https-down
```

This will:
- Stop the Caddy and web containers
- Remove the trust sentinel (`.caddy-trusted`)
- Delete the exported CA certificate (`deploy/caddy-root-ca.crt`)
- Delete the QR code PNG (`deploy/caddy-ca-qr.png`)

**Note:** This does NOT remove:
- Docker volumes (Caddy data/config persist for faster restarts)
- The `/etc/hosts` entry
- CA certificates installed on your Mac or mobile devices

To completely reset:

```bash
# Remove everything
make local-https-down

# Remove Docker volumes
docker volume rm wms_caddy_data wms_caddy_config

# Uninstall Caddy CA from macOS (if desired)
# This will affect other Caddy instances
caddy untrust

# Remove /etc/hosts entry
sudo sed -i '' '/dev.wms.local/d' /etc/hosts

# Remove CA from mobile devices manually through device settings
```

## Additional Resources

- [Caddy Documentation](https://caddyserver.com/docs/)
- [Django Security Settings](https://docs.djangoproject.com/en/stable/topics/security/)
- [Docker Compose Networking](https://docs.docker.com/compose/networking/)

## Support

If you encounter issues not covered in this guide, check:
1. Docker daemon is running: `docker ps`
2. Poetry environment is active: `poetry env info`
3. All required environment variables are set in `.env.local.https`
4. Container logs: `docker-compose logs web caddy`
