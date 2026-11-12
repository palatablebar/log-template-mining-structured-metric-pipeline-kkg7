"""路由聚合：所有子路由挂在 api_router 上（Nginx 剥 /api 前缀后同名可用）。"""
from __future__ import annotations

from fastapi import APIRouter

from src.routes import alerts, audit, auth, events, health, imports, meta, sources, templates

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(sources.router)
api_router.include_router(templates.router)
api_router.include_router(events.router)
api_router.include_router(alerts.router)
api_router.include_router(imports.router)
api_router.include_router(audit.router)
api_router.include_router(meta.router)
