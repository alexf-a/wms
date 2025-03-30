from llm.model_id import ModelID


class ClaudeModelID(ModelID):
    """Claude Model IDs."""
    CLAUDE_3_OPUS = "anthropic.claude-3-opus-20240229"
    CLAUDE_3_SONNET = "anthropic.claude-3-sonnet-20240229"
    CLAUDE_3_HAIKU = "anthropic.claude-3-haiku-20240307"
    CLAUDE_3_5_SONNET = "anthropic.claude-3-5-sonnet-20240620"
    CLAUDE_3_5_HAIKU = "anthropic.claude-3-5-haiku-20240620"
    CLAUDE_3_7_SONNET = "anthropic.claude-3-7-sonnet-20240809"
    CLAUDE_2 = "anthropic.claude-v2"
    CLAUDE_2_1 = "anthropic.claude-v2:1"
    CLAUDE_INSTANT = "anthropic.claude-instant-v1"
