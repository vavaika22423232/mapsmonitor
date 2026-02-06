"""Tests for message dispatcher."""
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from ingest.dispatcher import MessageDispatcher
from ingest.telegram_client import IncomingMessage, TelegramIngestClient


@pytest.fixture
def mock_telegram():
    """Create mock telegram client that records sent messages."""
    client = MagicMock(spec=TelegramIngestClient)
    client.send_message = AsyncMock(return_value=True)
    client.poll_interval = 30
    return client


@pytest.fixture
def dispatcher(mock_telegram):
    return MessageDispatcher(telegram_client=mock_telegram, dedup_ttl=60)


def make_message(text: str, channel: str = "test_channel", msg_id: int = 1) -> IncomingMessage:
    """Create IncomingMessage for testing."""
    raw = MagicMock()
    raw.media = None
    return IncomingMessage(
        id=msg_id,
        text=text,
        channel=channel,
        timestamp=datetime.now(),
        has_media=False,
        raw_message=raw,
    )


@pytest.mark.asyncio
async def test_process_message_bpla_sends(dispatcher, mock_telegram):
    """process_message parses BPLA and sends to target."""
    msg = make_message("БПЛА Харків (Харківська обл.)", msg_id=1)
    sent = await dispatcher.process_message(msg)
    assert sent >= 1
    mock_telegram.send_message.assert_called()
    call_args = mock_telegram.send_message.call_args
    assert "Харків" in call_args[0][0]


@pytest.mark.asyncio
async def test_process_message_empty_returns_zero(dispatcher):
    """Empty message returns 0."""
    msg = make_message("", msg_id=2)
    sent = await dispatcher.process_message(msg)
    assert sent == 0


@pytest.mark.asyncio
async def test_process_message_informational_skipped(dispatcher, mock_telegram):
    """Informational planned attack messages are skipped."""
    msg = make_message("Запланував удар по об'єкту", msg_id=3)
    sent = await dispatcher.process_message(msg)
    assert sent == 0
    mock_telegram.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_process_message_explosion(dispatcher, mock_telegram):
    """Explosion message is parsed and sent."""
    msg = make_message("Київ - вибухи", msg_id=4)
    sent = await dispatcher.process_message(msg)
    assert sent >= 1
    mock_telegram.send_message.assert_called()
    assert "Вибух" in mock_telegram.send_message.call_args[0][0] or "вибух" in mock_telegram.send_message.call_args[0][0].lower()


@pytest.mark.asyncio
async def test_dispatcher_stats(dispatcher, mock_telegram):
    """Dispatcher stats track processed and sent counts."""
    msg = make_message("БПЛА Харків (Харківська обл.)", msg_id=5)
    await dispatcher.process_message(msg)
    stats = dispatcher.stats
    assert stats["processed"] >= 1
    assert stats["sent"] >= 1
    assert "cache_size" in stats
