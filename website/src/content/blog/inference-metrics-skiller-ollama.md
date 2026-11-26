---
title: "Ollama Generation Speed for Text and Tool Calls"
description: "Measure local model generation speed in a real agent workflow, from text responses to tool calls."
socialImage: "/blog/inference-metrics-skiller-ollama/social.png"
publishedAt: 2026-11-25
---

How fast is your local model when it does actual agent work? With Skiller and Ollama, you can see generation speed next to each response, first for a writing task and then for a tool-calling cycle. No benchmark script required.

Ollama serves the model. Skiller handles the conversation, executes tools, and displays the tokens per second reported through generation metrics.

## Set up Skiller

Follow the [Skiller installation guide](/docs/getting-started/installation/), or install it with [pipx](https://pipx.pypa.io/stable/installation/):

```bash
pipx install skiller
```

Already installed? Upgrade it:

```bash
pipx upgrade skiller
```

## Set up Ollama

Install [Ollama](https://ollama.com/download). If its server is not already running, start it in a separate terminal:

```bash
ollama serve
```

Download a model that supports tool calls. For this guide, we use:

```bash
ollama pull hf.co/unsloth/Qwen3.8-27B-GGUF:UD-Q6_K
```

Find more quantizations and their download sizes in the [model files](https://huggingface.co/unsloth/Qwen3.8-27B-GGUF/tree/main).

Check which models are installed:

```bash
ollama list
```

Skiller and Ollama do not need to run on the same machine. For a remote server, download the model there and use its reachable root URL when connecting from Skiller, for example, `http://192.168.1.202:11434`, without `/v1`. Keep access limited to a trusted network.

## Create the @metrics agent

Create the agent in `~/my-agents/metrics`:

```bash
mkdir -p ~/my-agents/metrics
```

Add `~/my-agents` to `flow_paths` in `~/.skiller/settings/config.json`, keeping any existing settings and paths:

```json
{
  "flow_paths": ["~/my-agents"]
}
```

### Create the agent definition

Create `~/my-agents/metrics/metrics.yaml`:

```yaml
name: metrics
description: "Measure Ollama generation speed"
version: "0.1"
start: ask_user

steps:
  - wait_input: ask_user
    prompt: "Write a task to measure generation speed."
    next: respond

  - agent: respond
    config:
      file: "./metrics.agent.json"
    system: "Follow the user's instructions. Answer directly and clearly."
    task: '{{output_value("ask_user").payload.text}}'
    max_turns: 1
    next: ask_user
```

The workflow waits for a task, generates a response, and waits for the next task. No tools are enabled yet.

### Define the agent profile

Create `~/my-agents/metrics/metrics.agent.json` (agent profiles use JSON):

```json
{
  "llm": {
    "provider": "ollama",
    "model": "hf.co/unsloth/Qwen3.8-27B-GGUF:UD-Q6_K",
    "effort": 2
  },
  "context": {
    "window_width_tokens": 32768
  }
}
```

- `llm.provider`: the configured provider to use, here `ollama`.
- `llm.model`: the exact model name configured for that provider.
- `llm.effort`: reasoning effort from 1 to 5. Here, `2` selects the second value in the model’s `effort_mapping`; without a mapping, Skiller omits `think`.
- `context.window_width_tokens`: the agent’s context budget, here 32,768 tokens.

## Connect the Ollama provider

Start a new metrics session from your terminal:

```bash
skiller @metrics
```

In STUI, type `/`, select **auth**, and press Enter. You can also type `/auth` directly.

Select **ollama** and press Enter to open its connection setup.

![Select Ollama in the provider configuration table.](/blog/inference-metrics-skiller-ollama/metrics-auth-providers.svg)

Choose a local connection or enter your remote server URL, then follow the prompts to complete setup.

![Choose a local or remote Ollama connection.](/blog/inference-metrics-skiller-ollama/metrics-ollama-connection.svg)

After setup, Skiller writes an `ollama` entry to `~/.skiller/settings/providers.json` with the server URL and the models it discovered. For a local server with Q8 and Q6 installed:

```json
{
  "providers": {
    "ollama": {
      "base_url": "http://127.0.0.1:11434",
      "models": [
        {
          "context_window_tokens": 32768,
          "model": "hf.co/unsloth/Qwen3.8-27B-GGUF:Q8_0"
        },
        {
          "context_window_tokens": 32768,
          "model": "hf.co/unsloth/Qwen3.8-27B-GGUF:UD-Q6_K"
        }
      ],
      "timeout_seconds": 600
    }
  }
}
```

Your URL and model list will reflect your server. Setup detects the active context size when available; otherwise, it uses 32,768 tokens.

You can switch models at any time with `/models`. Select **ollama**, move to the model list with the arrow keys, and press Enter on the model you want to use. The `●` marks the current model.

![Switch between the installed Q6 and Q8 models with /models.](/blog/inference-metrics-skiller-ollama/metrics-model-selection.svg)

## Task generate 1000 words

Send the agent a task long enough to observe sustained generation:

```text
Write a detailed, approximately 1000-word guide to running a local LLM.
Organize it into five sections of about 200 words each: choosing a model,
understanding quantization, planning memory requirements, configuring context
size, and measuring generation speed. Explain each topic with practical
examples. Do not summarize or skip sections, and write the full guide in a
single response.
```

Once the response is complete, Skiller shows its generation speed at the bottom right. The footer shows the prompt token count and configured context size. Here is the result from our Q6 model:

![The completed response, with its generation speed highlighted in green: 26 t/s.](/blog/inference-metrics-skiller-ollama/metrics-text-result.svg)

The green highlights show three different measurements:

- **26 t/s**: output generation speed. Ollama generated 1,956 tokens in 74.62 seconds, or 26.21 tokens per second, rounded in STUI. This excludes model loading and prompt processing; generated tokens include reasoning when present.
- **698**: prompt tokens reported by Ollama for this request, including the instructions and conversation sent to the model. This is not the length of the generated answer.
- **32.8K**: the configured context budget of 32,768 tokens, displayed in compact form. It is the available budget, not the number of tokens used.

## Tool call cycle metrics

Use three sequential shell calls to observe generation speed across a tool cycle. Each call uses the previous result, followed by a final response.

In `metrics.yaml`, add `tools` to the `respond` step and increase `max_turns` to allow the tool cycles and final response:

```yaml
    tools:
      - shell
    max_turns: 5
```

Add this top-level `tools` field to `metrics.agent.json`, keeping its existing `llm` and `context` fields:

```json
{
  "tools": {
    "shell": {
      "allowed_commands": ["printf"],
      "allowed_paths": ["{{runtime.cwd}}"],
      "allowlist_enabled": true
    }
  }
}
```

Restart with `skiller @metrics` to load the updated definition, then send this prompt:

```text
Perform this calculation using exactly three sequential shell tool calls.
Do not combine commands or issue parallel calls.
1. Run printf '17\n'.
2. In a new tool call, use the returned number and add 25 with shell arithmetic.
3. In another tool call, use that result and multiply it by 2.
Wait for each tool result before making the next call.
Finally, report the three intermediate results and the final answer.
```

The agent ran the commands one at a time and reached **84**. There was one extra attempt: it used `echo` to print the sum, but our configuration only allows `printf`. Skiller rejected that command, and the agent tried again with `printf`, successfully returning **42** before continuing.

![Sequential tool calls, a blocked command, recovery with printf, and the final response.](/blog/inference-metrics-skiller-ollama/metrics-tools-result.svg)

Each `‹ ▪▪▪` marks a model response requesting a tool. Its **27 t/s** measures that generation, not command execution. The final answer has its own generation speed, also rounded to **27 t/s** here. Similar displayed speeds do not mean the responses took the same time: they generated different numbers of tokens.

The highlighted **3.1k** in the footer is the input token count for the final generation. It includes the system prompt and conversation history, including previous messages, tool calls, and their results, not just the latest user task.

The successful calls returned **17 → 42 → 84**. This run demonstrates tool execution and recovery, but does not meet the experiment’s exact three-call requirement.

## Run the experiment from another agent

An agent with shell access can run the same experiment through the Skiller CLI, without opening STUI. Use the configured `@metrics` flow with its shell tool enabled. Save the two prompts above as `task-1.txt` and `task-2.txt` in the working directory.

1. **Create a run.** It stops at the first input prompt. Keep the returned `run_id` for both tasks:

   ```bash
   skiller run @metrics
   ```

2. **Send the text generation task.** Replace `<run_id>` with the returned ID. `--wait` waits until the agent finishes and asks for another task:

   ```bash
   skiller input receive <run_id> --text "$(cat task-1.txt)" --wait
   ```

3. **Read the first result and its metrics:**

   ```bash
   skiller logs <run_id>
   ```

   Find the `AGENT_FINAL_ASSISTANT_MESSAGE` event. Its `payload.generation_metrics` contains `output_tokens` and `output_generation_duration_ns`. Calculate **t/s = output_tokens × 1000000000 / output_generation_duration_ns**. Record the event sequence so you can distinguish this task from the next one.

4. **Send the tool experiment to the same run:**

   ```bash
   skiller input receive <run_id> --text "$(cat task-2.txt)" --wait
   ```

5. **Read the new events** with `skiller logs <run_id>`. For sequences after the first task, inspect `AGENT_ASSISTANT_MESSAGE` for each tool cycle and `AGENT_FINAL_ASSISTANT_MESSAGE` for the final answer. Calculate their speeds using the same formula. Check `AGENT_TOOL_CALL` and `AGENT_TOOL_RESULT` to confirm which commands actually ran and whether any were rejected.

Report the model, each generation’s output tokens and t/s, the actual tool-call count, and the final answer. Missing metrics should be reported as unavailable. `STEP_SUCCESS` repeats the final generation’s metrics; do not count it as another generation.

## Conclusion

Skiller makes Ollama’s generation metrics visible interactively in its TUI and exposes an agent-friendly CLI. You can inspect responses yourself, delegate measurements to an agent, or automate repeatable experiments.

These metrics are not limited to one-shot text generation. The tool experiment also shows the generation speed of each assistant response requesting a tool and of the final answer, making it possible to observe inference throughout a tool-calling cycle.
