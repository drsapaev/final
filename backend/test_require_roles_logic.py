# Тестируем функцию require_roles
def test_require_roles():
    # Симулируем вызов require_roles("Admin", "Registrar")
    roles = ("Admin", "Registrar")
    print(f"Роли: {roles}")
    print(f"Тип: {type(roles)}")
    
    # Симулируем роль пользователя
    user_role = "Doctor"
    is_super = False
    
    print(f"Роль пользователя: {user_role}")
    print(f"is_superuser: {is_super}")
    
    # Логика из require_roles
    if not roles:
        print("Нет ролей - доступ разрешен")
        return True
    
    if is_super:
        print("Суперпользователь - доступ разрешен")
        return True
    
    # Проверяем роль с учетом регистра
    role_lower = str(user_role).lower() if user_role else ""
    roles_lower = [str(r).lower() for r in roles]
    
    print(f"Роль пользователя (нижний регистр): {role_lower}")
    print(f"Требуемые роли (нижний регистр): {roles_lower}")
    
    if role_lower not in roles_lower:
        print("Доступ запрещен - роль не найдена")
        return False
    else:
        print("Доступ разрешен - роль найдена")
        return True

test_require_roles()
