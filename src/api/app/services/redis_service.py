import json
from copy import deepcopy
from typing import List
from random import randrange
from datetime import datetime

import redis
import shortuuid

from app.db.postgres import get_db

from app.core.config import config
from app.core.logger import logger
from app.core.authorization import get_user_details
from app.core.constants import INTRODUCTION_MESSAGE

from app.repositories.action_details import Repository
from app.repositories.list_actions import Repository as ListRepository

from app.models.utils import Event
from app.models.action_details import Model, Status
from app.models.list_actions import (
    Status as ListActionStatus,
    ListActionStatusItem,
    Model as ListModel,
)

from app.services.util_service import send_message
from app.services.text_service import text_service


class Service:
    """
    Service for scheduling and handling message events using Redis.

    Responsibilities:
    - Schedule outbound messages with a randomized delay.
    - Buffer multi-line inbound messages and emit when buffer expires.
    - React to Redis key expiration events to dispatch buffered content.

    Note:
    - This service relies on Redis keyspace notifications (expired events).
    """

    def __init__(self, db: int):
        """
        Initialize the Redis-backed service.

        Args:
            db: SQLAlchemy session for persisting action details.
        """
        self.redis_client: redis.Redis = redis.Redis(
            host=config["redis"]["host"], port=config["redis"]["port"], db=db
        )
        self.min_wait = config["redis"]["schedule_send"]["min_wait"]
        self.max_wait = config["redis"]["schedule_send"]["max_wait"]
        self.db = db
        logger.debug(
            "Redis Service initialized with host=%s port=%s db=%s min_wait=%s max_wait=%s",
            config["redis"]["host"],
            config["redis"]["port"],
            db,
            self.min_wait,
            self.max_wait,
        )

    def schedule_send(
        self,
        action_id: int,
        recruiter_id: int,
        applicants: list[int],
        content: str = INTRODUCTION_MESSAGE,
    ) -> List[ListActionStatusItem]:
        """
        Schedule messages to a list of applicants by spacing them with a random delay.

        Stores a per-applicant "bk" payload and a volatile key used to trigger expiration
        handling. If a schedule already exists for an applicant, it is left unchanged.

        Args:
            action_id: Action identifier for tracking.
            recruiter_id: Sender user ID.
            applicants: List of applicant IDs to schedule messages for.
            content: Text content to send (may be used downstream).
            db: Redis logical database index for scheduling.

        Returns:
            A list of ListActionStatusItem summarizing scheduled and unchanged applicants.
        """
        logger.info(
            "Scheduling send: action_id=%s recruiter_id=%s applicants_count=%s",
            action_id,
            recruiter_id,
            len(applicants),
        )
        current_ts = int(datetime.now().timestamp())
        try:
            latest_ts = self.redis_client.get("latest")
            if latest_ts:
                latest_ts = int(latest_ts.decode("utf-8"))  # type: ignore
        except Exception:
            logger.exception("Failed to GET latest timestamp from redis")
            latest_ts = None

        if latest_ts is None or latest_ts < current_ts:  # type: ignore
            latest_ts = current_ts
        logger.debug("Latest timestamp for scheduling: %s", latest_ts)
        updated = []
        no_change = []

        for applicant in applicants:
            try:
                exists = self.redis_client.get(f"{applicant}_bk")
            except Exception:
                logger.exception(
                    "Failed to GET schedule bk for applicant=%s", applicant
                )
                exists = None

            if not exists:
                gap = randrange(self.min_wait, self.max_wait)
                latest_ts += gap  # type: ignore
                logger.debug(
                    "Scheduling applicant=%s with gap=%s seconds; scheduled_ts=%s",
                    applicant,
                    gap,
                    latest_ts,
                )
                event = Event(
                    mid=shortuuid.uuid(),
                    timestamp=datetime.fromtimestamp(float(latest_ts)).strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    ),
                    content=content,
                    chat_id=f"{applicant}@s.whatsapp.net",
                    receiver_id=applicant,
                    sender_id=recruiter_id,
                    msg_type="text",
                )
                data = {
                    "action_id": action_id,
                    "event": event.model_dump(exclude_none=True),
                }
                try:
                    self.redis_client.set(
                        str(applicant) + "_bk",
                        json.dumps(data).encode("utf-8"),
                    )
                    ttl = latest_ts - current_ts
                    self.redis_client.setex(
                        str(applicant),
                        ttl,
                        "",
                    )
                    self.redis_client.set(
                        "latest",
                        latest_ts,
                    )
                except Exception:
                    logger.exception(
                        "Failed to set schedule keys for applicant=%s",
                        applicant,
                    )

                detail = Model(
                    action_id=action_id,
                    applicant_id=applicant,
                    status=Status.SCHEDULED,
                    additional_config={"event": event.model_dump(exclude_none=True)},
                    scheduled_at=datetime.fromtimestamp(latest_ts),
                )  # type: ignore
                updated.append(applicant)
                logger.info(
                    "Applicant scheduled: action_id=%s applicant_id=%s scheduled_at=%s",
                    action_id,
                    applicant,
                    latest_ts,
                )
            else:
                logger.debug(
                    "Schedule exists for applicant=%s; leaving unchanged.", applicant
                )
                detail = Model(
                    action_id=action_id,
                    applicant_id=applicant,
                    status=Status.NO_CHANGE,
                    additional_config={"exists": exists.decode("utf-8")},  # type: ignore
                )
                no_change.append(applicant)
            try:
                actions_repo = Repository(get_db())
                table = actions_repo.create(detail)

                actions_repo.close()
            except Exception:
                logger.exception(
                    "Failed to persist action detail: action_id=%s applicant_id=%s status=%s",
                    action_id,
                    detail.applicant_id,
                    detail.status,
                )

        result = []
        if updated:
            result.append(
                ListActionStatusItem(
                    status=ListActionStatus.COMPLETED,
                    applicants=updated,
                )
            )
        if no_change:
            result.append(
                ListActionStatusItem(
                    status=ListActionStatus.NO_CHANGE,
                    applicants=no_change,
                )
            )

        logger.info(
            "Scheduling result: updated=%s no_change=%s",
            len(updated),
            len(no_change),
        )
        return result

    def handle_expiry(self):
        """
        Listen for Redis key expiration events and dispatch buffered messages.

        Args:
            db: Redis logical database index to subscribe for expiration events.

        Behavior:
            - Subscribes to __keyevent@<db>__:expired channel.
            - For expired keys, retrieves '{key}_bk' payload and sends the message.
            - When db == 0, stitches multi-line buffered content and sends typing event first.
        """
        logger.info(
            "Starting expiry handler for Redis",
        )
        pubsub = self.redis_client.pubsub()
        try:
            self.redis_client.config_set("notify-keyspace-events", "Ex")
            logger.debug(
                "Configured Redis notify-keyspace-events to 'Ex' for expiration events."
            )
        except Exception:
            logger.exception("Failed to set Redis notify-keyspace-events to 'Ex'")

        channel = f"__keyevent@{self.db}__:expired"
        try:
            pubsub.psubscribe(channel)
            logger.info("Subscribed to keyevent channel: %s", channel)
        except Exception:
            logger.exception("Failed to subscribe to channel: %s", channel)
            return

        for message in pubsub.listen():
            try:
                if message["type"] != "pmessage":
                    continue
                expired_key = message["data"]
                if isinstance(expired_key, bytes):
                    expired_key = expired_key.decode("utf-8")
                logger.debug("Received expiration for key=%s", expired_key)
                key = deepcopy(expired_key)
                expired_key = f"{expired_key}_bk"
                event = self.redis_client.get(expired_key)
                if not event:
                    logger.debug("No payload found for expired key=%s", expired_key)
                    continue

                event = event.decode("utf-8")  # type: ignore
                try:
                    self.redis_client.delete(expired_key)
                    logger.debug(
                        "Deleted payload key=%s after expiration.", expired_key
                    )
                except Exception:
                    logger.exception("Failed to delete payload key=%s", expired_key)

                if self.db == 0:
                    logger.debug(
                        "Handling multi-line buffer flush for key=%s (db=0).",
                        expired_key,
                    )
                    events = json.loads(event)
                    content = "\n".join([e["content"] for e in events])
                    event = events[0]
                    event["content"] = content
                    logger.info("Dispatching event for key=%s", expired_key)
                    typing_event = Event(
                        mid=shortuuid.uuid(),
                        timestamp=datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                        msg_type="typing",
                        sender_id=event["receiver_id"],
                        receiver_id=event["sender_id"],
                        chat_id=event["chat_id"],
                    )
                    user_detail = get_user_details(event["receiver_id"], get_db())
                    send_message(
                        user_details=user_detail,
                        applicant_id=event["sender_id"],
                        event=typing_event,
                        key=key,
                    )
                    text_service.parse_event(event, expired_key)
                else:
                    data = json.loads(event)
                    schedule_event = Event.model_validate(data["event"])
                    user_detail = get_user_details(
                        str(schedule_event.sender_id), get_db()
                    )
                    # to-do: update action_details and list_actions
                    list_repo = ListRepository(get_db())
                    list_ = list_repo.get(data["action_id"])
                    list_ = ListModel.model_validate(list_)
                    if list_.status == ListActionStatus.INITIATED:
                        list_repo.update_by_id(
                            data["action_id"], ListActionStatus.IN_PROGRESS
                        )
                    actions_repo = Repository(get_db())
                    actions_repo.update_by_action_id(
                        data["action_id"], schedule_event.receiver_id, Status.COMPLETED
                    )
                    items = actions_repo.get_by_action_id(data["action_id"])
                    statuses = [Model.model_validate(item).status for item in items]
                    if Status.SCHEDULED not in statuses:
                        list_repo.update_by_id(
                            data["action_id"], ListActionStatus.COMPLETED
                        )
                    actions_repo.close()
                    list_repo.close()
                    send_message(
                        user_details=user_detail,
                        applicant_id=schedule_event.receiver_id,
                        event=schedule_event,
                        key=f"{schedule_event.sender_id}_{schedule_event.receiver_id}",
                    )
            except Exception:
                logger.exception("Error while handling expiry message: %s", message)

    def multi_line_handler(self, key: str, event: dict, ttl: int):
        """
        Buffer multi-line inbound messages and reset expiry window.

        Stores/updates a JSON array under:
        - key: volatile entry with TTL (buffer lifetime)
        - f\"{key}:latest\": mirror of latest buffer content without TTL (for quick read)

        Args:
            key: Redis key prefix used for this buffer.
            event: Single message event to append to the buffer.
            ttl: Time-to-live in seconds for the buffer key.
            db: Redis logical database index.

        Returns:
            None
        """
        logger.debug(
            "[multi_line_handler] key=%s ttl=%s appending event keys=%s",
            key,
            ttl,
            list(event.keys()),
        )
        try:
            data = self.redis_client.get(f"{key}_bk")
        except Exception:
            logger.exception(
                "[multi_line_handler] Failed to GET latest for key=%s",
                key,
            )
            data = None

        if data:
            try:
                events = json.loads(data.decode("utf-8"))  # type: ignore
                events.append(event)
                updated_events = json.dumps(events).encode("utf-8")
                self.redis_client.setex(key, ttl, updated_events)
                self.redis_client.set(
                    f"{key}_bk",
                    updated_events,
                )
                logger.debug(
                    "[multi_line_handler] Appended event; buffer size=%s key=%s",
                    len(events),
                    key,
                )
            except Exception:
                logger.exception(
                    "[multi_line_handler] Failed to append and persist buffer for key=%s",
                    key,
                )
        else:
            try:
                raw_json = json.dumps([event]).encode("utf-8")
                self.redis_client.setex(key, ttl, raw_json)
                self.redis_client.set(f"{key}_bk", raw_json)
                logger.debug(
                    "[multi_line_handler] Created new buffer for key=%s ttl=%s",
                    key,
                    ttl,
                )
            except Exception:
                logger.exception(
                    "[multi_line_handler] Failed to create buffer for key=%s", key
                )

    def cancel_action(self, applicant_id: int):
        exists = self.redis_client.delete(f"{applicant_id}_bk", str(applicant_id))
        if exists:
            logger.info("Cancelled action for applicant %s", applicant_id)
        else:
            logger.warning("No active action found for applicant %s", applicant_id)
