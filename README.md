# logmine · 日志模板挖掘与结构化指标管道

把「同一模板、不同参数」的日志压成模板与槽位，再按 (模板 × 5min) 桶做中位数 + MAD 基线，
让「某个模板突然变多」变成可确认的告警——而不是靠 grep 和关键字误报。

- 短名：`logmine`；前端 `18228` / 后端 `19228` / MySQL `17728`
- 视觉方向：气象站观测板（浅灰蓝纸面 + 深青灰 + 琥珀，Archivo Narrow + Source Code Pro，大号数值仪表 + 细网格底纹 + 上下非对称分栏）

## 1. 真实场景

**模拟客户**：云栖 IDC · SRE 团队（14 人），在管 40 个服务、每天约 1200 万行日志（demo 压缩到 6240 行）。

**现有工作流**：值班时用 `grep` + 手写正则找问题，告警靠关键字匹配。三个最痛的点和对应改法：

| 痛点 | logmine 的做法 |
|---|---|
| 新服务日志格式没人写规则，接入要等 2–3 天 | 上传样本，Drain 直接挖模板（`/import`），不需要人写正则 |
| 同一模板不同参数被当多条，关键字告警误报多 | 先聚成模板再计数，按 (模板 × 5min) 桶判定，模板级去抖 |
| 无法按「模板」看趋势，复盘靠翻文件 | `/events` 按模板聚合趋势；`/alerts` 每条告警带判定快照 |

**上下游**：上游是各服务 Filebeat 采集的日志（demo 用 `/import` 样本 + seed 事件表代替）；
本系统替代「grep + 关键字告警」这一段；下游是值班看板与告警群、复盘报告。

**角色权限**

| 角色（enum） | 账号 | 主要页面 | 权限 | 典型动作 |
|---|---|---|---|---|
| `admin` SRE 负责人 | admin@logmine.demo | 全部 | 全部写 | 建日志源、改解析规则、导入挖掘、配告警 |
| `engineer` 值班工程师 | engineer@logmine.demo | 检索 / 告警 | 读写事件与告警确认 | 检索、跑扫描、确认/静默告警 |
| `viewer` 只读观察者 | viewer@logmine.demo | 趋势 / 模板 | 只读 | 看趋势与模板 |

演示密码统一 `Demo@2026`。

## 2. 快速启动

```bash
cd batch-20261110b/projects/gb-555
cp .env.example .env
docker compose up -d --build
```

- 前端 <http://localhost:18228>（Nginx 托管构建产物 + `/api` 反代）
- 后端 <http://localhost:19228/api/health>（FastAPI，`/api` 与根路径两套路由）
- MySQL `localhost:17728`（`logmine / logmine_pw_2026`）
- 首次启动 `SEED_DEMO=true` 自动幂等 seed（失败只记 WARNING 不阻塞）；手动重跑：

```bash
docker compose exec -T backend python -m scripts.seed_demo
# SEED_SUMMARY sources=4 rules=8 templates=8 events=6240 alerts=2 users=3
```

演示流程（与 TESTING.md 第 5 节一致）：admin 登录 → `/import`「载入内置样本」→「运行 Drain 挖掘」
（5 个新模板 / 覆盖率 96.39%）→「应用模板到事件」→ `/events` 看按模板聚合趋势 →
`/alerts`「运行异常扫描」（error 模板尖峰 z=6.745 触发告警）→ 用 engineer 登录确认并静默 30min →
viewer 登录验证只读（建规则 403）。

## 3. 两个核心算法（Python 真算，结果落库，前端只展示）

### A. Drain 日志模板挖掘 · `backend/src/services/drain_engine.py`

输入：日志行批。① tokenize（按空白切分，引号内保留）；② 按 token 数分层、层内前缀树；
③ 从根逐 token 匹配，匹配不到就停在当前节点，用通配位个数算相似度
`similarity = 1 - mismatch / token_count`，阈值 0.5（可配），达标就把差异位写 `<*>` 合并，否则新建；
④ 变量识别：数字 / IP / UUID / 路径 / hex / 时间戳优先归槽位（`key=value` 先剥 key 再判类型，key 记为槽位名）；
⑤ 新建模板记录槽位类型、样例行、首次出现位置；⑥ 输出模板列表 + 覆盖率（被模板覆盖行 / 总行）+ 新模板数。

失败态：空行 / 纯符号行 → `_noise` 模板并单列统计（不参与覆盖率分子）；单模板样本 < 2 → `tentative`。

### B. 模板级聚合与基线异常 · `backend/src/services/anomaly_engine.py`

① 按 (template_id, 5min 桶) 计数并统计 error/fatal 行；② 基线 = 当前桶之前 12 个桶（缺失桶补 0）；
③ `z = 0.6745 × (x − median) / MAD`，`MAD = median(|x − median|)`，MAD=0 时用 1 兜底；
④ error 占比从基线 <5% 骤升到当前 >25% 也触发；⑤ `z > 3.5` 判尖峰，同模板 30 分钟静默去抖。
输出 `alert_event`（模板 / 桶 / 计数 / 基线 median / MAD / z / error 占比 / 触发原因 / 状态）。
失败态：有效历史桶 < 3 → 标 `insufficient_history`，不判异常。

可复现条件：`SEED_ANCHOR=2026-11-10T15:05:00` 固定时间轴 + 确定性样本生成器
（`backend/scripts/fixtures.py`，无 random），因此 z 值与覆盖率每次重跑一致。

## 4. 页面（6 个）

| 路由 | 内容 | 共享组件 |
|---|---|---|
| `/login` | 登录（手输邮箱，不做账号快捷切换） | — |
| `/sources` | 日志源与解析规则（左列表右详情） | `SourceCard` |
| `/templates` | 模板库：模板串 + 槽位高亮 + 频次 | `TemplateTokenStrip` |
| `/events` | 事件检索 + 按模板聚合趋势（Canvas2D 折线 + error 柱） | `TrendChart` |
| `/alerts` | 告警规则与触发记录（mini 趋势 + 判定快照） | `TrendChart`（mini） |
| `/import` | 导入/采样 → Drain 挖掘预览 → 应用模板 | `TemplateTokenStrip` / `SourceCard` |

## 5. 技术栈

| 层 | 选型 |
|---|---|
| 前端 | React 18 + TypeScript + Vite（zustand 状态，Canvas2D 图表，无图表库） |
| 后端 | Python 3.11 + FastAPI + SQLAlchemy 2.0（pymysql）+ Pydantic v2 |
| 任务 | Celery 5 + Redis（worker 跑周期扫描/挖掘与心跳） |
| 数据库 | MySQL 8.0（utf8mb4，容器时区 +08:00） |
| 网关 | Nginx 1.27（托管 dist + `/api/` 反代剥前缀 + SPA 回落） |
| 容器 | docker compose，5 服务全部 healthcheck |

## 6. 目录

```
gb-555/
├─ docker-compose.yml / .env / .env.example
├─ backend/
│  ├─ Dockerfile / entrypoint.sh / requirements.txt
│  ├─ migrations/               # 占位（建表走 metadata.create_all，见文件说明）
│  ├─ scripts/
│  │  ├─ fixtures.py            # 确定性日志样本生成器（seed 与 /import 共用）
│  │  └─ seed_demo.py           # 幂等 seed + SEED_SUMMARY
│  └─ src/
│     ├─ config/                # settings / database / app / celery / bootstrap
│     ├─ constants/             # enums / roles / error_codes / limits / messages / log_templates
│     ├─ models/                # log_source / parse_rule / log_template / log_event / alert_rule / alert_event / user / audit_log
│     ├─ schemas/               # 请求响应模型
│     ├─ services/              # drain_engine / anomaly_engine / source / template / event / alert / import / audit / quota / auth
│     ├─ controllers/           # 编排 service + 写审计
│     ├─ routes/                # health / auth / sources / templates / events / alerts / imports / audit / meta
│     ├─ middlewares/           # auth / rbac / rate_limit / audit_logger / error_handler
│     └─ utils/                 # jwt / password / errors / logger / redis / time_buckets / text
├─ worker/                      # Celery worker（复用 backend 服务层）+ healthcheck.sh
└─ frontend/
   ├─ Dockerfile / nginx.conf
   └─ src/{api,stores,types,components/common,components/layout,hooks,pages,router,utils,constants,styles}
```

## 7. 环境变量（`.env.example`）

| 变量 | 说明 | 默认 |
|---|---|---|
| `FRONTEND_PORT` / `BACKEND_PORT` / `DB_PORT` | 宿主端口 | 18228 / 19228 / 17728 |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` / `DB_ROOT_PASSWORD` | MySQL | logmine / logmine / … |
| `JWT_SECRET` / `ACCESS_TOKEN_MINUTES` / `REFRESH_TOKEN_DAYS` | 认证 | HS256 / 120 / 7 |
| `REDIS_URL` | Redis（限流/配额/心跳/Celery） | `redis://redis:6379/0` |
| `SEED_DEMO` | 启动自动 seed | `true` |
| `SEED_ANCHOR` | demo 固定时间轴起点 | `2026-11-10T15:05:00` |
| `MAX_UPLOAD_MB` | 单次导入样本上限 | 8 |
| `RATE_LIMIT_PER_MINUTE` / `DAILY_QUOTA_*` | 限流与每日写配额 | 120 / 8000·4000·2000 |

## 8. 横切关注点

1. **JWT + 3 角色**：`utils/jwt.py` 签发、`middlewares/auth.py` 校验、`middlewares/rbac.py`
   `require_permission(action)` 按 `constants/roles.py` 能力矩阵判定；前端 `constants/enums.ts`
   的 `PERMISSION_MATRIX` 与 `stores/authStore.can()` 对应，页面用 `RequireRole` 门禁。
2. **审计日志**：`audit_log` 表；`services/audit_service.record()` 在 controller 内显式写
   （login / sources.create|update / parse_rules.create|update / templates.confirm|mark_noise /
   events.import_apply / alerts.rule_create|rule_update / alerts.scan / alerts.acknowledge|silence）。
3. **限流 / 配额**：`middlewares/rate_limit.guard(bucket)` 用 Redis 滑动窗口做每用户每分钟限流
   （读 180 / 写 40 / 扫描 6），写请求额外扣 `services/quota_service` 的每日角色配额，超限统一 429。

## 9. 共享枚举出现位置（前后端各一份）

| 枚举组 | 后端 | 前端 |
|---|---|---|
| 角色 role | `constants/enums.py`(ROLE_*) + `constants/roles.py` + `models/user.py` + `seed_demo.py` | `constants/enums.ts`(ROLES/ROLE_LABELS/PERMISSION_MATRIX) |
| 日志格式 / 采集状态 | `constants/enums.py` + `models/log_source.py` | `constants/enums.ts` + `pages/Sources.tsx` |
| 模板状态 | `constants/enums.py` + `models/log_template.py` + `services/drain_engine.py` | `constants/enums.ts`(TEMPLATE_STATUS_LABELS) + `components/common/StatusPill.tsx` |
| 槽位类型 | `constants/enums.py` + `services/drain_engine.py` | `constants/enums.ts`(SLOT_LABELS) + `utils/slotColor.ts` + `TemplateTokenStrip` |
| 事件级别 | `constants/enums.py` + `models/log_event.py` + `services/anomaly_engine.py` | `constants/enums.ts`(LEVEL_LABELS) + `LevelBadge` |
| 触发原因 / 告警状态 | `constants/enums.py` + `models/alert_event.py` | `constants/enums.ts`(TRIGGER_REASON_LABELS/ALERT_STATUS_LABELS) + `pages/Alerts.tsx` |

## 10. 本地开发（不走容器）

```bash
# backend（需要本地 MySQL/Redis 或改 .env 指向容器映射端口）
cd backend && pip install -r requirements.txt
python -m src.config.bootstrap
SEED_DEMO=true uvicorn src.main:app --reload --port 8000

# frontend
cd frontend && npm install && npm run dev   # vite 代理 /api → localhost:19228
```

## 11. Docker 说明

- 恰好 5 个容器：`frontend` / `backend` / `worker` / `db` / `redis`，全部 healthcheck；
  顶层 `name: logmine`，无 `version:`；`container_name: ${COMPOSE_PROJECT_NAME:-logmine}-<role>`。
- backend/worker 依赖 db/redis `service_healthy`；frontend 依赖 backend healthy。
- 命名卷：`db_data`（MySQL）、`redis_data`（Redis AOF）、`sample_data`（样本文件，backend/worker 共享）。
- 建表：backend 启动先跑 `python -m src.config.bootstrap`（`Base.metadata.create_all`），再起 uvicorn。
- 收尾：`docker compose down -v --remove-orphans`。

## 12. License

内部演示项目，仅用于批量选题评审；示例数据均为生成数据，不含真实客户日志。
