from urllib.error import HTTPError
from urllib.request import Request, urlopen
import json
import os

API_KEY = os.environ.get("API_KEY")

if API_KEY is None:
    raise Exception("API_KEY not provided")

reqbody = {
    "model": "claude-sonnet-4-5",
    "max_tokens": 500,
    "messages": [
        { "role": "user", "content": "What is love?" },
    ],
}

req = Request(
    "https://api.anthropic.com/v1/messages",
    method="POST",
    data=json.dumps(reqbody).encode(),
    headers={
        "X-Api-Key": API_KEY,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json"
    }
)

try:
    resp = urlopen(req)

    data = json.loads(resp.read())
    print(data)
except HTTPError as e:
    body = e.read()
    print(e.code, body.decode())
