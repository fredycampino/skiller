---
title: Bedrock adapter
description: Configure providers that use the Amazon Bedrock Converse API.
---

Uses the Amazon Bedrock Converse API with a named AWS profile. The profile supplies credentials and region through the AWS SDK configuration.

Built-in provider using this adapter:

- Amazon Bedrock (`bedrock`)

## Override providers

Customize the built-in `bedrock` provider by overriding its definition in your [user provider catalog](/docs/configuration/llm-providers/):

```json
{
  "providers": {
    "bedrock": {
      "enabled": true,
      "profile": "my-aws-profile",
      "timeout_seconds": 600,
      "models": [
        {
          "model": "us.anthropic.claude-opus-4-6-v1",
          "context_window_tokens": 1000000,
          "max_output_tokens": 4096
        }
      ]
    }
  }
}
```

Include only the fields you want to change. Omitted fields, including `adapter`, are inherited from the built-in catalog definition. If supplied, `models` replaces the entire inherited list. Use models or inference profiles available to your AWS account and region.

## Define new Bedrock-based providers

Use a new provider name and declare `"adapter": "bedrock"`, following the definition above:

```json
{
  "providers": {
    "my-bedrock": {
      "adapter": "bedrock",
      "...": "..."
    }
  }
}
```

`"..."` represents the remaining provider fields from the previous example; it is not a configuration field. This adds a separate connection without changing the built-in provider. Select its name in your [agent configuration](/docs/configuration/model-selection/).

## Provider fields

The defaults below are the values in the built-in bedrock definition. A new provider must declare these fields explicitly.

| Field | Description | Default |
| --- | --- | --- |
| `enabled` | Makes the provider available. | `true` |
| `profile` | Named AWS profile used by the SDK. | `default` |
| `timeout_seconds` | Positive read timeout in seconds for the Bedrock client. | `600` |
| `models` | Available models; replaces the complete inherited list. | From the included catalog |

## Credentials

Configure the AWS profile before using it. The profile must resolve credentials and a region, and its identity needs permission to invoke the selected model or inference profile.

Provider configuration does not create AWS credentials or grant model access. For guided setup, see [Add an LLM provider](/docs/getting-started/add-an-llm-provider/).

## Models

| Field | Description | Default |
| --- | --- | --- |
| `model` | Model or inference profile identifier supported by Converse in your AWS setup. | Required for each model entry |
| `context_window_tokens` | Positive context window size in tokens. | Required for each model entry |
| `max_output_tokens` | Positive output token limit, sent as inferenceConfig.maxTokens. | `128000` when omitted |

Defining models replaces the full inherited list. Replace the example model and token limits with values available to your AWS account and region.

For agent-level provider, model, and effort selection, see [Model selection](/docs/configuration/model-selection/).
