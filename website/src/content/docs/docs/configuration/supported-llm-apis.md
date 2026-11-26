---
title: Supported LLM APIs
description: Understand the LLM APIs supported by Skiller and the providers that use them.
---

The agent harness is agnostic to the LLM API protocol and provider. Skiller connects the harness to LLM providers through adapters.

## Supported integrations

The following table summarizes the supported adapters, their APIs, and providers:

| API | Adapter | Providers |
| --- | --- | --- |
| OpenAI-compatible Chat Completions | `openai` | MiniMax, Moonshot, DeepSeek, OpenRouter, LM Studio, and compatible endpoints |
| Codex Responses | `codex` | OpenAI Codex |
| Amazon Bedrock Converse | `bedrock` | Models available through Amazon Bedrock |
| Ollama native Chat API (`/api/chat`) | `ollama` | Local or remote Ollama servers |

Codex support uses its dedicated authentication and transport; it does not imply general support for arbitrary OpenAI Responses endpoints. OpenAI-compatible endpoints must support the request features used by your agent, including tool calls when tools are enabled.

## Configure your providers

Use [Add an LLM provider](/docs/getting-started/add-an-llm-provider/) to authenticate from STUI.

See [User LLM providers](/docs/configuration/llm-providers/) for your configured catalog, credentials, and models. To override or add a provider, see [OpenAI](/docs/configuration/openai-adapter/), [Codex](/docs/configuration/codex-adapter/), [Bedrock](/docs/configuration/bedrock-adapter/), or [Ollama](/docs/configuration/ollama-adapter/).
