import os
import sys

import requests


API_URL = "http://localhost:18000/api/v1/registrar/queues/today"
TOKEN_ENV = "REGISTRAR_API_TOKEN"


def main() -> int:
    token = os.environ.get(TOKEN_ENV, "").strip()
    if not token:
        print(f"Set {TOKEN_ENV} to a locally generated bearer token before running this smoke script.")
        return 2

    try:
        response = requests.get(
            API_URL,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
    except requests.RequestException as exc:
        print(f"Request failed: {exc}")
        return 1

    if response.status_code != 200:
        print(f"API failed: {response.status_code}")
        print(response.text)
        return 1

    data = response.json()
    queues = data.get("queues", [])
    print(f"API returned data: {response.status_code}")
    print(f"Queues: {len(queues)}")

    total_entries = 0
    for queue in queues:
        entries = len(queue.get("entries", []))
        total_entries += entries
        print(f"  {queue['specialty']}: {entries} entries")

    print(f"Total entries: {total_entries}")
    if total_entries > 6:
        print("New entry detected")
    else:
        print("New entry not found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
