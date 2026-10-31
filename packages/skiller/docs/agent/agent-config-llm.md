# LLM Adapter Implementation

User-facing provider configuration is documented in
[User LLM providers](https://skiller.run/docs/configuration/llm-providers/).
This document covers the implementation behind those provider definitions, not
the configuration file contract.

## Adapter resolution

`DefaultLLMClientResolver` in
`../../src/skiller/infrastructure/llm/default_llm_client_resolver.py` resolves a
typed provider definition into an implementation of the domain `LLMPort`.

| Provider definition | Implementation | Protocol |
| --- | --- | --- |
| `OpenAILLMProviderDefinition` | `openai/openai_llm_port.py`: `OpenAILLMPort` | OpenAI-compatible Chat Completions |
| `CodexLLMProviderDefinition` | `codex/responses_llm_port.py`: `ResponsesLLMPort` | Codex Responses |
| `BedrockLLMProviderDefinition` | `bedrock/converse_llm_port.py`: `ConverseLLMPort` | Amazon Bedrock Converse |

Implementation paths in the table are relative to
`packages/skiller/src/skiller/infrastructure/llm/`.

Provider names do not determine the transport: multiple providers can use the
same adapter. Catalog parsing produces the typed definitions used by the resolver.

## OpenAI-compatible adapter

Configuration reference: [OpenAI-compatible adapter](https://skiller.run/docs/configuration/openai-adapter/).

`OpenAILLMPort` uses the OpenAI SDK's `chat.completions.create` operation.
`OpenAIMapper` translates requests and responses, while
`OpenAIApiKeyDatasource` resolves the configured credential source before the
resolver constructs the port.

Provider-specific `options` are passed to the mapper as `extra_body`. Protocol
mapping and SDK access remain in infrastructure.

See [Chat Completions reasoning](./completions-reasoning.md) for reasoning
parameter handling.

## Bedrock adapter

Configuration reference: [Bedrock adapter](https://skiller.run/docs/configuration/bedrock-adapter/).

`ConverseLLMPort` constructs a Boto3 session using the configured AWS profile
and creates a `bedrock-runtime` client. `BedrockMapper`,
`CollectConverseResponse`, and `ConverseMapper` handle request mapping, stream
collection, and response mapping respectively.

See [Bedrock thinking](./bedrock-thinking.md) for reasoning-specific behavior.

## Codex adapter

Configuration reference: [Codex adapter](https://skiller.run/docs/configuration/codex-adapter/).

`ResponsesLLMPort` uses the Codex Responses protocol. The resolver supplies
`CodexMapper`, `ResponsesMapper`, `CollectCodexResponse`, and
`CodexTurnSessionManager` for protocol mapping, response collection, and turn
session handling.

`CodexCredentialsDatasource` loads and persists OAuth credentials; the port
handles token refresh. Credential contents are not part of the agent's LLM
selection configuration.

## Documentation boundary

Keep SDK behavior, protocol mapping, token refresh, and adapter internals here.
Maintain provider JSON examples, credential configuration, model lists, and
custom-provider instructions in the website's
[LLM providers reference](https://skiller.run/docs/configuration/llm-providers/)
instead of duplicating them locally.
