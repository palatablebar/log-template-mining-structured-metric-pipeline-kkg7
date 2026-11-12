"""RBAC 角色常量与能力矩阵。前后端必须一致：
users.role / constants/roles.py / frontend constants/enums.ts / <RequireRole>。
"""
from __future__ import annotations

from src.constants.enums import ALL_ROLES, ROLE_ADMIN, ROLE_ENGINEER, ROLE_VIEWER

PERMISSIONS: dict[str, tuple[str, ...]] = {
    # 读
    "sources:read": ALL_ROLES,
    "templates:read": ALL_ROLES,
    "events:read": ALL_ROLES,
    "alerts:read": ALL_ROLES,
    "audit:read": ALL_ROLES,
    # 写
    "sources:write": (ROLE_ADMIN,),
    "parse_rules:write": (ROLE_ADMIN,),
    "templates:write": (ROLE_ADMIN,),
    "events:import": (ROLE_ADMIN,),
    "alerts:write": (ROLE_ADMIN,),
    "alerts:ack": (ROLE_ADMIN, ROLE_ENGINEER),
    "alerts:silence": (ROLE_ADMIN, ROLE_ENGINEER),
    "scan:run": (ROLE_ADMIN, ROLE_ENGINEER),
}

ROLE_DAILY_QUOTA_KEY: dict[str, str] = {
    ROLE_ADMIN: "daily_quota_admin",
    ROLE_ENGINEER: "daily_quota_engineer",
    ROLE_VIEWER: "daily_quota_viewer",
}


def role_can(role: str, action: str) -> bool:
    return role in PERMISSIONS.get(action, ())
