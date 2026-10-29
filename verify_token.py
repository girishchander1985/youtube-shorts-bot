# verify_token.py
import json
import os
import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

PROXY_URL = "http://192.0.2.12:8080"
PROXIES = {
    "http": PROXY_URL,
    "https": PROXY_URL,
}

# Set environment proxies for underlying urllib/transport sessions
os.environ["HTTP_PROXY"] = PROXY_URL
os.environ["HTTPS_PROXY"] = PROXY_URL
os.environ["http_proxy"] = PROXY_URL
os.environ["https_proxy"] = PROXY_URL

TOKEN_FILE = "token.json"


def verify_youtube():
  if not os.path.exists(TOKEN_FILE):
    print(f"Error: {TOKEN_FILE} not found. Run auth_init.py first.")
    return

  # 1. Load Credentials
  creds = Credentials.from_authorized_user_file(TOKEN_FILE)

  # 2. Refresh token via requests session through proxy if expired
  session = requests.Session()
  session.proxies.update(PROXIES)

  if creds.expired or not creds.valid:
    print("Token needs refresh. Refreshing via proxy...")
    transport_req = Request(session=session)
    creds.refresh(transport_req)
    with open(TOKEN_FILE, "w") as f:
      f.write(creds.to_json())
    print("Token refreshed and updated successfully.")

  # 3. Call YouTube Data API directly via requests
  url = "https://www.googleapis.com/youtube/v3/channels"
  params = {"part": "snippet,statistics,status", "mine": "true"}
  headers = {
      "Authorization": f"Bearer {creds.token}",
      "Accept": "application/json",
  }

  try:
    response = session.get(url, params=params, headers=headers, timeout=20)
    data = response.json()

    if "error" in data:
      print("API Error Response:")
      print(json.dumps(data["error"], indent=2))
      return

    items = data.get("items", [])
    if not items:
      print(
          "Authentication succeeded, but no YouTube channel was found on this"
          " Google account."
      )
      return

    ch = items[0]
    print("=" * 45)
    print(" YOUTUBE AUTHENTICATION VERIFIED ")
    print("=" * 45)
    print(f"Channel Title   : {ch['snippet']['title']}")
    print(f"Channel ID      : {ch['id']}")
    print(f"Subscribers     : {ch['statistics'].get('subscriberCount', '0')}")
    print(f"Total Videos    : {ch['statistics'].get('videoCount', '0')}")
    print(f"Privacy Status  : {ch['status'].get('privacyStatus', 'public')}")
    print("=" * 45)
    print(
        "SUCCESS: token.json is confirmed valid and ready for Azure deployment!"
    )

  except Exception as e:
    print(f"Verification request failed: {e}")


if __name__ == "__main__":
  verify_youtube()