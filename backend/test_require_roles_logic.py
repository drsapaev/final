"""Import-safe manual require_roles logic check."""

from __future__ import annotations


def test_require_roles() -> bool:
    roles = ("Admin", "Registrar")
    print(f"Roles: {roles}")
    print(f"Type: {type(roles)}")

    user_role = "Doctor"
    is_super = False

    print(f"User role: {user_role}")
    print(f"is_superuser: {is_super}")

    if not roles:
        print("No roles configured; access allowed")
        return True

    if is_super:
        print("Superuser; access allowed")
        return True

    role_lower = str(user_role).lower() if user_role else ""
    roles_lower = [str(role).lower() for role in roles]

    print(f"User role lowercase: {role_lower}")
    print(f"Required roles lowercase: {roles_lower}")

    if role_lower not in roles_lower:
        print("Access denied; role not found")
        return False

    print("Access allowed; role found")
    return True


if __name__ == "__main__":
    raise SystemExit(0 if test_require_roles() else 1)
