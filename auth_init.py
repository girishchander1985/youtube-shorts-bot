# auth_init.py
import os
from google_auth_oauthlib.flow import InstalledAppFlow

# 1. Allow oauthlib to accept modified/relaxed scopes from Google
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl"
]

def authenticate():
    flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
    creds = flow.run_local_server(port=8080)
    with open("token.json", "w") as f:
        f.write(creds.to_json())
    print("\nSUCCESS: 'token.json' generated successfully!")

if __name__ == "__main__":
    authenticate()