"""AI module - Groq client and fallback logic."""
from .groq_client import GroqClient
from .fallback import ai_fallback_parse

__all__ = ['GroqClient', 'ai_fallback_parse']
