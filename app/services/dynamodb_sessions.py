import boto3
import json
import logging
import os
import time
from typing import Optional

logger = logging.getLogger(__name__)
_table = None


def _get_table():
    global _table
    if _table is None:
        _table = boto3.resource("dynamodb").Table(os.environ["DYNAMODB_TABLE"])
    return _table


def _new_session() -> dict:
    return {
        "state": "new",
        "call_sid": None,
        "criteria": None,
        "rejection_reasons": [],
        "page": 1,
        "liked_properties": [],
        "current_property": None,
        "seen_urls": [],
    }


def get_session(phone: str) -> dict:
    resp = _get_table().get_item(Key={"phone": phone})
    item = resp.get("Item")
    if not item:
        return _new_session()
    # Deserialize JSON-encoded fields
    for field in ("criteria", "current_property"):
        if isinstance(item.get(field), str):
            item[field] = json.loads(item[field])
    for field in ("rejection_reasons", "liked_properties", "seen_urls"):
        if isinstance(item.get(field), str):
            item[field] = json.loads(item[field])
    return item


def put_session(phone: str, session: dict) -> None:
    item = dict(session)
    item["phone"] = phone
    item["ttl"] = int(time.time()) + 7 * 86400  # 7-day TTL
    # Serialize complex types to JSON strings for DynamoDB
    for field in ("criteria", "current_property"):
        if item.get(field) is not None:
            item[field] = json.dumps(item[field])
    for field in ("rejection_reasons", "liked_properties", "seen_urls"):
        if isinstance(item.get(field), list):
            item[field] = json.dumps(item[field])
    _get_table().put_item(Item=item)
