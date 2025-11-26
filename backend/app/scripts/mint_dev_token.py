from __future__ import annotations

from app.api.deps import create_access_token  # type: ignore

if __name__ == "__main__":
    print(create_access_token("admin"))
