from datetime import datetime
from dataclasses import dataclass, asdict
import threading
from json import JSONDecodeError
from pathlib import Path
import json
import typer
from src.logs.app_log import get_log

logger = get_log()

DURABLE_PATH = Path.home() / ".sebastian" / ".scheduled_tasks.json"

@dataclass
class CronJob:
    id: str
    cron: str
    prompt: str
    recurring: bool
    durable: bool

class CronSchedule:
    def __init__(self):
        self.scheduled_jobs: dict[str, CronJob] = {}
        self.cron_queue: list[CronJob] = []
        self.cron_lock = threading.Lock()
        self.agent_lock = threading.Lock()
        self._last_fired: dict[str, str] = {}

    def _cron_field_matches(self, field: str, value: int) -> bool:
        """Match single cron field against value"""
        if field == "*":
            return True
        if field.startswith("*/"):
            step = int(field[2:])
            return step > 0 and value % step == 0
        if "," in field:
            return any(self._cron_field_matches(f.strip(), value) for f in field.split(","))
        if "-" in field:
            lo, hi = field.split("-", 1)
            return int(lo) <= value <= int(hi)
        return value == int(field)

    def cron_matches(self, cron_expr: str, dt: datetime) -> bool:
        """Check if a 5-field cron expression matches the given datetime"""
        fields = cron_expr.strip().split()
        if len(fields) != 5:
            return False
        minute, hour, dom, month, dow = fields

        m = self._cron_field_matches(minute, dt.minute)
        h = self._cron_field_matches(hour, dt.hour)
        dom_ok = self._cron_field_matches(dom, dt.day)
        month_ok = self._cron_field_matches(month, dt.month)
        #Python中Monday为0，Cron中Sunday为0
        dow_ok = self._cron_field_matches(dow, (dt.weekday()+1) % 7)

        #匹配规则：Minute, Hour, Month必须全部匹配成功
        if not (m and h and month_ok):
            return False

        #DOM和DOW匹配规则：如果均为*则成功；如果其中一个为*，则另一个必须匹配成功;如果两个都不是*，则匹配成功一个即可
        dom_unconstrained = dom == "*"
        dow_unconstrained = dow == "*"
        if dom_unconstrained and dow_unconstrained:
            return True
        if dom_unconstrained:
            return dow_ok
        if dow_unconstrained:
            return dom_ok
        return dom_ok or dow_ok

    def _validate_cron_filed(self, field: str, lo: int, hi: int) -> str | None:
        """Validate a single cron field value is within [lo, hi]"""
        if field == "*":
            return None
        if field.startswith("*/"):
            step_str = field[2:]
            if not step_str.isdigit():
                return f"Invalid step: {field}"
            step = int(step_str)
            if step < 0:
                return f"Step must be > 0: {field}"
            return None
        if "," in field:
            for part in field.split(","):
                err = self._validate_cron_filed(part.strip(), lo, hi)
                if err:
                    return err
            return None
        if "-" in field:
            parts = field.split("-", 1)
            if not parts[0].isdigit() or not parts[1].isdigit():
                return f"Invalid range: {field}"
            a, b = int(parts[0]), int(parts[1])
            if a < lo or a > hi or b < lo or b > hi:
                return f"Range {field} out of bounds [{lo}, {hi}]"
            if a > b:
                return f"Range start > end: {field}"
            return None
        if not field.isdigit():
            return f"Invalid field: {field}"
        val = int(field)
        if val < lo or val > hi:
            return f"Value {val} out of bounds [{lo}, {hi}]"
        return None

    def validate_cron(self, cron_expr: str) -> str | None:
        """Validate a cron expression. Returns error message or None"""
        fields = cron_expr.strip().split()
        if len(fields) != 5:
            return f"Expected 5 fields, got {len(fields)}"
        bounds = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 6)]
        names = ["minute", "hour", "day-of-month", "month", "day-of-week"]
        for i, (field, (lo, hi), name) in enumerate(zip(fields, bounds, names)):
            err = self._validate_cron_filed(field, lo, hi)
            if err:
                return f"{name}: {err}"
        return None

    def save_durable_jobs(self):
        """Persist durable jobs to .scheduled_task.json."""
        durable = [asdict(j) for j in self.scheduled_jobs.values() if j.durable]
        DURABLE_PATH.write_text(json.dumps(durable, indent=2, ensure_ascii=False))

    def _load_durable_jobs(self):
        """Load durable jobs from .scheduled_task.json."""
        if not DURABLE_PATH.is_file():
            DURABLE_PATH.write_text("")
            return

        try:
            jobs = json.loads(DURABLE_PATH.read_text())
            for j in jobs:
                job = CronJob(**j)
                err = self.validate_cron(job.cron)
                if err:
                    logger.error(f"skipping invalid job {job.id}: {err}")
                    typer.echo(typer.style(f"\n> [cron] skipping invalid job {job.id}: {err}", fg=typer.colors.RED))
                    continue
                self.scheduled_jobs[job.id] = job
            valid = [j for j in jobs if j['id'] in self.scheduled_jobs]
            if valid:
                logger.info(f"loaded {len(valid)} durable job(s)")
                typer.echo(typer.style(f"\n> [cron] loaded {len(valid)} durable job(s)", fg=typer.colors.GREEN))
        except JSONDecodeError as e:
            logger.error(f"加载持久化定时任务时json解析出现错误：{str(e)}")
        except Exception as e:
            logger.error(f"加载持久化定时任务时出现异常：{str(e)}")

    def schedule_job(self, cron: str, prompt: str, recurring: bool = True, durable: bool = True) -> CronJob | str: