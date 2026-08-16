from datetime import datetime
from dataclasses import dataclass, asdict
import threading
from json import JSONDecodeError
from pathlib import Path
import json
import time
import random
import typer
from src.logs.app_log import get_log
from src.tools.tools_registry import get_tools_registry

logger = get_log()

DURABLE_PATH = Path.home() / ".sebastian" / ".scheduled_tasks.json"

@dataclass
class CronJob:
    """
    Args:
        id: Cron job的ID
        cron: Unix标准的CronJob五段表达式
        prompt: 触发时注入给Agent的消息
        recurring: True=周期性, False=一次性
        durable: True=跨会话
    """
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

    def load_durable_jobs(self):
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
        """Register a new cron job. Returns CronJob or error string"""
        err = self.validate_cron(cron)
        if err:
            return err
        job = CronJob(
            id=f"cron_{random.randint(0, 999999):06d}",
            cron = cron,
            prompt = prompt,
            recurring = recurring,
            durable = durable
        )
        with self.cron_lock:
            self.scheduled_jobs[job.id] = job
        if durable:
            self.save_durable_jobs()
        typer.echo(typer.style(f"\n> [cron register] {job.id} '{cron}' -> {prompt[:40]}", fg=typer.colors.GREEN))
        logger.info(f"{job.id} '{cron}' -> {prompt}")
        return job

    def cancel_job(self, job_id: str) -> str | None:
        """Cancel a cron job"""
        with self.cron_lock:
            job = self.scheduled_jobs.pop(job_id, None)
        if not job:
            return None
        #如果被取消的定时任务durable（即已经在.json文件中保存，则重写.json文件）
        if job.durable:
            self.save_durable_jobs()
        typer.echo(typer.style(f"\n> [cron cancel] {job_id}", fg=typer.colors.YELLOW))
        logger.info(f"{job_id} cancelled")
        return f"Cancelled {job_id}"

    def cron_scheduler_loop(self):
        """Run cron job in independent daemon thread"""
        while True:
            time.sleep(1)
            now = datetime.now()
            minute_marker = now.strftime("%Y-%m-%d %H:%M")
            with self.cron_lock:
                for job in list(self.scheduled_jobs.values()):
                    try:
                        if self.cron_matches(job.cron, now):
                            if self._last_fired.get(job.id) != minute_marker:
                                self.cron_queue.append(job)
                                self._last_fired[job.id] = minute_marker
                                typer.echo(typer.style(f"\n> [cron fire] {job.id} -> {job.prompt[:40]}", fg=typer.colors.GREEN))
                                logger.info(f"Cron fire: {job.id} -> {job.prompt}")
                            if not job.recurring:
                                self.scheduled_jobs.pop(job.id, None)
                                if job.durable:
                                    self.save_durable_jobs()
                    except Exception as e:
                        typer.echo(typer.style(f"\n> [cron error] {job.id}: {str(e)}", fg=typer.colors.RED))
                        logger.error(f"Cron error: {job.id}: {str(e)}")

    def consume_cron_queue(self) -> list[CronJob]:
        """Consume fired jobs from cron_queue"""
        with self.cron_lock:
            fired = list(self.cron_queue)
            self.cron_queue.clear()
        return fired

    def has_cron_queue(self) -> bool:
        """Return whether fired cron jobs are waiting to be delivered."""
        with self.cron_lock:
            #cron_queue非空为True,空为False
            return bool(self.cron_queue)

    # -------------Cron Tools：Schedule,List,Cancel ---------------
    def run_schedule_cron(self, cron: str, prompt: str, recurring: bool = True, durable: bool = True) -> str:
        result = self.schedule_job(cron, prompt, recurring, durable)
        if isinstance(result, str):
            return json.dumps({
                "success": False,
                "error": result
            }, ensure_ascii=False)
        return json.dumps({
            "success": True,
            "summary": f"Scheduled {result.id}: '{cron}' -> {prompt}"
        }, ensure_ascii=False)

    def run_list_crons(self) -> str:
        with self.cron_lock:
            jobs = list(self.scheduled_jobs.values())
        if not jobs:
            return json.dumps({
                "success": False,
                "error": "No existed cron jobs "
            }, ensure_ascii=False)
        lines = []
        for j in jobs:
            tag = "recurring" if j.recurring else "one-shot"
            dur = "durable" if j.durable else "session"
            lines.append(f" {j.id}: '{j.cron}' -> {j.prompt[:40]} [{tag}, {dur}]")
        return "\n".join(lines)

    def run_cancel_cron(self, job_id: str) -> str:
        result = self.cancel_job(job_id)
        if result is None:
            return json.dumps({
                "success": False,
                "error": f"Cron job: {job_id} is not found"
            }, ensure_ascii=False)
        return json.dumps({
            "success": True,
            "summary": result
        }, ensure_ascii=False)

CRON_SCHEDULE = CronSchedule()

SCHEDULE_CRON_SCHEMA = {
    "type": "function",
    "function": {
        "name": "schedule_cron",
        "description": "Schedule a cron job. cron is 5-field(Unix format): minute hour day-of-month month day-of-week.",
        "parameters": {
            "type": "object",
            "properties": {
                "cron": {"type": "string", "description": "5-field cron expression"},
                "prompt": {"type": "string", "description": "Message to inject when fired"},
                "recurring": {"type": "boolean", "description": "True=recurring, False=one-shot"},
                "durable": {"type": "boolean", "description": "True=persist to disk"}
            },
            "required": ["cron", "prompt"]
        }
    }
}

LIST_CRONS_SCHEMA= {
    "type": "function",
    "function": {
        "name": "list_crons",
        "description": "List all registered cron jobs.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
}

CANCEL_CRON_SCHEMA = {
    "type": "function",
    "function": {
        "name": "cancel_cron",
        "description": "Cancel a cron job by ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "job_id": {"type": "string", "description": "Job's ID"}
            },
            "required": ["job_id"]
        }
    }
}

get_tools_registry().register_tool("schedule_cron", CRON_SCHEDULE.run_schedule_cron, SCHEDULE_CRON_SCHEMA, for_agent="Brain_Agent")
get_tools_registry().register_tool("list_crons", CRON_SCHEDULE.run_list_crons, LIST_CRONS_SCHEMA, for_agent="Brain_Agent")
get_tools_registry().register_tool("cancel_cron", CRON_SCHEDULE.run_cancel_cron, CANCEL_CRON_SCHEMA, for_agent="Brain_Agent")

#启动守护线程
CRON_SCHEDULE.load_durable_jobs()
threading.Thread(target=CRON_SCHEDULE.cron_scheduler_loop, daemon=True).start()
typer.echo(typer.style(f"\n> [cron] scheduler thread started", fg=typer.colors.GREEN))
logger.info(f"Scheduler thread started")
