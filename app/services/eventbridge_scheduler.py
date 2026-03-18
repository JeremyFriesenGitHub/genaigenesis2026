import boto3
import json
import logging
import os
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)
_scheduler = None

SCHEDULER_GROUP = os.environ.get("EVENTBRIDGE_SCHEDULER_GROUP", "personaplex-cooldowns")
LAMBDA_ARN = os.environ.get("LAMBDA_FUNCTION_ARN", "")
ROLE_ARN = os.environ.get("LAMBDA_ROLE_ARN", "")


def _client():
    global _scheduler
    if _scheduler is None:
        _scheduler = boto3.client("scheduler")
    return _scheduler


def schedule_resume_search(phone: str, delay_seconds: int = 3600) -> None:
    """Create a one-time EventBridge schedule to fire resume_search after delay."""
    fire_at = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
    schedule_name = f"resume-{phone.replace('+', '').replace(' ', '')}"
    _client().create_schedule(
        GroupName=SCHEDULER_GROUP,
        Name=schedule_name,
        ScheduleExpression=f"at({fire_at.strftime('%Y-%m-%dT%H:%M:%S')})",
        FlexibleTimeWindow={"Mode": "OFF"},
        Target={
            "Arn": LAMBDA_ARN,
            "RoleArn": ROLE_ARN,
            "Input": json.dumps({"type": "resume_search", "phone": phone}),
        },
    )
    logger.info("Scheduled resume_search for %s at %s", phone, fire_at)


def delete_resume_search(phone: str) -> None:
    """Cancel a pending resume_search schedule (e.g. on STOP)."""
    schedule_name = f"resume-{phone.replace('+', '').replace(' ', '')}"
    try:
        _client().delete_schedule(GroupName=SCHEDULER_GROUP, Name=schedule_name)
    except Exception:
        pass  # Ignore if already fired or not found
