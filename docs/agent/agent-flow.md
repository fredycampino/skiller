# Agent Flow

This document shows the current flow of `AgentRunner.execute(...)`.

## Status

Current implementation flow.

## Flow Diagram

```mermaid
%%{init: {"theme": "dark", "themeVariables": {"fontSize": "22px", "background": "#111827", "mainBkg": "#1f2937", "secondaryBkg": "#111827", "tertiaryBkg": "#111827", "primaryColor": "#1f2937", "primaryTextColor": "#f9fafb", "primaryBorderColor": "#64748b", "lineColor": "#94a3b8", "clusterBkg": "#111827", "clusterBorder": "#475569"}}}%%
flowchart TB
    start([Start]) --> setup

    subgraph setup_block[Setup]
        setup[Read config and context]
        tools[Resolve enabled tools]
        seed[Append incoming task]
        init[Init counters]
        setup --> tools --> seed --> init
    end

    init --> loop_check

    subgraph loop_block[Turn Loop]
        loop_check{turn_count < max_turns?}
        build[Build prompt]
        llm_call[Call LLM]
        ok{response.ok?}
        loop_check -- yes --> build --> llm_call --> ok
    end

    loop_check -- no --> fail_max[Fail: max_turns reached]
    ok -- no --> fail_llm[Fail: provider error]

    ok -- yes --> tools_enabled{Tools enabled?}
    tools_enabled -- no --> final_path
    tools_enabled -- yes --> tool_calls_check

    subgraph final_block[Final Answer Path]
        final_path[Extract final text]
        empty{Final text empty?}
        save_final[Append assistant final message]
        finish([Return result])
        final_path --> empty
        empty -- no --> save_final --> finish
    end

    empty -- yes --> fail_empty[Fail: no final answer]

    subgraph tool_turn_block[Tool Turn Executor]
        tool_calls_check{response.tool_calls present?}
        keep_content{response content?}
        save_content[Append assistant content]
        iterate[For each tool_call in order]
        parse[Parse arguments_json]
        valid{Arguments valid?}
        feedback[Append invalid feedback user_message]
        append_call[Append tool_call with tool_call_id]
        emit_call[Emit AGENT_TOOL_CALL]
        execute_tool[Execute tool via ToolManager]
        append_result[Append tool_result with tool_call_id]
        emit_result[Emit AGENT_TOOL_RESULT]
        more{More tool_calls?}
        advance[turn_count += 1]

        tool_calls_check -- no --> final_path
        tool_calls_check -- yes --> keep_content
        keep_content -- yes --> save_content --> iterate
        keep_content -- no --> iterate
        iterate --> parse --> valid
        valid -- no --> feedback --> more
        valid -- yes --> append_call --> emit_call --> execute_tool --> append_result --> emit_result --> more
        more -- yes --> iterate
        more -- no --> advance
    end

    advance --> loop_check
```

## Notes

- The loop supports more than one native `tool_call` per response.
- One assistant response advances the turn counter once, after all tool calls are processed.
- Invalid tool calls append feedback and do not cancel other valid tool calls in the same response.
- Every executed tool call is correlated with `tool_call_id` in context and runtime events.
- Streaming is out of scope for the current `LLMPort` contract.

## Related Docs

- [`./agent-loop.md`](./agent-loop.md)
- [`./agent-event.md`](./agent-event.md)
- [`./agent-context.md`](./agent-context.md)
- [`../runtime/agent-architecture.md`](../runtime/agent-architecture.md)
