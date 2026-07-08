import os
from pathlib import Path
from typing import List, Dict
from dotenv import load_dotenv
from openai import OpenAI
from google import genai
from ollama import Client as OllamaClient
from anthropic import Anthropic
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.llms import Ollama
from langchain_anthropic import ChatAnthropic


# Read the env file
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# Read configuration from .env file
PROVIDER = os.getenv("PROVIDER", "openai").lower()
MODEL = os.getenv("MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

Message = Dict[str, str]

def chat(messages: List[Message]) -> str:
    if not messages:
        raise ValueError("messages cannot be empty")

    if PROVIDER == "openai":
        return _call_openai(messages)

    if PROVIDER == "ollama":
        return _call_ollama(messages)

    if PROVIDER == "google":
        return _call_gemini(messages)

    if PROVIDER == "anthropic":
        return _call_anthropic(messages)

    raise NotImplementedError(f"Provider '{PROVIDER}' not supported yet")

def _call_openai(messages: List[Message]) -> str:
    """Call OpenAI API."""
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY not set in .env")

    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=MODEL, messages=messages
    )
    return response.choices[0].message.content

def _call_gemini(messages: List[Message]) -> str:
    if not GOOGLE_API_KEY:
        raise ValueError("GOOGLE_API_KEY is not set in the .env file")

    client = genai.Client(api_key=GOOGLE_API_KEY)

    system_text = ""
    contents = []
    for msg in messages:
        if msg["role"] == "system":
            system_text = msg["content"]
        elif msg["role"] == "user":
            contents.append({"role": "user", "parts": [{"text": msg["content"]}]})
        elif msg["role"] == "assistant":
            contents.append({"role": "model", "parts": [{"text": msg["content"]}]})

    config = genai.types.GenerateContentConfig(
        temperature=0,
        system_instruction=system_text if system_text else None,
    )
    response = client.models.generate_content(
        model=MODEL, contents=contents, config=config
    )
    return response.text

def _call_ollama(messages: List[Message]) -> str:
    """Call local Ollama API."""
    client = OllamaClient(host=OLLAMA_HOST)
    response = client.chat(model=MODEL, messages=messages)
    if not response.message or not response.message.content:
        raise RuntimeError("Ollama returned empty response. Is Ollama running?")
    return response.message.content

def _call_anthropic(messages: List[Message]) -> str:
    """Call Anthropic Claude API."""
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY is not set in .env")

    system_text = next(
        (msg["content"] for msg in messages if msg["role"] == "system"),
        None
    )

    anthro_messages = [
        {"role": msg["role"], "content": msg["content"]}
        for msg in messages
        if msg["role"] in ("user", "assistant")
    ]

    if not anthro_messages:
        raise ValueError("Anthropic requires at least one user or assistant message")

    client = Anthropic(api_key=ANTHROPIC_API_KEY)

    response = client.messages.create(
        model=MODEL,
        messages=anthro_messages,
        system=system_text
    )

    return response.content[0].text

def get_langchain_llm():
    """
    Returns Langchain LLM wrapper based on .env PROVIDER.
    Used by agents_v2/ (Langchain-based agents).
    """
    if PROVIDER == "openai":
        return ChatOpenAI(
            model=MODEL,
            temperature=0,
            api_key=OPENAI_API_KEY
        )

    elif PROVIDER == "google":
        return ChatGoogleGenerativeAI(
            model=MODEL,
            temperature=0,
            google_api_key=GOOGLE_API_KEY
        )
    elif PROVIDER == "anthropic":
        return ChatAnthropic(
            model=MODEL,
            temperature=0,
            anthropic_api_key=ANTHROPIC_API_KEY,
        )

    elif PROVIDER == "ollama":
        return Ollama(
            model=MODEL,
            temperature=0,
            base_url=OLLAMA_HOST
        )
    else:
        raise ValueError(f"Unsupported provider: {PROVIDER}")