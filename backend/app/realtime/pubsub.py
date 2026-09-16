"""
INDRA streaming bus.

TWO BACKENDS, selected at startup:

  DEMO MODE (default, KAFKA_BOOTSTRAP_SERVERS unset):
    In-process asyncio queue. Every publish/subscribe call works identically
    to a real Kafka producer/consumer pair. No broker required.

  LIVE MODE (KAFKA_BOOTSTRAP_SERVERS set, e.g. "redpanda:9092"):
    Uses kafka-python KafkaProducer/KafkaConsumer. publishes every event to
    the real Kafka/Redpanda topic "indra.events". A background consumer
    task relays messages back to the in-process subscriber list so WebSocket
    fan-out continues to work identically from the callers' perspective.
    The in-process bus remains active as a local relay — Kafka is the
    durable store, the in-process queue is the last-mile to WebSocket clients.

Topic: "indra.events" (all event types published to one topic; event_type
field in the message payload differentiates them — simplest single-broker
setup that proves the real Kafka path works).

§1 upgrade: real Kafka/Redpanda producer/consumer path added.
"""
import asyncio
import datetime as dt
import json
import logging
import os
from collections import deque

log = logging.getLogger("indra.realtime.pubsub")

_KAFKA_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "")
_KAFKA_TOPIC = "indra.events"

_subscribers: list[asyncio.Queue] = []
_recent_events = deque(maxlen=200)

# ---- Kafka producer (created lazily, None in Demo Mode) ------------------
_kafka_producer = None
_kafka_init_failed = False


def _get_kafka_producer():
    global _kafka_producer, _kafka_init_failed
    if not _KAFKA_SERVERS or _kafka_init_failed:
        return None
    if _kafka_producer is not None:
        return _kafka_producer
    try:
        from kafka import KafkaProducer
        _kafka_producer = KafkaProducer(
            bootstrap_servers=_KAFKA_SERVERS.split(","),
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            request_timeout_ms=5000,
        )
        log.info("Kafka producer connected to %s, topic=%s", _KAFKA_SERVERS, _KAFKA_TOPIC)
        return _kafka_producer
    except Exception as exc:
        log.error("Kafka producer init failed (%s) — using in-process bus.", exc)
        _kafka_init_failed = True
        return None


# ---- In-process bus (always active — last-mile relay to WebSocket) --------
def subscribe() -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue()
    _subscribers.append(q)
    return q


def unsubscribe(q: asyncio.Queue):
    if q in _subscribers:
        _subscribers.remove(q)


def _deliver_local(message: dict):
    """Fan out to all in-process subscribers (runs in the asyncio event loop)."""
    _recent_events.append(message)
    for q in list(_subscribers):
        try:
            q.put_nowait(message)
        except asyncio.QueueFull:
            pass


async def publish(event_type: str, payload: dict) -> dict:
    message = {
        "type": event_type,
        "payload": payload,
        "ts": dt.datetime.utcnow().isoformat(),
    }

    # --- Kafka publish (fire-and-forget, never blocks ingestion) -----------
    producer = _get_kafka_producer()
    if producer is not None:
        try:
            producer.send(_KAFKA_TOPIC, value=message)
            # Don't flush synchronously — producer batches are fine for our
            # throughput; a background consumer relays back to local bus.
        except Exception as exc:
            log.warning("Kafka send failed (%s) — message still delivered locally.", exc)

    # --- Local in-process delivery (always) --------------------------------
    _deliver_local(message)
    return message


def recent(limit: int = 20):
    return list(_recent_events)[-limit:]


# ---- Kafka consumer background task (Live Mode only) ---------------------
async def start_kafka_consumer():
    """Start a background asyncio task that consumes from Kafka and relays
    messages to local WebSocket subscribers. No-op in Demo Mode."""
    if not _KAFKA_SERVERS:
        return

    async def _consume():
        loop = asyncio.get_event_loop()
        try:
            from kafka import KafkaConsumer
            consumer = await loop.run_in_executor(None, lambda: KafkaConsumer(
                _KAFKA_TOPIC,
                bootstrap_servers=_KAFKA_SERVERS.split(","),
                group_id="indra-ws-relay",
                auto_offset_reset="latest",
                value_deserializer=lambda b: json.loads(b.decode("utf-8")),
                consumer_timeout_ms=1000,
            ))
            log.info("Kafka consumer connected, relaying %s → WebSocket.", _KAFKA_TOPIC)
            while True:
                # poll in executor so we don't block the event loop
                records = await loop.run_in_executor(
                    None, lambda: consumer.poll(timeout_ms=500, max_records=50)
                )
                for tp, msgs in records.items():
                    for msg in msgs:
                        _deliver_local(msg.value)
                await asyncio.sleep(0.1)
        except Exception as exc:
            log.error("Kafka consumer error: %s — WebSocket relay via Kafka disabled.", exc)

    asyncio.create_task(_consume())
