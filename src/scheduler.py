import sys
import pytz
from datetime import datetime

# Ensure UTF-8 stdout encoding on Windows
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.schedulers.background import BackgroundScheduler
from src.config import DEFAULT_TIMEZONE

def create_scheduler(blocking: bool = True):
    """Create an APScheduler instance configured for IST (Asia/Kolkata)."""
    tz = pytz.timezone(DEFAULT_TIMEZONE)
    scheduler_cls = BlockingScheduler if blocking else BackgroundScheduler
    scheduler = scheduler_cls(timezone=tz)
    return scheduler

def start_scheduler_service(interval_minutes: int = 30, city: str = "top"):
    """
    Run standalone APScheduler blocking process for unattended server deployments.
    Triggers UrbanPulse ETL every 30 minutes (or specified interval).
    """
    from daily_etl import run_daily_pipeline

    scheduler = create_scheduler(blocking=True)

    @scheduler.scheduled_job('interval', minutes=interval_minutes)
    def scheduled_etl_job():
        print(f"\n[Scheduler] Triggering UrbanPulse ETL Refresh at {datetime.now()} ({DEFAULT_TIMEZONE})...")
        run_daily_pipeline(city=city, max_workers=10)

    print(f"[Scheduler] UrbanPulse scheduler started. Scheduled to run every {interval_minutes} minutes ({DEFAULT_TIMEZONE})...")
    print(f"[Scheduler] Executing initial run now...")
    run_daily_pipeline(city=city, max_workers=10)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("[Scheduler] Stopped.")

if __name__ == "__main__":
    start_scheduler_service(interval_minutes=30, city="top")
