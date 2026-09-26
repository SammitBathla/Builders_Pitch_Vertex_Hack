"""Provider-neutral LLM failure type (Requirement 11.2: fail loudly per case, never
silently). Both the Anthropic client and the (unused-by-default) Bedrock client raise this
so callers don't need to know which provider is active."""


class LLMUnavailableError(RuntimeError):
    pass
