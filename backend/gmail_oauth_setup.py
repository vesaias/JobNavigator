"""One-time Gmail OAuth2 setup script.
Run this locally to get a refresh token, then add it to .env as GMAIL_REFRESH_TOKEN.

Works with Web application type OAuth credentials by spinning up a temporary
localhost server to catch the redirect.

Usage:
  py backend/gmail_oauth_setup.py
"""
import http.server
import json
import os
import sys
import threading
import urllib.parse
import urllib.request
import webbrowser

from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("GMAIL_CLIENT_ID")
CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET")

if not CLIENT_ID or not CLIENT_SECRET:
    print("ERROR: Set GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET in .env first")
    sys.exit(1)

REDIRECT_PORT = 8090
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}"
SCOPE = "https://www.googleapis.com/auth/gmail.readonly"

AUTH_URL = (
    "https://accounts.google.com/o/oauth2/v2/auth?"
    + urllib.parse.urlencode({
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",
    })
)

# Will be set by the callback handler
auth_code = None
server_error = None


class OAuthHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code, server_error
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)

        if "code" in params:
            auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<html><body style='font-family:sans-serif;text-align:center;padding:60px'>"
                b"<h1>&#9989; Authorization successful!</h1>"
                b"<p>You can close this tab and return to the terminal.</p>"
                b"</body></html>"
            )
        elif "error" in params:
            server_error = params["error"][0]
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(f"<html><body><h1>Error: {server_error}</h1></body></html>".encode())
        else:
            self.send_response(400)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress HTTP log noise


print("=" * 60)
print("Gmail OAuth2 Setup")
print("=" * 60)
print()
print("IMPORTANT: You must add this redirect URI in Google Cloud Console:")
print(f"  {REDIRECT_URI}")
print()
print("  Go to: https://console.cloud.google.com/apis/credentials")
print("  Edit your OAuth 2.0 Client ID -> Authorized redirect URIs")
print(f"  Add: {REDIRECT_URI}")
print("  Click Save, then re-run this script.")
print()
print("Opening browser for authorization...")
print()

# Start temporary local server
server = http.server.HTTPServer(("localhost", REDIRECT_PORT), OAuthHandler)
server_thread = threading.Thread(target=server.handle_request)
server_thread.start()

# Open browser
webbrowser.open(AUTH_URL)

print("Waiting for Google authorization callback...")
print("(If the browser didn't open, copy this URL manually:)")
print()
print(AUTH_URL)
print()

# Wait for callback
server_thread.join(timeout=120)
server.server_close()

if server_error:
    print(f"ERROR: Google returned error: {server_error}")
    sys.exit(1)

if not auth_code:
    print("ERROR: Timed out waiting for authorization (2 minutes).")
    print("Make sure you completed the Google sign-in flow.")
    sys.exit(1)

print("Authorization code received! Exchanging for tokens...")

# Exchange code for tokens
data = urllib.parse.urlencode({
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "code": auth_code,
    "grant_type": "authorization_code",
    "redirect_uri": REDIRECT_URI,
}).encode()

req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data, method="POST")
req.add_header("Content-Type", "application/x-www-form-urlencoded")

try:
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read().decode())
        refresh_token = result.get("refresh_token")

        if refresh_token:
            print()
            print("=" * 60)
            print("SUCCESS! Add this to your .env file:")
            print()
            print(f"GMAIL_REFRESH_TOKEN={refresh_token}")
            print()
            print("=" * 60)
        else:
            print("ERROR: No refresh token in response.")
            print(json.dumps(result, indent=2))
except urllib.error.HTTPError as e:
    body = e.read().decode()
    print(f"ERROR: Token exchange failed ({e.code}): {body}")
except Exception as e:
    print(f"ERROR: {e}")
