# Agent context

This note defines the token markers persisted in agent context entries that have `usage_json`.

## Marker delta tokens

`delta_tokens` is the existing token delta marker for an entry with `usage_json`.

It is calculated from the LLM-reported `prompt_tokens`:

- If there is no previous usage marker, `delta_tokens = prompt_tokens`.
- If the context window moved or was rebased, Skiller estimates the current window tokens and stores the positive difference.
- Otherwise, `delta_tokens = current_prompt_tokens - previous_prompt_tokens`.
- If the result would be negative, it is clamped to `0`.

`delta_tokens` belongs to the current usage marker, but it represents the measured growth since the previous usage marker. It is not the isolated token size of the current entry.

Example:

| sequence | entry | usage_json | prompt_tokens | delta_tokens |
|---:|---|---|---:|---:|
| 1 | user: "hola" | no | null | null |
| 2 | assistant final: "hola" | yes | 100 | 100 |
| 3 | user: "busca README" | no | null | null |
| 4 | assistant tool_calls | yes | 180 | 80 |
| 5 | tool_call: search_files | no | null | null |
| 6 | tool_result: README.md | no | null | null |
| 7 | assistant final | yes | 300 | 120 |
| 8 | user: "ahora package.json" | no | null | null |
| 9 | assistant tool_calls | yes | 390 | 90 |
| 10 | tool_call | no | null | null |
| 11 | tool_result | no | null | null |
| 12 | assistant final | yes | 500 | 110 |

Examples:

- Sequence `2`: `100 - 0 = 100`.
- Sequence `4`: `180 - 100 = 80`.
- Sequence `7`: `300 - 180 = 120`.
- Sequence `9`: `390 - 300 = 90`.
- Sequence `12`: `500 - 390 = 110`.

## Marker delta compact tokens

`delta_compact_tokens` is the estimated token delta for the same marker after removing tool history entries that can later be pruned from the prompt.

Column semantics:

- `NULL`: compact delta is not prepared. This is a legacy or migrated marker state.
- `0`: compact delta was prepared and is zero. This is valid only when `delta_tokens = 0`.
- `> 0`: compact delta was prepared and weighs that many estimated tokens.

New marker rule:

- Build the block from the previous entry with `usage_json` to the current entry with `usage_json`, including both markers.
- Calculate `delta_compact_tokens` only when the block contains prunable entries.
- If the block has no prunable entries, set `delta_compact_tokens = delta_tokens`.

Prunable entries:

- `assistant_message` with `message_type = "tool_calls"`
- `tool_call`
- `tool_result`

Non-prunable entries:

- `user_message`
- `assistant_message` with `message_type = "final"`

Example:

| sequence | entry | usage_json | prompt_tokens | delta_tokens | delta_compact_tokens |
|---:|---|---|---:|---:|---:|
| 1 | user: "hola" | no | null | null | null |
| 2 | assistant final: "hola" | yes | 100 | 100 | 100 |
| 3 | user: "busca README" | no | null | null | null |
| 4 | assistant tool_calls | yes | 180 | 80 | compact estimate |
| 5 | tool_call: search_files | no | null | null | null |
| 6 | tool_result: README.md | no | null | null | null |
| 7 | assistant final | yes | 300 | 120 | compact estimate |
| 8 | user: "ahora package.json" | no | null | null | null |
| 9 | assistant tool_calls | yes | 390 | 90 | compact estimate |
| 10 | tool_call | no | null | null | null |
| 11 | tool_result | no | null | null | null |
| 12 | assistant final | yes | 500 | 110 | compact estimate |

Block examples:

- Sequence `2`: block `[2]`; no prunable entries; `delta_compact_tokens = 100`.
- Sequence `4`: block `[2, 3, 4]`; contains `assistant tool_calls`; estimate compact delta.
- Sequence `7`: block `[4, 5, 6, 7]`; contains `assistant tool_calls`, `tool_call`, and `tool_result`; estimate compact delta.
- Sequence `9`: block `[7, 8, 9]`; contains `assistant tool_calls`; estimate compact delta.
- Sequence `12`: block `[9, 10, 11, 12]`; contains `assistant tool_calls`, `tool_call`, and `tool_result`; estimate compact delta.

Estimation:

- `full_chars`: serialized size of all entries in the block.
- `compact_chars`: serialized size after removing prunable entries.
- `delta_compact_tokens = round(delta_tokens * compact_chars / full_chars)`.

Safety rules:

- If `full_chars == 0`, use `delta_tokens`.
- Clamp the result to `0 <= delta_compact_tokens <= delta_tokens`.
- If no prunable entries exist, use `delta_tokens`.

Legacy backfill:

- Before selecting a compact window, Skiller prepares legacy markers for the context.
- Markers with `delta_compact_tokens IS NULL` are backfilled as `ceil(delta_tokens / 3)`.
- Markers with `delta_tokens > 0` and `delta_compact_tokens = 0` are also rebuilt as `ceil(delta_tokens / 3)` because `0` is not a valid compact weight for a positive delta.
- Markers with `delta_tokens = 0` and `delta_compact_tokens = 0` are left unchanged.
- The legacy backfill does not use payload inspection. It is a transition heuristic for old markers whose compact weight was not prepared when they were written.

`delta_compact_tokens` does not delete persisted context. It only records the estimated delta that a future compact prompt window can use when old tool history is omitted.

## List context window

A normal context window selects the most recent conversation entries that fit in the requested token width.

The window is calculated from usage markers, not from every entry. A usage marker is an entry with `usage_json` and token marker columns. Each marker contributes its `delta_tokens` value to the window estimate.

Algorithm:

1. Read usage markers for the context.
2. Treat negative `delta_tokens` as `0`.
3. Accumulate `delta_tokens` backwards, from the newest marker to older markers.
4. Select the oldest marker whose backward accumulation is still within the requested token window.
5. Find the previous usage marker before that selected marker.
6. Start the returned entries after the previous usage marker, so the selected marker block is not cut in the middle.
7. If no marker fits, keep the latest marker block.
8. Return all entries from the calculated start sequence in original sequence order.

The normal window does not prune entries. If a block is selected, its user messages, assistant messages, tool calls, and tool results are all returned complete.

## Compact session window

A compact session window keeps the recent part of the conversation complete and prunes only older tool history when more context can fit.

The compact window has one policy value: `keep_last_markers`. This value means how many recent usage marker blocks must stay complete. It is normalized to the range `1..100` before the window is calculated.

Algorithm:

1. Prepare legacy compact deltas for the context when needed.
2. Find the recent protected tail using the last `keep_last_markers` usage markers.
3. Count that protected tail with normal `delta_tokens`.
4. If the protected tail already fills or exceeds the requested token window, use the normal window result. No compact pruning is applied.
5. If the protected tail does not fill the requested token window, fill the remaining older portion using prepared `delta_compact_tokens`.
6. In that older compact portion, omit prunable entries and keep non-prunable entries.
7. Return entries in original sequence order.

Protected tail:

- Uses normal `delta_tokens`.
- Keeps all entries complete.
- Does not prune `assistant tool_calls`, `tool_call`, or `tool_result` entries.

Older compact portion:

- Uses prepared `delta_compact_tokens` for accumulation.
- Does not fall back from `delta_compact_tokens = NULL` to `delta_tokens`.
- Omits prunable entries.
- Keeps user messages and assistant final messages.

Usage markers are entries with `usage_json` and token marker columns. The compact window uses usage markers, not only assistant final messages, because token growth is measured from usage marker to usage marker.

A compact session window never modifies persisted context. It only changes which persisted entries are selected for the prompt window.
