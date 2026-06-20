"""
Message broker abstraction — internal event bus.
Development: asyncio in-memory queues.
Production: aio-pika (RabbitMQ) — enabled when BROKER_URL starts with amqp://.

Topics (routing keys):
  compliance.drift       — DriftEvent payloads
  compliance.remediation — RemediationJob payloads
  audit.events           — AuditEntry payloads
  siem.export            — NormalizedEvent payloads
  device.audit           — DeviceAuditJob payloads
"""

from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from typing import Any, Callable, Coroutine

import structlog

log = structlog.get_logger(__name__)

MessageHandler = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]


# ── Abstract interface ─────────────────────────────────────────────────────────

class MessageBroker(ABC):
    @abstractmethod
    async def publish(self, topic: str, message: dict[str, Any]) -> None: ...

    @abstractmethod
    async def subscribe(self, topic: str, handler: MessageHandler) -> None: ...

    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...


# ── In-memory broker (development / testing) ──────────────────────────────────

class InMemoryBroker(MessageBroker):
    """
    Asyncio-queue-backed broker for local development and unit tests.
    Supports fan-out to multiple subscribers per topic.
    """

    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue[dict]] = {}
        self._handlers: dict[str, list[MessageHandler]] = {}
        self._worker_tasks: list[asyncio.Task] = []
        self._running = False

    async def publish(self, topic: str, message: dict[str, Any]) -> None:
        queue = self._queues.setdefault(topic, asyncio.Queue(maxsize=10_000))
        try:
            queue.put_nowait(message)
            log.debug("broker.published", topic=topic)
        except asyncio.QueueFull:
            log.warning("broker.queue_full", topic=topic)

    async def subscribe(self, topic: str, handler: MessageHandler) -> None:
        self._handlers.setdefault(topic, []).append(handler)
        self._queues.setdefault(topic, asyncio.Queue(maxsize=10_000))

    async def start(self) -> None:
        self._running = True
        for topic, handlers in self._handlers.items():
            task = asyncio.create_task(
                self._dispatch_loop(topic, handlers),
                name=f"broker-{topic}",
            )
            self._worker_tasks.append(task)
        log.info("broker.started", type="in_memory", topics=list(self._handlers.keys()))

    async def stop(self) -> None:
        self._running = False
        for task in self._worker_tasks:
            task.cancel()
        self._worker_tasks.clear()
        log.info("broker.stopped")

    async def _dispatch_loop(self, topic: str, handlers: list[MessageHandler]) -> None:
        queue = self._queues[topic]
        while self._running:
            try:
                message = await asyncio.wait_for(queue.get(), timeout=1.0)
                for handler in handlers:
                    try:
                        await handler(message)
                    except Exception as exc:
                        log.error("broker.handler_error", topic=topic, error=str(exc))
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break


# ── RabbitMQ broker (production) ──────────────────────────────────────────────

class RabbitMQBroker(MessageBroker):
    """
    aio-pika backed RabbitMQ broker.
    Uses topic exchange with durable queues for guaranteed delivery.
    """

    def __init__(self, url: str) -> None:
        self._url = url
        self._connection = None
        self._channel = None
        self._exchange = None
        self._handlers: dict[str, list[MessageHandler]] = {}

    async def start(self) -> None:
        try:
            import aio_pika
            self._connection = await aio_pika.connect_robust(self._url)
            self._channel = await self._connection.channel()
            await self._channel.set_qos(prefetch_count=10)
            self._exchange = await self._channel.declare_exchange(
                "nexusguard.security",
                aio_pika.ExchangeType.TOPIC,
                durable=True,
            )
            # Bind queues for registered handlers
            for topic, handlers in self._handlers.items():
                queue = await self._channel.declare_queue(
                    f"nexusguard.{topic.replace('.', '_')}",
                    durable=True,
                )
                await queue.bind(self._exchange, routing_key=topic)
                await queue.consume(self._make_consumer(handlers))
            log.info("broker.started", type="rabbitmq", url=self._url)
        except Exception as exc:
            log.error("broker.rabbitmq.start_failed", error=str(exc))
            raise

    async def publish(self, topic: str, message: dict[str, Any]) -> None:
        if not self._exchange:
            raise RuntimeError("Broker not started")
        import aio_pika
        body = json.dumps(message, default=str).encode()
        await self._exchange.publish(
            aio_pika.Message(body=body, content_type="application/json", delivery_mode=2),
            routing_key=topic,
        )

    async def subscribe(self, topic: str, handler: MessageHandler) -> None:
        self._handlers.setdefault(topic, []).append(handler)

    async def stop(self) -> None:
        if self._connection:
            await self._connection.close()
        log.info("broker.stopped")

    def _make_consumer(self, handlers: list[MessageHandler]):
        async def _consume(message) -> None:
            async with message.process():
                payload = json.loads(message.body)
                for handler in handlers:
                    try:
                        await handler(payload)
                    except Exception as exc:
                        log.error("broker.consumer_error", error=str(exc))
        return _consume


# ── Factory & lifecycle ────────────────────────────────────────────────────────

_broker: MessageBroker | None = None


async def init_broker() -> None:
    global _broker
    from app.core.config import settings
    broker_url = settings.celery.BROKER_URL

    if broker_url.startswith("amqp"):
        _broker = RabbitMQBroker(url=broker_url)
    else:
        _broker = InMemoryBroker()

    await _broker.start()
    log.info("broker.initialized", type=type(_broker).__name__, env=settings.ENVIRONMENT)


async def close_broker() -> None:
    global _broker
    if _broker:
        await _broker.stop()
    _broker = None
    log.info("broker.closed")


def get_broker() -> MessageBroker:
    if _broker is None:
        raise RuntimeError("Broker not initialized — call init_broker() during startup")
    return _broker


# ── Domain event bus integration ───────────────────────────────────────────────

async def publish_domain_event(event_type: str, payload: dict) -> None:
    """
    Bridge: publish a domain event to both the message broker and the internal event bus.
    Allows consumers to subscribe via either mechanism.
    """
    try:
        broker = get_broker()
        await broker.publish(f"domain.{event_type}", payload)
    except Exception as exc:
        log.warning("broker.domain_event_publish_failed", event_type=event_type, error=str(exc))
