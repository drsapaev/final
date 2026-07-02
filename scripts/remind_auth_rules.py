#!/usr/bin/env python3
import os
import sys

def show_auth_reminder():
    print("\n" + "="*60)
    print("🚨 НАПОМИНАНИЕ О ПРАВИЛАХ АУТЕНТИФИКАЦИИ")
    print("="*60)
    print("📖 Перед работой прочитать:")
    print("   - docs/AUTHENTICATION_LAWS_FOR_AI.md")
    print("   - docs/AUTHENTICATION_SYSTEM_FINAL_GUIDE.md")
    print("\n🧪 Перед коммитом запустить:")
    print("   cd backend && python test_role_routing.py")
    print("\n🛡️ Критические правила:")
    print("   - НЕ нарушать блокирующий 2FA флоу")
    print("   - НЕ дублировать модели ролей")
    print("   - ИСПОЛЬЗОВАТЬ только LoginFormStyled.jsx")
    print("="*60 + "\n")

if __name__ == "__main__":
    show_auth_reminder()
