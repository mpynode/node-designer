"""LLM assistant backend for the Node Designer (Shape A).

An embedded chat assistant that can build / edit mPy nodes interactively by
calling a small set of tools that map onto the public wrapper API
(``create``, ``add_input_attr``, ``add_output_attr``, ``set_*_expression``,
``set_variable`` ...). The model runs in the cloud (Anthropic or Gemini); the
tools execute locally, on Maya's main thread, inside undo chunks.

Modules:
  * ``config``          -- provider selection + per-provider key/model prefs.
  * ``tools``           -- tool schemas + main-thread dispatch to the API.
  * ``system_prompt``   -- the API cheat-sheet that teaches the model.
  * ``anthropic_client``-- stdlib (urllib) Messages-API tool-calling loop.
  * ``gemini_client``   -- stdlib (urllib) generateContent tool-calling loop.

Both clients expose an identical Qt signal surface, so ``make_client`` can
swap them based on the selected provider without the panel caring which is
live. The Qt panel that hosts the chat lives in
``ui/widgets/assistant_panel.py``.
"""

from __future__ import annotations

from mpynode.ui.llm import config


def make_client(ctx_provider, parent=None, provider=None):
    """Build the assistant client for the selected provider.

    ``ctx_provider()`` returns a fresh ``tools.ToolContext`` per turn.
    ``provider`` overrides the stored preference when given.
    """
    provider = provider or config.get_provider()
    if provider == "gemini":
        from mpynode.ui.llm.gemini_client import GeminiClient

        return GeminiClient(ctx_provider, parent)
    if provider == "openai":
        from mpynode.ui.llm.openai_client import OpenAIClient

        return OpenAIClient(ctx_provider, parent)
    if provider == "claude_cli":
        from mpynode.ui.llm.claude_cli_client import ClaudeCliClient

        return ClaudeCliClient(ctx_provider, parent)
    if provider == "gemini_cli":
        from mpynode.ui.llm.gemini_cli_client import GeminiCliClient

        return GeminiCliClient(ctx_provider, parent)
    if provider == "codex_cli":
        from mpynode.ui.llm.codex_cli_client import CodexCliClient

        return CodexCliClient(ctx_provider, parent)
    from mpynode.ui.llm.anthropic_client import AssistantClient

    return AssistantClient(ctx_provider, parent)
