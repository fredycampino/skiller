# Agent LLM Response

`LLMResponse` is the common response returned by an LLM port. The
`finish_type` field classifies how the response ended and is the domain-level
value that application code should use.

```python
response.finish_type  # LLMFinishType
response.error        # human-readable detail, when applicable
response.error_code   # stable machine-readable detail, when applicable
```

`finish_type` is required. Every LLM port must populate it before returning a
response. Provider-specific terminal fields such as OpenAI `finish_reason`,
Bedrock `stopReason`, and Codex `status` are consumed inside infrastructure and
do not cross the LLM port boundary.

The agent runner accepts only `stop` and `tool_calls`. Every invalid-response,
error, or unknown value terminates the LLM request without publishing partial
content as a final answer.

## Values

### Normal outcomes

| Value | Meaning |
| --- | --- |
| `stop` | The provider completed a usable text response. |
| `tool_calls` | The provider completed a response containing tool calls that the agent must execute or continue. |

### Provider response is not usable

| Value | Meaning |
| --- | --- |
| `invalid_response_length` | Generation ended because of an output-length limit. The response is not accepted as a normal completion. |
| `invalid_response_content_filter` | Generation was interrupted by a provider content filter. |

### Request or transport errors

| Value | Meaning |
| --- | --- |
| `error_api_key_missing` | The selected provider has no API key configured. |
| `error_request_failed` | The provider request or authentication request failed. |
| `error_stream` | A streaming response failed before a valid terminal response was collected. |

### Malformed or incomplete provider response

| Value | Meaning |
| --- | --- |
| `error_missing_choices` | Chat Completions response has no usable `choices` collection. |
| `error_missing_message` | A choice has no usable message payload. |
| `error_missing_finish_reason` | The provider omitted the field that identifies how generation ended. |
| `error_missing_content` | A response expected to contain text has no usable content. |
| `error_missing_tool_calls` | A response expected to contain tool calls has none. |
| `error_malformed_response` | The response has an inconsistent or invalid shape. |
| `unknown` | The provider returned an unrecognized finish status. |

For error and invalid-response values, `error_code` identifies the stable
machine-readable reason and `error` contains the concrete diagnostic message.
For example:

```python
response.finish_type == LLMFinishType.ERROR_STREAM
response.error_code == "stream_failed"
response.error == "Codex stream failed: ..."
```

The complete enum is defined in
`skiller.domain.agent.llm.finish_type.LLMFinishType`.
