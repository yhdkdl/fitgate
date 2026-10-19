"""
FitGate Staging Spike - cPanel UAPI Probe Script (uapi_probe.py).

This throwaway utility runs on the owner's computer inside the backend container:
  docker compose exec backend python deploy/spike/uapi_probe.py ...

Purpose:
  Validate cPanel UAPI token access and subdomain management functions:
  - SubDomain::listsubdomains
  - SubDomain::addsubdomain (with multi-level labels such as spike1.fitgate)
  - SubDomain::delsubdomain (with cleanup support)

Documentation Reference:
  - SubDomain::addsubdomain: https://docs.cpanel.net/b/uapi/subdomain-addsubdomain/
  - SubDomain::delsubdomain: https://docs.cpanel.net/b/uapi/subdomain-delsubdomain/
  - SubDomain::listsubdomains: https://docs.cpanel.net/b/uapi/subdomain-listsubdomains/

Environment Variables Required (NO DEFAULTS - fails fast if unset):
  - CPANEL_HOST: cPanel server hostname or IP (e.g. server.yegara.com or tebebtech.com)
  - CPANEL_USERNAME: cPanel account username
  - CPANEL_API_TOKEN: cPanel API token (never printed or logged)
"""

import argparse
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request


def get_cpanel_env():
    """Retrieve and validate cPanel credentials from environment with NO defaults."""
    host = os.environ.get("CPANEL_HOST")
    username = os.environ.get("CPANEL_USERNAME")
    token = os.environ.get("CPANEL_API_TOKEN")

    missing = []
    if not host or not host.strip():
        missing.append("CPANEL_HOST")
    if not username or not username.strip():
        missing.append("CPANEL_USERNAME")
    if not token or not token.strip():
        missing.append("CPANEL_API_TOKEN")

    if missing:
        sys.stderr.write(
            f"ERROR: Missing required environment variable(s): {', '.join(missing)}.\n"
            "Ensure these are set in your local .env file or container environment.\n"
            "Never commit or share API tokens.\n"
        )
        sys.exit(1)

    return host.strip(), username.strip(), token.strip()


def call_uapi(host, username, token, module, function, params=None):
    """
    Execute a cPanel UAPI call over HTTPS port 2083.

    Returns the parsed JSON response dictionary.
    Guarantees the API token is never exposed in output or exceptions.
    """
    params = params or {}
    encoded_params = urllib.parse.urlencode(params)
    url = f"https://{host}:2083/execute/{module}/{function}"

    if encoded_params:
        url = f"{url}?{encoded_params}"

    headers = {
        "Authorization": f"cpanel {username}:{token}",
        "User-Agent": "FitGate-UAPI-Probe/1.0",
        "Accept": "application/json",
    }

    req = urllib.request.Request(url, headers=headers, method="GET")

    # Use standard SSL verification context
    ctx = ssl.create_default_context()

    try:
        with urllib.request.urlopen(req, context=ctx, timeout=20) as resp:
            raw_body = resp.read().decode("utf-8")
            data = json.loads(raw_body)
            return data
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed_err = json.loads(err_body)
            return parsed_err
        except Exception:
            raise RuntimeError(
                f"cPanel HTTP {exc.code} {exc.reason}: {err_body}"
            ) from None
    except Exception as exc:
        raise RuntimeError(
            f"Network error communicating with cPanel UAPI at {host}:2083: {exc}"
        ) from None


def normalize_result(data):
    """Extract result dictionary and errors handling both top-level and nested cPanel formats."""
    # Some cPanel versions wrap output in {"result": {...}}, others place status at root
    result = data.get("result", data)
    status = result.get("status")
    errors = result.get("errors")
    messages = result.get("messages")
    warnings = result.get("warnings")
    payload = result.get("data")
    return status, payload, errors, messages, warnings


def list_subdomains(host, username, token):
    """List all subdomains currently configured on the cPanel account."""
    print(
        f"[*] Querying cPanel UAPI SubDomain::listsubdomains on {host} (user: {username})..."
    )
    data = call_uapi(host, username, token, "SubDomain", "listsubdomains")
    status, subdomains, errors, _, warnings = normalize_result(data)

    if status != 1:
        print(f"[!] FAILED: cPanel returned error status: {errors}")
        return False

    if warnings:
        print(f"[?] Warnings: {warnings}")

    if not subdomains:
        print("[-] No subdomains found on this cPanel account.")
        return True

    print(f"\n[+] Found {len(subdomains)} subdomain(s):")
    print(
        f"{'DOMAIN':<35} {'ROOT DOMAIN':<20} {'DOCUMENT ROOT':<35} {'DOMAIN KEY':<30}"
    )
    print("-" * 125)
    for sub in subdomains:
        domain = sub.get("domain", "")
        rootdomain = sub.get("rootdomain", "")
        doc_dir = sub.get("dir", sub.get("basedir", ""))
        domainkey = sub.get("domainkey", "")
        print(f"{domain:<35} {rootdomain:<20} {doc_dir:<35} {domainkey:<30}")
    print("-" * 125)
    return True


def add_subdomain(
    host, username, token, domain, rootdomain, doc_root=None, disallowdot=0
):
    """
    Create a subdomain via SubDomain::addsubdomain.

    Note on multi-level labels (e.g. spike1.fitgate under tebebtech.com):
    Per official cPanel docs:
      - 'domain' is the prefix (e.g. spike1.fitgate)
      - 'rootdomain' is the registered domain (e.g. tebebtech.com)
      - 'disallowdot=0' instructs cPanel to preserve dots in the subdomain label
      - 'dir' is the document root path (e.g. public_html/fitgate)
    """
    doc_root = doc_root or f"public_html/{domain}"
    fqdn = f"{domain}.{rootdomain}"
    print(f"[*] Adding subdomain '{fqdn}'...")
    print(f"    - Prefix (domain)     : {domain}")
    print(f"    - Parent (rootdomain) : {rootdomain}")
    print(f"    - Document Root (dir) : {doc_root}")
    print(
        f"    - disallowdot         : {disallowdot} (0 = allow dots for multi-level labels)"
    )

    params = {
        "domain": domain,
        "rootdomain": rootdomain,
        "dir": doc_root,
        "disallowdot": disallowdot,
    }

    data = call_uapi(host, username, token, "SubDomain", "addsubdomain", params)
    status, payload, errors, messages, warnings = normalize_result(data)

    if status == 1:
        print(f"[+] SUCCESS: Subdomain '{fqdn}' provisioned successfully!")
        if payload:
            print(f"    Result details: {payload}")
        if messages:
            print(f"    Messages: {messages}")
        return True
    else:
        print(f"[!] FAILED: Could not create subdomain '{fqdn}'.")
        print(f"    Errors: {errors}")
        if warnings:
            print(f"    Warnings: {warnings}")
        return False


def delete_subdomain(host, username, token, domain, disallowdot=0):
    """
    Delete a subdomain via SubDomain::delsubdomain.

    Per official cPanel docs:
      - 'domain' accepts the FQDN (e.g. spike1.fitgate.tebebtech.com) or domainkey
      - 'disallowdot=0' preserves dots in multi-level domain names
    """
    print(f"[*] Deleting subdomain '{domain}'...")
    params = {
        "domain": domain,
        "disallowdot": disallowdot,
    }

    data = call_uapi(host, username, token, "SubDomain", "delsubdomain", params)
    status, payload, errors, messages, warnings = normalize_result(data)

    if status == 1:
        print(f"[+] SUCCESS: Subdomain '{domain}' deleted successfully!")
        if messages:
            print(f"    Messages: {messages}")
        return True
    else:
        print(f"[!] FAILED: Could not delete subdomain '{domain}'.")
        print(f"    Errors: {errors}")
        if warnings:
            print(f"    Warnings: {warnings}")
        return False


def run_full_test(
    host, username, token, domain, rootdomain, doc_root=None, cleanup=False
):
    """Run an end-to-end probe: list -> add -> list -> (optional) delete."""
    print("=" * 60)
    print("  FitGate cPanel UAPI End-to-End Subdomain Probe Test")
    print("=" * 60)

    # 1. List before
    print("\n--- Phase 1: List existing subdomains ---")
    list_subdomains(host, username, token)

    # 2. Add
    print("\n--- Phase 2: Add test subdomain ---")
    created = add_subdomain(
        host, username, token, domain, rootdomain, doc_root, disallowdot=0
    )
    if not created:
        print("[!] Stopping test due to creation failure.")
        return False

    # 3. List after
    print("\n--- Phase 3: Verify subdomain appears in listing ---")
    list_subdomains(host, username, token)

    fqdn = f"{domain}.{rootdomain}"
    if cleanup:
        print("\n--- Phase 4: Cleanup (--cleanup requested) ---")
        deleted = delete_subdomain(host, username, token, fqdn, disallowdot=0)
        print("\n--- Phase 5: Final listing verification ---")
        list_subdomains(host, username, token)
        return deleted
    else:
        print(f"\n[NOTE] Subdomain '{fqdn}' left active for manual testing.")
        print("       To delete later, run:")
        print(
            f"       docker compose exec backend python deploy/spike/uapi_probe.py delete --domain {fqdn}"
        )
        return True


def main():
    parser = argparse.ArgumentParser(
        description="FitGate cPanel UAPI Subdomain Probe Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all subdomains:
  docker compose exec backend python deploy/spike/uapi_probe.py list

  # Add multi-level subdomain spike1.fitgate under tebebtech.com:
  docker compose exec backend python deploy/spike/uapi_probe.py add --domain spike1.fitgate --rootdomain tebebtech.com --dir public_html/fitgate

  # Delete subdomain:
  docker compose exec backend python deploy/spike/uapi_probe.py delete --domain spike1.fitgate.tebebtech.com

  # Run full test with automatic cleanup:
  docker compose exec backend python deploy/spike/uapi_probe.py test --domain spike1.fitgate --rootdomain tebebtech.com --dir public_html/fitgate --cleanup
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Command: list
    subparsers.add_parser("list", help="List all subdomains on the cPanel account")

    # Command: add
    parser_add = subparsers.add_parser("add", help="Add a new subdomain")
    parser_add.add_argument(
        "--domain",
        required=True,
        help="Subdomain prefix (e.g. spike1.fitgate or testgym)",
    )
    parser_add.add_argument(
        "--rootdomain",
        required=True,
        help="Parent root domain (e.g. tebebtech.com)",
    )
    parser_add.add_argument(
        "--dir",
        default=None,
        help="Document root folder (e.g. public_html/fitgate). Defaults to public_html/<domain>",
    )
    parser_add.add_argument(
        "--disallowdot",
        type=int,
        default=0,
        help="Whether to strip dots (0 = keep dots for multi-level subdomains, default 0)",
    )

    # Command: delete
    parser_del = subparsers.add_parser("delete", help="Delete an existing subdomain")
    parser_del.add_argument(
        "--domain",
        required=True,
        help="Full domain name to delete (e.g. spike1.fitgate.tebebtech.com)",
    )
    parser_del.add_argument(
        "--disallowdot",
        type=int,
        default=0,
        help="0 to allow dots in domain name (default 0)",
    )

    # Command: test
    parser_test = subparsers.add_parser(
        "test", help="Run end-to-end add, verify, and optional delete"
    )
    parser_test.add_argument(
        "--domain",
        default="spike1.fitgate",
        help="Subdomain prefix (default: spike1.fitgate)",
    )
    parser_test.add_argument(
        "--rootdomain",
        default="tebebtech.com",
        help="Parent root domain (default: tebebtech.com)",
    )
    parser_test.add_argument(
        "--dir",
        default=None,
        help="Document root folder (e.g. public_html/fitgate)",
    )
    parser_test.add_argument(
        "--cleanup",
        action="store_true",
        help="Delete the subdomain immediately after verifying creation",
    )

    # Also support top-level flags for convenience:
    parser.add_argument(
        "--list", action="store_true", help="Shortcut for 'list' command"
    )
    parser.add_argument(
        "--cleanup",
        dest="cleanup_target",
        help="Shortcut to delete a subdomain by name",
    )

    args = parser.parse_args()

    # Load credentials (fails fast if unset)
    host, username, token = get_cpanel_env()

    if args.list or args.command == "list":
        success = list_subdomains(host, username, token)
        sys.exit(0 if success else 1)
    elif args.cleanup_target:
        success = delete_subdomain(
            host, username, token, args.cleanup_target, disallowdot=0
        )
        sys.exit(0 if success else 1)
    elif args.command == "add":
        success = add_subdomain(
            host,
            username,
            token,
            args.domain,
            args.rootdomain,
            args.dir,
            args.disallowdot,
        )
        sys.exit(0 if success else 1)
    elif args.command == "delete":
        success = delete_subdomain(host, username, token, args.domain, args.disallowdot)
        sys.exit(0 if success else 1)
    elif args.command == "test":
        success = run_full_test(
            host,
            username,
            token,
            args.domain,
            args.rootdomain,
            args.dir,
            cleanup=args.cleanup,
        )
        sys.exit(0 if success else 1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
