import sys
import argparse
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from src.graph import run_mca_agent

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

def run_job():
    try:
        run_mca_agent()
    except Exception as e:
        print(f"[Error] Execution failed: {e}")

def start_scheduler():
    scheduler = BlockingScheduler()
    print("=" * 60)
    print(" [Scheduler] Starting MCA Document Automation Agent Scheduler")
    print(" [Scheduler] Initial run commencing now...")
    print("=" * 60)
    run_job()

    scheduler.add_job(run_job, 'interval', hours=24)
    print("\nScheduler started. Running every 24 hours. Press Ctrl+C to exit.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("\nScheduler stopped.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MCA Companies Act 2013 Document Downloader & Classifier")
    parser.add_argument("--once", action="store_true", help="Run once and exit without starting scheduler")
    args = parser.parse_args()

    if args.once:
        run_job()
    else:
        start_scheduler()
