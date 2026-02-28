"""
Shared LLM factory — all agents use the same provider config.
Uses Mistral API (OpenAI-compatible endpoint).
"""

from dotenv import load_dotenv
from langchain_mistralai import ChatMistralAI
from config import LLM as C

load_dotenv()


def _build_mistral_chat(model: str, temperature: float, streaming: bool) -> ChatMistralAI:
    # MISTRAL_API_KEY is read automatically from the environment by ChatMistralAI
    return ChatMistralAI(
        model=model,
        temperature=temperature,
        streaming=streaming,
    )


def build_llm(streaming: bool = False) -> ChatMistralAI:
    return _build_mistral_chat(
        model=C.CHARACTER_MODEL,
        temperature=C.CHARACTER_TEMP,
        streaming=streaming,
    )


def build_mistral_llm(streaming: bool = False) -> ChatMistralAI:
    return _build_mistral_chat(
        model=C.SUSPICION_MODEL,
        temperature=C.SUSPICION_TEMP,
        streaming=streaming,
    )


def build_win_check_llm(streaming: bool = False) -> ChatMistralAI:
    return _build_mistral_chat(
        model=C.WIN_CHECK_MODEL,
        temperature=C.WIN_CHECK_TEMP,
        streaming=streaming,
    )
