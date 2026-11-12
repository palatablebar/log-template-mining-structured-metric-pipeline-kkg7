"""结构化运行日志模板（utils.logger.render 使用，键值固定便于 grep）。"""
from __future__ import annotations

LOG_TEMPLATES: dict[str, str] = {
    "app.start": "app.start env={env} version={version}",
    "http.access": "http.access method={method} path={path} status={status} elapsed_ms={elapsed_ms} trace={trace}",
    "auth.login": "auth.login email={email} role={role} ok={ok}",
    "drain.run": "drain.run lines={lines} known={known} new_templates={new_templates} coverage={coverage} elapsed_ms={elapsed_ms}",
    "drain.noise": "drain.noise lines={lines} noise_lines={noise_lines} tentative={tentative}",
    "anomaly.scan": "anomaly.scan templates={templates} buckets={buckets} alerts={alerts} skipped={skipped}",
    "anomaly.skip": "anomaly.skip template={template} buckets={buckets} reason={reason}",
    "seed.summary": "seed.summary {summary}",
}
