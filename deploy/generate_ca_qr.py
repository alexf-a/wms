#!/usr/bin/env python3
# ruff: noqa: T201
"""Generate QR code for Caddy CA certificate download.

This script generates a QR code that mobile devices can scan to download
the Caddy root CA certificate for trusting local HTTPS connections.

Usage:
    python deploy/generate_ca_qr.py --cert-path deploy/caddy-root-ca.crt --env-file .env.local.https
"""

import argparse
import sys
from pathlib import Path


def parse_env_file(env_file_path: Path) -> dict[str, str]:
    """Parse environment file and return key-value pairs.

    Args:
        env_file_path: Path to the .env file.

    Returns:
        Dictionary of environment variables.

    Raises:
        FileNotFoundError: If env file doesn't exist.
        ValueError: If LOCAL_IP is not found in env file.
    """
    if not env_file_path.exists():
        raise FileNotFoundError(f"Environment file not found: {env_file_path}")

    env_vars = {}
    with open(env_file_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env_vars[key.strip()] = value.strip()

    if "LOCAL_IP" not in env_vars or not env_vars["LOCAL_IP"]:
        raise ValueError(
            f"LOCAL_IP not found or empty in {env_file_path}. "
            "Please set LOCAL_IP to your local network IP address."
        )

    return env_vars


def generate_qr_code(download_url: str, output_path: Path) -> None:
    """Generate QR code for the download URL.

    Args:
        download_url: URL to encode in the QR code.
        output_path: Path where PNG file will be saved.

    Raises:
        ImportError: If qrcode library is not installed.
    """
    try:
        import qrcode
    except ImportError as e:
        raise ImportError(
            "qrcode library not found. Install with: poetry add qrcode[pil]"
        ) from e

    # Generate QR code with terminal output
    qr = qrcode.QRCode()
    qr.add_data(download_url)
    qr.make()

    # Print ASCII QR code to terminal
    print("\n" + "=" * 60)
    print("Scan this QR code with your mobile device:")
    print("=" * 60)
    qr.print_ascii()
    print("=" * 60 + "\n")

    # Save PNG version
    try:
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(output_path)
        print(f"QR code saved to: {output_path}")
    except Exception as e:
        print(f"Warning: Failed to save PNG QR code: {e}", file=sys.stderr)
        print("ASCII QR code above can still be scanned from terminal.", file=sys.stderr)


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    parser = argparse.ArgumentParser(
        description="Generate QR code for Caddy CA certificate download"
    )
    parser.add_argument(
        "--cert-path",
        type=Path,
        required=True,
        help="Path to the Caddy root CA certificate file",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        required=True,
        help="Path to the environment file containing LOCAL_IP",
    )
    args = parser.parse_args()

    try:
        # Validate certificate file exists
        if not args.cert_path.exists():
            print(f"Error: Certificate file not found: {args.cert_path}", file=sys.stderr)
            print("\nRun 'make caddy-export-ca' to extract the certificate first.", file=sys.stderr)
            return 1

        # Parse environment file
        env_vars = parse_env_file(args.env_file)
        local_ip = env_vars["LOCAL_IP"]

        # Generate download URL
        download_url = f"http://{local_ip}:8000/caddy-ca/download"

        # Generate QR code
        output_path = args.cert_path.parent / "caddy-ca-qr.png"
        generate_qr_code(download_url, output_path)

        # Print instructions
        print("\n" + "=" * 60)
        print("Mobile CA Certificate Installation Instructions")
        print("=" * 60)
        print(f"\nDownload URL: {download_url}\n")
        print("iOS:")
        print("  1. Scan the QR code above or visit the URL in Safari")
        print("  2. Tap 'Allow' to download the configuration profile")
        print("  3. Go to Settings → General → VPN & Device Management")
        print("  4. Tap the downloaded profile and tap 'Install'")
        print("  5. Go to Settings → General → About → Certificate Trust Settings")
        print("  6. Enable full trust for the Caddy Local Authority certificate")
        print("\nAndroid:")
        print("  1. Scan the QR code above or visit the URL in Chrome")
        print("  2. Download the certificate file")
        print("  3. Go to Settings → Security → Install from storage")
        print("  4. Select the downloaded certificate file")
        print("  5. Name it 'Caddy Local CA' and tap OK")
        print("\n" + "=" * 60 + "\n")

        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except ImportError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
