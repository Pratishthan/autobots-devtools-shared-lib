# ABOUTME: LLM factory for the dynagent reference architecture.
# ABOUTME: Returns a configured ChatGoogleGenerativeAI instance.

from langchain_google_genai import ChatGoogleGenerativeAI


def lm() -> ChatGoogleGenerativeAI:
    """Return the default LLM instance."""
    return ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0)
