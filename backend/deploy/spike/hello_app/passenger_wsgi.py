"""
FitGate Staging Spike - Minimal WSGI Verification App (passenger_wsgi.py).

This throwaway application runs under cPanel Python App Manager (Phusion Passenger)
to verify hosting capabilities before deploying the production Django application.

Checks performed on each request:
1. Host header (HTTP_HOST)
2. X-Forwarded-Host and X-Forwarded-Proto headers
3. HTTPS status (direct SSL, proxy header, server port)
4. Python version and executable path
5. Current working directory and script directory
6. Filesystem write permissions in the application folder
7. Outbound HTTPS connectivity to https://api.cloudinary.com
8. Outbound TCP connectivity to SMTP host and port (configurable via query string)
9. Optional PostgreSQL connection test (configurable via query string)
"""

import os
import socket
import sys
import time
import urllib.parse
import urllib.request


def check_filesystem_write(target_dir):
    """Test creating, writing to, reading, and deleting a temporary file in target_dir."""
    test_filename = os.path.join(
        target_dir, f"_spike_write_test_{int(time.time())}.tmp"
    )
    try:
        test_payload = f"FitGate spike write check at {time.ctime()}\n"
        with open(test_filename, "w", encoding="utf-8") as f:
            f.write(test_payload)
        with open(test_filename, "r", encoding="utf-8") as f:
            read_back = f.read()
        os.remove(test_filename)
        if read_back == test_payload:
            return "SUCCESS: Wrote, verified, and removed temporary file in application folder."
        return "WARNING: File was written but read-back content did not match."
    except Exception as exc:
        return f"FAILED: Unable to write to folder ({target_dir}): {exc}"


def check_outbound_https(url="https://api.cloudinary.com", timeout=5):
    """Test outbound HTTPS connectivity to an external API (e.g. Cloudinary)."""
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "FitGate-Spike-WSGI/1.0"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return f"SUCCESS: Outbound HTTPS to {url} reachable (HTTP {response.status} {response.reason})."
    except urllib.error.HTTPError as exc:
        # HTTP errors (like 401 or 404) still prove SSL handshake and outbound networking succeed
        return f"SUCCESS: Outbound HTTPS connected to {url} (HTTP {exc.code} {exc.reason})."
    except Exception as exc:
        return f"FAILED: Outbound HTTPS to {url} failed: {exc}"


def check_tcp_connect(host, port, timeout=5):
    """Test TCP socket connection to a remote host and port (e.g. SMTP server)."""
    try:
        port_num = int(port)
    except (ValueError, TypeError):
        return f"FAILED: Invalid port '{port}' specified."

    try:
        start_time = time.time()
        with socket.create_connection((host, port_num), timeout=timeout):
            elapsed_ms = int((time.time() - start_time) * 1000)
            return f"SUCCESS: Connected to {host}:{port_num} via TCP in {elapsed_ms}ms."
    except socket.timeout:
        return f"FAILED: Connection to {host}:{port_num} timed out after {timeout}s (firewall likely blocking outbound port)."
    except ConnectionRefusedError:
        return f"FAILED: Connection to {host}:{port_num} refused by destination."
    except Exception as exc:
        return f"FAILED: TCP connection to {host}:{port_num} error: {exc}"


def check_postgresql(db_params):
    """Test connecting to PostgreSQL using psycopg (v3) or psycopg2 if credentials are provided."""
    db_name = db_params.get("db_name")
    if not db_name:
        # Check if driver packages are available in this environment
        drivers = []
        try:
            import psycopg  # noqa: F401

            drivers.append("psycopg (v3)")
        except ImportError:
            pass
        try:
            import psycopg2  # noqa: F401

            drivers.append("psycopg2")
        except ImportError:
            pass

        if drivers:
            return f"DRIVERS AVAILABLE: {', '.join(drivers)}. Pass ?db_name=...&db_user=...&db_pass=... to test live connection."
        return "NO POSTGRES DRIVER: Neither psycopg (v3) nor psycopg2 is installed in this Python environment."

    driver_name = None
    connect_func = None
    try:
        import psycopg

        driver_name = "psycopg (v3)"
        connect_func = psycopg.connect
    except ImportError:
        try:
            import psycopg2

            driver_name = "psycopg2"
            connect_func = psycopg2.connect
        except ImportError:
            return "FAILED: Cannot test PostgreSQL connection; neither psycopg nor psycopg2 is installed."

    host = db_params.get("db_host", "localhost")
    port = int(db_params.get("db_port", 5432))
    user = db_params.get("db_user", "")
    password = db_params.get("db_pass", "")

    try:
        conn = connect_func(
            host=host,
            port=port,
            dbname=db_name,
            user=user,
            password=password,
            connect_timeout=5,
        )
        cur = conn.cursor()
        cur.execute("SELECT version();")
        version_row = cur.fetchone()
        cur.close()
        conn.close()
        return f"SUCCESS: Connected via {driver_name}! Server version: {version_row[0] if version_row else 'unknown'}"
    except Exception as exc:
        return f"FAILED: Connection to PostgreSQL failed via {driver_name}: {exc}"


def application(environ, start_response):
    """Standard WSGI entry point for Phusion Passenger."""
    query_string = environ.get("QUERY_STRING", "")
    params = urllib.parse.parse_qs(query_string)

    # 1. Host and Forwarding headers
    http_host = environ.get("HTTP_HOST", "<None>")
    x_forwarded_host = environ.get("HTTP_X_FORWARDED_HOST", "<None>")
    x_forwarded_proto = environ.get("HTTP_X_FORWARDED_PROTO", "<None>")
    server_port = environ.get("SERVER_PORT", "<None>")
    wsgi_scheme = environ.get("wsgi.url_scheme", "<None>")
    env_https = environ.get("HTTPS", "<None>")

    # Determine if request was over HTTPS
    is_https = (
        wsgi_scheme.lower() == "https"
        or env_https.lower() in ("on", "1")
        or x_forwarded_proto.lower() == "https"
        or server_port == "443"
    )

    # 2. Python runtime information
    py_version = sys.version.replace("\n", " ")
    py_executable = sys.executable

    # 3. Directories and Filesystem write check
    cwd = os.getcwd()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    write_status_cwd = check_filesystem_write(cwd)
    write_status_script = (
        check_filesystem_write(script_dir) if script_dir != cwd else write_status_cwd
    )

    # 4. Outbound HTTPS check
    cloudinary_status = check_outbound_https("https://api.cloudinary.com", timeout=5)

    # 5. Outbound SMTP TCP connect check
    # Check query params for smtp_host and smtp_port
    smtp_host = params.get("smtp_host", params.get("host", [None]))[0]
    smtp_port = params.get("smtp_port", params.get("port", [None]))[0]

    if smtp_host and smtp_port:
        smtp_status = check_tcp_connect(smtp_host, smtp_port, timeout=5)
    elif smtp_host:
        smtp_status = check_tcp_connect(smtp_host, 587, timeout=5)
    else:
        smtp_status = (
            "SKIPPED (Pass ?smtp_host=<host>&smtp_port=<port> in URL to test, "
            "e.g. ?smtp_host=smtp-relay.brevo.com&smtp_port=587 or ?smtp_host=smtp.resend.com&smtp_port=465)"
        )

    # 6. Optional PostgreSQL connection check
    db_params = {
        "db_host": params.get("db_host", ["localhost"])[0],
        "db_port": params.get("db_port", ["5432"])[0],
        "db_name": params.get("db_name", [None])[0],
        "db_user": params.get("db_user", [None])[0],
        "db_pass": params.get("db_pass", [None])[0],
    }
    pg_status = check_postgresql(db_params)

    # Build response plain text
    lines = [
        "============================================================",
        "  FitGate Staging Spike - Hosting Verification App Output   ",
        "============================================================",
        "",
        "[1] INCOMING HOST & PROXY HEADERS",
        f"  Host Header (HTTP_HOST)           : {http_host}",
        f"  X-Forwarded-Host                  : {x_forwarded_host}",
        f"  X-Forwarded-Proto                 : {x_forwarded_proto}",
        f"  Server Port (SERVER_PORT)         : {server_port}",
        f"  WSGI Scheme (wsgi.url_scheme)     : {wsgi_scheme}",
        f"  HTTPS Environment Variable        : {env_https}",
        f"  Evaluated as HTTPS Request        : {'YES' if is_https else 'NO'}",
        "",
        "[2] PYTHON RUNTIME",
        f"  Python Version                    : {py_version}",
        f"  Python Executable                 : {py_executable}",
        "",
        "[3] DIRECTORIES & PERMISSIONS",
        f"  Current Working Directory (cwd)   : {cwd}",
        f"  Script Directory (__file__)       : {script_dir}",
        f"  Filesystem Write Test (cwd)       : {write_status_cwd}",
        f"  Filesystem Write Test (script_dir): {write_status_script}",
        "",
        "[4] OUTBOUND NETWORKING",
        f"  Cloudinary HTTPS (Port 443)       : {cloudinary_status}",
        f"  SMTP TCP Connect Test             : {smtp_status}",
        "",
        "[5] DATABASE (POSTGRESQL)",
        f"  PostgreSQL Connection / Drivers   : {pg_status}",
        "",
        "============================================================",
        f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
        "============================================================",
    ]

    body = "\n".join(lines) + "\n"
    response_data = body.encode("utf-8")

    status = "200 OK"
    response_headers = [
        ("Content-Type", "text/plain; charset=utf-8"),
        ("Content-Length", str(len(response_data))),
        ("Cache-Control", "no-cache, no-store, must-revalidate"),
    ]

    start_response(status, response_headers)
    return [response_data]


if __name__ == "__main__":
    # Allow testing locally via Python command line or simple server
    from wsgiref.simple_server import make_server

    port = 8080
    print(f"Starting test server on http://localhost:{port}/ ...")
    with make_server("", port, application) as httpd:
        httpd.serve_forever()
