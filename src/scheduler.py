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

def start_scheduler_service():
    """
    Run standalone APScheduler blocking process for unattended server deployments.
    Triggers daily_etl at 00:00 IST every day.
    """
    from daily_etl import run_daily_pipeline

    scheduler = create_scheduler(blocking=True)

    @scheduler.scheduled_job('cron', hour=0, minute=0)
    def scheduled_etl_job():
        print(f"\n[Scheduler] Triggering Daily UrbanPulse ETL at {datetime.now()} (00:00 IST)")
        run_daily_pipeline()

    print(f"[Scheduler] UrbanPulse scheduler started. Scheduled to run daily at 00:00 {DEFAULT_TIMEZONE}...")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("[Scheduler] Stopped.")

if __name__ == "__main__":
    start_scheduler_service()
