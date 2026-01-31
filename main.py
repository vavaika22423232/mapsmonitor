"""
Main entry point for Telegram Forwarder.
"""
import os
import sys
import asyncio
import logging

from ingest.dispatcher import create_and_run_dispatcher
from utils.logging import setup_logging


def _get_env_int(name: str, default: int) -> int:
    """Read integer env var with fallback."""
    value = os.getenv(name, str(default))
    try:
        return int(value)
    except ValueError:
        raise ValueError(f"{name} must be an integer")


def _get_log_level() -> int:
    """Read log level from env (INFO by default)."""
    level_str = os.getenv('LOG_LEVEL', 'INFO').upper()
    return logging._nameToLevel.get(level_str, logging.INFO)


def main():
    """Application entry point."""
    setup_logging(_get_log_level())
    logger = logging.getLogger(__name__)
    
    api_id = os.getenv('TELEGRAM_API_ID')
    api_hash = os.getenv('TELEGRAM_API_HASH')
    session = os.getenv('TELEGRAM_SESSION')
    
    if not api_id or not api_hash or not session:
        logger.error("TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_SESSION are required")
        sys.exit(1)
    
    try:
        api_id = int(api_id)
    except ValueError:
        logger.error("TELEGRAM_API_ID must be numeric")
        sys.exit(1)
    
    sources = os.getenv(
        'SOURCE_CHANNELS',
        'UkraineAlarmSignal,war_monitor,napramok,ukrainsiypposhnik,povitryanatrivogaaa,'
        'raketa_trevoga,monikppy,radarraketppo,korabely_media,odessaveter,'
        'veselyy_pivden,sectorv666,vanek_nikolaev,monitor1654'
    ).split(',')
    target = os.getenv('TARGET_CHANNEL', 'mapstransler')
    
    poll_interval = _get_env_int('POLL_INTERVAL', 30)
    dedup_interval = _get_env_int('DEDUP_INTERVAL', 300)
    
    async def _run():
        await create_and_run_dispatcher(
            api_id=api_id,
            api_hash=api_hash,
            session=session,
            sources=sources,
            target=target,
            poll_interval=poll_interval,
            dedup_ttl=dedup_interval
        )
    
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        logger.info("Shutdown requested")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise


if __name__ == '__main__':
    main()
