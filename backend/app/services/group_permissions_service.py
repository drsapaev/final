"""
Сервис для работы с разрешениями групп пользователей
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Set, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from app.models.user import User
from app.models.role_permission import (
    Role, Permission, UserGroup, UserPermissionOverride,
    PermissionAuditLog, RoleHierarchy, user_roles_table, user_groups_table, group_roles_table
)
from app.crud import user as crud_user

logger = logging.getLogger(__name__)


class GroupPermissionsService:
    """Сервис для управления разрешениями групп и пользователей"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        # Кэш для разрешений (в production лучше использовать Redis)
        self._permissions_cache = {}
        self._cache_ttl = 300  # 5 минут
    
    def get_user_permissions(self, db: Session, user_id: int, use_cache: bool = True) -> Set[str]:
        """
        Получить все разрешения пользователя из БД
        Включает разрешения из ролей, групп и индивидуальные переопределения
        """
        try:
            # Проверяем кэш
            cache_key = f"user_permissions_{user_id}"
            if use_cache and cache_key in self._permissions_cache:
                cached_data = self._permissions_cache[cache_key]
                if datetime.utcnow() - cached_data['timestamp'] < timedelta(seconds=self._cache_ttl):
                    return cached_data['permissions']
            
            # Проверяем, что пользователь существует
            if not db.query(User.id).filter(User.id == user_id).first():
                return set()

            permissions = set()

            # 1) Роли пользователя через связующую таблицу
            user_roles = db.query(Role).join(
                user_roles_table, Role.id == user_roles_table.c.role_id
            ).filter(
                user_roles_table.c.user_id == user_id,
                Role.is_active == True
            ).all()

            for role in user_roles:
                role_permissions = self._get_role_permissions_recursive(db, role.id)
                permissions.update(role_permissions)

            # 2) Разрешения из групп пользователя
            user_groups = db.query(UserGroup).join(
                user_groups_table, UserGroup.id == user_groups_table.c.group_id
            ).filter(
                user_groups_table.c.user_id == user_id,
                UserGroup.is_active == True
            ).all()

            for group in user_groups:
                group_permissions = self._get_group_permissions(db, group.id)
                permissions.update(group_permissions)
            
            # 3. Индивидуальные переопределения разрешений
            overrides = db.query(UserPermissionOverride).filter(
                and_(
                    UserPermissionOverride.user_id == user_id,
                    UserPermissionOverride.is_active == True,
                    or_(
                        UserPermissionOverride.expires_at.is_(None),
                        UserPermissionOverride.expires_at > datetime.utcnow()
                    )
                )
            ).all()
            
            for override in overrides:
                permission_codename = override.permission.codename
                if override.override_type == "grant":
                    permissions.add(permission_codename)
                elif override.override_type == "deny":
                    permissions.discard(permission_codename)
            
            # Кэшируем результат
            if use_cache:
                self._permissions_cache[cache_key] = {
                    'permissions': permissions,
                    'timestamp': datetime.utcnow()
                }
            
            return permissions
            
        except Exception as e:
            self.logger.error(f"Ошибка получения разрешений пользователя {user_id}: {e}")
            return set()
    
    def _get_role_permissions_recursive(self, db: Session, role_id: int, visited: Set[int] = None) -> Set[str]:
        """
        Получить разрешения роли с учетом иерархии (рекурсивно)
        """
        if visited is None:
            visited = set()
        
        if role_id in visited:
            return set()  # Избегаем циклических зависимостей
        
        visited.add(role_id)
        permissions = set()
        
        role = db.query(Role).filter(Role.id == role_id).first()
        if not role or not role.is_active:
            return permissions
        
        # Прямые разрешения роли
        for permission in role.permissions:
            if permission.is_active:
                permissions.add(permission.codename)
        
        # Разрешения родительской роли
        if role.parent_role_id:
            parent_permissions = self._get_role_permissions_recursive(
                db, role.parent_role_id, visited.copy()
            )
            permissions.update(parent_permissions)
        
        return permissions
    
    def _get_group_permissions(self, db: Session, group_id: int) -> Set[str]:
        """
        Получить все разрешения группы через её роли
        """
        permissions = set()
        
        group = db.query(UserGroup).filter(UserGroup.id == group_id).first()
        if not group or not group.is_active:
            return permissions

        # Роли группы через group_roles_table
        group_roles = db.query(Role).join(
            group_roles_table, Role.id == group_roles_table.c.role_id
        ).filter(
            group_roles_table.c.group_id == group_id,
            Role.is_active == True
        ).all()

        for role in group_roles:
            role_permissions = self._get_role_permissions_recursive(db, role.id)
            permissions.update(role_permissions)
        
        return permissions
    
    def has_permission(self, db: Session, user_id: int, permission_codename: str) -> bool:
        """
        Проверить, есть ли у пользователя конкретное разрешение
        """
        user_permissions = self.get_user_permissions(db, user_id)
        return permission_codename in user_permissions
    
    def has_any_permission(self, db: Session, user_id: int, permission_codenames: List[str]) -> bool:
        """
        Проверить, есть ли у пользователя хотя бы одно из указанных разрешений
        """
        user_permissions = self.get_user_permissions(db, user_id)
        return any(perm in user_permissions for perm in permission_codenames)
    
    def has_all_permissions(self, db: Session, user_id: int, permission_codenames: List[str]) -> bool:
        """
        Проверить, есть ли у пользователя все указанные разрешения
        """
        user_permissions = self.get_user_permissions(db, user_id)
        return all(perm in user_permissions for perm in permission_codenames)
    
    def get_group_permissions_summary(self, db: Session, group_id: int) -> Dict[str, Any]:
        """
        Получить сводку разрешений группы
        """
        try:
            group = db.query(UserGroup).filter(UserGroup.id == group_id).first()
            if not group:
                return {"error": "Группа не найдена"}
            
            permissions = self._get_group_permissions(db, group_id)
            
            # Группируем разрешения по категориям
            permissions_by_category = {}
            for perm_codename in permissions:
                permission = db.query(Permission).filter(
                    Permission.codename == perm_codename
                ).first()
                if permission:
                    category = permission.category or "general"
                    if category not in permissions_by_category:
                        permissions_by_category[category] = []
                    permissions_by_category[category].append({
                        "codename": permission.codename,
                        "name": permission.name,
                        "description": permission.description
                    })
            
            # Роли группы (через связующую таблицу)
            roles_info = []
            group_roles = db.query(Role).join(
                group_roles_table, Role.id == group_roles_table.c.role_id
            ).filter(
                group_roles_table.c.group_id == group_id,
                Role.is_active == True
            ).all()

            for role in group_roles:
                roles_info.append({
                    "id": role.id,
                    "name": role.name,
                    "display_name": role.display_name,
                    "description": role.description,
                    "level": role.level
                })

            # Подсчитываем пользователей в группе
            users_count = db.query(User).join(
                user_groups_table, User.id == user_groups_table.c.user_id
            ).filter(
                user_groups_table.c.group_id == group_id,
                User.is_active == True
            ).count()
            
            return {
                "group_id": group_id,
                "group_name": group.name,
                "group_display_name": group.display_name,
                "group_type": group.group_type,
                "users_count": users_count,
                "roles": roles_info,
                "permissions_count": len(permissions),
                "permissions_by_category": permissions_by_category,
                "total_permissions": list(permissions)
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка получения сводки разрешений группы {group_id}: {e}")
            return {"error": f"Ошибка получения данных: {str(e)}"}
    
    def assign_role_to_group(
        self, 
        db: Session, 
        group_id: int, 
        role_id: int, 
        assigned_by_user_id: int
    ) -> Dict[str, Any]:
        """
        Назначить роль группе
        """
        try:
            group = db.query(UserGroup).filter(UserGroup.id == group_id).first()
            role = db.query(Role).filter(Role.id == role_id).first()
            
            if not group:
                return {"success": False, "error": "Группа не найдена"}
            
            if not role:
                return {"success": False, "error": "Роль не найдена"}
            
            # Проверяем, не назначена ли уже роль
            if role in group.roles:
                return {"success": False, "error": "Роль уже назначена группе"}
            
            # Назначаем роль
            group.roles.append(role)
            db.commit()
            
            # Очищаем кэш для всех пользователей группы
            self._clear_cache_for_group_users(group)
            
            # Логируем изменение
            self._log_permission_change(
                db, assigned_by_user_id, "assign_role_to_group", 
                "group", group_id, role_id=role_id,
                new_value=f"Роль {role.name} назначена группе {group.name}"
            )
            
            return {
                "success": True,
                "message": f"Роль '{role.display_name}' назначена группе '{group.display_name}'"
            }
            
        except Exception as e:
            db.rollback()
            self.logger.error(f"Ошибка назначения роли {role_id} группе {group_id}: {e}")
            return {"success": False, "error": f"Ошибка назначения роли: {str(e)}"}
    
    def revoke_role_from_group(
        self, 
        db: Session, 
        group_id: int, 
        role_id: int, 
        revoked_by_user_id: int
    ) -> Dict[str, Any]:
        """
        Отозвать роль у группы
        """
        try:
            group = db.query(UserGroup).filter(UserGroup.id == group_id).first()
            role = db.query(Role).filter(Role.id == role_id).first()
            
            if not group:
                return {"success": False, "error": "Группа не найдена"}
            
            if not role:
                return {"success": False, "error": "Роль не найдена"}
            
            # Проверяем, назначена ли роль
            if role not in group.roles:
                return {"success": False, "error": "Роль не назначена группе"}
            
            # Отзываем роль
            group.roles.remove(role)
            db.commit()
            
            # Очищаем кэш для всех пользователей группы
            self._clear_cache_for_group_users(group)
            
            # Логируем изменение
            self._log_permission_change(
                db, revoked_by_user_id, "revoke_role_from_group", 
                "group", group_id, role_id=role_id,
                old_value=f"Роль {role.name} отозвана у группы {group.name}"
            )
            
            return {
                "success": True,
                "message": f"Роль '{role.display_name}' отозвана у группы '{group.display_name}'"
            }
            
        except Exception as e:
            db.rollback()
            self.logger.error(f"Ошибка отзыва роли {role_id} у группы {group_id}: {e}")
            return {"success": False, "error": f"Ошибка отзыва роли: {str(e)}"}
    
    def add_user_to_group(
        self, 
        db: Session, 
        user_id: int, 
        group_id: int, 
        added_by_user_id: int
    ) -> Dict[str, Any]:
        """
        Добавить пользователя в группу
        """
        try:
            user = db.query(User).filter(User.id == user_id).first()
            group = db.query(UserGroup).filter(UserGroup.id == group_id).first()
            
            if not user:
                return {"success": False, "error": "Пользователь не найден"}
            
            if not group:
                return {"success": False, "error": "Группа не найдена"}
            
            # Проверяем, не состоит ли уже в группе
            if group in user.groups:
                return {"success": False, "error": "Пользователь уже состоит в группе"}
            
            # Добавляем в группу
            user.groups.append(group)
            db.commit()
            
            # Очищаем кэш пользователя
            self._clear_user_cache(user_id)
            
            # Логируем изменение
            self._log_permission_change(
                db, added_by_user_id, "add_user_to_group", 
                "user", user_id, 
                new_value=f"Пользователь {user.username} добавлен в группу {group.name}"
            )
            
            return {
                "success": True,
                "message": f"Пользователь '{user.username}' добавлен в группу '{group.display_name}'"
            }
            
        except Exception as e:
            db.rollback()
            self.logger.error(f"Ошибка добавления пользователя {user_id} в группу {group_id}: {e}")
            return {"success": False, "error": f"Ошибка добавления в группу: {str(e)}"}
    
    def remove_user_from_group(
        self, 
        db: Session, 
        user_id: int, 
        group_id: int, 
        removed_by_user_id: int
    ) -> Dict[str, Any]:
        """
        Удалить пользователя из группы
        """
        try:
            user = db.query(User).filter(User.id == user_id).first()
            group = db.query(UserGroup).filter(UserGroup.id == group_id).first()
            
            if not user:
                return {"success": False, "error": "Пользователь не найден"}
            
            if not group:
                return {"success": False, "error": "Группа не найдена"}
            
            # Проверяем, состоит ли в группе
            if group not in user.groups:
                return {"success": False, "error": "Пользователь не состоит в группе"}
            
            # Удаляем из группы
            user.groups.remove(group)
            db.commit()
            
            # Очищаем кэш пользователя
            self._clear_user_cache(user_id)
            
            # Логируем изменение
            self._log_permission_change(
                db, removed_by_user_id, "remove_user_from_group", 
                "user", user_id,
                old_value=f"Пользователь {user.username} удален из группы {group.name}"
            )
            
            return {
                "success": True,
                "message": f"Пользователь '{user.username}' удален из группы '{group.display_name}'"
            }
            
        except Exception as e:
            db.rollback()
            self.logger.error(f"Ошибка удаления пользователя {user_id} из группы {group_id}: {e}")
            return {"success": False, "error": f"Ошибка удаления из группы: {str(e)}"}
    
    def _clear_user_cache(self, user_id: int):
        """Очистить кэш разрешений пользователя"""
        cache_key = f"user_permissions_{user_id}"
        if cache_key in self._permissions_cache:
            del self._permissions_cache[cache_key]
    
    def _clear_cache_for_group_users(self, group: UserGroup):
        """Очистить кэш для всех пользователей группы"""
        for user in group.users:
            self._clear_user_cache(user.id)
    
    def _log_permission_change(
        self, 
        db: Session, 
        user_id: int, 
        action: str, 
        target_type: str, 
        target_id: int,
        permission_id: Optional[int] = None,
        role_id: Optional[int] = None,
        old_value: Optional[str] = None,
        new_value: Optional[str] = None,
        reason: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """Логировать изменения разрешений"""
        try:
            audit_log = PermissionAuditLog(
                user_id=user_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                permission_id=permission_id,
                role_id=role_id,
                old_value=old_value,
                new_value=new_value,
                reason=reason,
                ip_address=ip_address,
                user_agent=user_agent
            )
            db.add(audit_log)
            db.commit()
        except Exception as e:
            self.logger.error(f"Ошибка логирования изменения разрешений: {e}")
    
    def clear_all_cache(self):
        """Очистить весь кэш разрешений"""
        self._permissions_cache.clear()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Получить статистику кэша"""
        return {
            "cache_size": len(self._permissions_cache),
            "cache_ttl": self._cache_ttl,
            "cached_users": [
                key.replace("user_permissions_", "") 
                for key in self._permissions_cache.keys()
            ]
        }


# Глобальный экземпляр сервиса
_group_permissions_service = None


def get_group_permissions_service() -> GroupPermissionsService:
    """Получить экземпляр сервиса разрешений групп"""
    global _group_permissions_service
    if _group_permissions_service is None:
        _group_permissions_service = GroupPermissionsService()
    return _group_permissions_service
