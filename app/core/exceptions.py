class LLMError(Exception):
    pass

class LLMRateLimitError(LLMError):
    pass

class LLMTimeoutError(LLMError):
    pass

class LLMAuthError(LLMError):
    pass