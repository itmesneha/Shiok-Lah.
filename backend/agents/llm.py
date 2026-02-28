# backend/agents/llm.py
"""
LLM Factory for Shiok Lah!

This module provides a factory for creating LLM instances using Mistral API.
It supports different models for character dialogue, suspicion evaluation,
and win condition checking.
"""

from typing import Literal, Optional, Dict, Any
import requests
import json
from ..config import LLM


class MistralLLM:
    """
    Wrapper around Mistral API for LLM interactions.
    
    Attributes:
        api_url: Mistral API endpoint
        model: Model name to use
        temperature: Temperature for sampling
        max_tokens: Maximum tokens to generate
        api_key: Mistral API key
    """
    
    def __init__(
        self,
        model: str = LLM.CHARACTER_MODEL,
        temperature: float = LLM.CHARACTER_TEMP,
        max_tokens: int = LLM.CHARACTER_TOKENS,
        api_key: Optional[str] = None
    ):
        """Initialize Mistral LLM with model configuration."""
        self.api_url = "https://api.mistral.ai/v1/chat/completions"
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.api_key = api_key or ""
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
    
    def generate(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        context: Optional[dict] = None
    ) -> str:
        """
        Generate text from the LLM using Mistral API.
        
        Args:
            prompt: User prompt
            system_message: System message for context
            context: Additional context dictionary
            
        Returns:
            Generated text response
            
        Raises:
            Exception: If API request fails
        """
        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }
        
        try:
            response = requests.post(
                self.api_url,
                headers=self.headers,
                data=json.dumps(payload)
            )
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except requests.exceptions.RequestException as e:
            raise Exception(f"Mistral API request failed: {str(e)}")


def get_character_model(api_key: Optional[str] = None) -> MistralLLM:
    """Get LLM instance configured for character dialogue."""
    return MistralLLM(
        model=LLM.CHARACTER_MODEL,
        temperature=LLM.CHARACTER_TEMP,
        max_tokens=LLM.CHARACTER_TOKENS,
        api_key=api_key
    )


def get_suspicion_model(api_key: Optional[str] = None) -> MistralLLM:
    """Get LLM instance configured for suspicion evaluation."""
    return MistralLLM(
        model=LLM.SUSPICION_MODEL,
        temperature=LLM.SUSPICION_TEMP,
        max_tokens=LLM.SUSPICION_TOKENS,
        api_key=api_key
    )


def get_win_check_model(api_key: Optional[str] = None) -> MistralLLM:
    """Get LLM instance configured for win condition checking."""
    return MistralLLM(
        model=LLM.WIN_CHECK_MODEL,
        temperature=LLM.WIN_CHECK_TEMP,
        max_tokens=LLM.WIN_CHECK_TOKENS,
        api_key=api_key
    )
