# Agent context

This note defines the token markers persisted in agent context entries that have `usage_json`.

## Marker delta tokens

`delta_tokens` is the existing token delta marker for an entry with `usage_json`.

It is calculated from LLM-reported `prompt_tokens` only when consecutive markers are comparable; otherwise Skiller estimates the persisted-context block from payload size:

- If there is no previous usage marker, Skiller estimates the current block delta from payload
  character counts. Provider `prompt_tokens` include prompt parts outside persisted context, such as
  system messages and tool schema, so they are not used as the block delta.
- If the context window moved or was rebased, Skiller estimates the current block delta from
  payload character counts. See [Moved window delta estimation](#moved-window-delta-estimation).
- If `current_prompt_tokens < previous_prompt_tokens`, Skiller estimates the current block delta
  because the provider values are not comparable as a monotonic series.
- Otherwise, `delta_tokens = current_prompt_tokens - previous_prompt_tokens`.

`delta_tokens` belongs to the current usage marker, but it represents the measured growth since the previous usage marker. It is not the isolated token size of the current entry.

Example:

| sequence | entry | usage_json | prompt_tokens | delta_tokens |
|---:|---|---|---:|---:|
| 1 | user: "hola" | no | null | null |
| 2 | assistant final: "hola" | yes | 130 | 100 |
| 3 | user: "busca README" | no | null | null |
| 4 | assistant tool_calls | yes | 210 | 80 |
| 5 | tool_call: search_files | no | null | null |
| 6 | tool_result: README.md | no | null | null |
| 7 | assistant final | yes | 330 | 120 |
| 8 | user: "ahora package.json" | no | null | null |
| 9 | assistant tool_calls | yes | 420 | 90 |
| 10 | tool_call | no | null | null |
| 11 | tool_result | no | null | null |
| 12 | assistant final | yes | 530 | 110 |

Examples:

- Sequence `2`: first marker; `delta_tokens` is estimated from the persisted block `1..2`.
- Sequence `4`: `210 - 130 = 80`.
- Sequence `7`: `330 - 210 = 120`.
- Sequence `9`: `420 - 330 = 90`.
- Sequence `12`: `530 - 420 = 110`.

### Moved window delta estimation

When the context window moved or was rebased, Skiller cannot calculate the delta from two
comparable `prompt_tokens` values.

In that case, Skiller estimates the current delta from payload character counts:

- Start at `max(window_start_sequence, previous_usage_marker.sequence + 1)`.
- Sum persisted payload chars from that start sequence.
- Add the current response payload chars.
- Convert chars to an estimated token delta.


## Protected list context

A protected list context is the recent tail that must stay complete before compact pruning is
allowed.

A block is the sequence range after the previous usage marker and up to the current usage marker.
The current usage marker's `delta_tokens` is the token weight of that whole block.

Example:

| block marker | block sequences | block tokens |
|---:|---|---:|
| `2` | `1, 2` | `delta_tokens(2)` |
| `4` | `3, 4` | `delta_tokens(4)` |
| `7` | `5, 6, 7` | `delta_tokens(7)` |
| `9` | `8, 9` | `delta_tokens(9)` |
| `12` | `10, 11, 12` | `delta_tokens(12)` |

Protected tail rule:

1. Read usage markers from newest to oldest.
2. Add complete blocks while both conditions hold:
   the tail has at most `keep_last_blocks` and the accumulated `delta_tokens` stay
   within `window_width_tokens`.
3. Stop before adding a block that would exceed either limit.
4. If the latest block alone exceeds `window_width_tokens`, keep that latest block anyway.
5. If there are fewer than `keep_last_blocks` and they fit, keep all available blocks.
6. The protected tail starts after the usage marker before the oldest protected block.
7. The protected tail keeps every entry in those blocks, including prunable entries.

The compact portion can only be selected before the protected tail start sequence. This keeps the
compact list and protected list aligned on block boundaries.


## Marker delta compact tokens

`delta_compact_tokens(sequence)` is the estimated token weight of that sequence in compact mode.
When present, it also marks the sequence as non-prunable for compact-window accumulation.

Usage marker rule:

- For each usage marker, use the same delta block represented by `delta_tokens`: entries after
  the previous usage marker up to and including the current usage marker.
- Calculate `full_chars` as the serialized size of all entries in that delta block.
- Estimate each entry weight with:
  `entry_tokens = round(delta_tokens(marker) * entry_chars / full_chars)`.
- Store `delta_compact_tokens = entry_tokens` only on non-prunable entries.
- Prunable entries do not contribute compact weight.

Prunable entries:

- `assistant_message` with `message_type = "tool_calls"`
- `tool_call`
- `tool_result`

Non-prunable entries:

- `user_message`
- `assistant_message` with `message_type = "final"`

Example:

| sequence | entry | usage_json | prompt_tokens | delta_tokens | delta_compact_tokens | prunable |
|---:|---|---|---:|---:|---:|---|
| 1 | user: "hola" | no | null | null | entry estimate | no |
| 2 | assistant final: "hola" | yes | 100 | 100 | entry estimate | no |
| 3 | user: "busca README" | no | null | null | entry estimate | no |
| 4 | assistant tool_calls | yes | 180 | 80 | null | yes |
| 5 | tool_call: search_files | no | null | null | null | yes |
| 6 | tool_result: README.md | no | null | null | null | yes |
| 7 | assistant final | yes | 300 | 120 | entry estimate | no |
| 8 | user: "ahora package.json" | no | null | null | entry estimate | no |
| 9 | assistant tool_calls | yes | 390 | 90 | null | yes |
| 10 | tool_call | no | null | null | null | yes |
| 11 | tool_result | no | null | null | null | yes |
| 12 | user: "incluye scripts" | no | null | null | entry estimate | no |
| 13 | assistant final | yes | 500 | 110 | entry estimate | no |

Compact delta examples:

- Marker `2`: estimate and store compact weights for sequences `1` and `2`.
- Marker `4`: estimate compact weight for sequence `3`; sequence `4` is prunable.
- Marker `7`: estimate compact weight for sequence `7`; sequences `5` and `6` are prunable.
- Marker `9`: estimate compact weight for sequence `8`; sequence `9` is prunable.
- Marker `13`: estimate compact weights for sequences `12` and `13`; sequences `10` and `11`
  are prunable.

Estimation:

- `full_chars`: serialized size of all entries in the delta block.
- `entry_chars`: serialized size of one non-prunable entry in the delta block.
- `delta_compact_tokens(entry) = round(delta_tokens(marker) * entry_chars / full_chars)`.

Safety rules:

- If `full_chars == 0`, no entry weight can be estimated from chars.
- Clamp each entry estimate to `0 <= delta_compact_tokens(entry) <= delta_tokens(marker)`.
- The sum of compact entry weights for one delta block must not exceed `delta_tokens(marker)`.

`delta_compact_tokens` does not delete persisted context. It records per-sequence compact weights
that a future compact prompt window can use when old tool history is omitted.

Old persisted entries without `delta_compact_tokens` are not backfilled during compact-window
selection. They do not participate in the compact list, but they can still appear in the protected
tail or in a normal context window.

## Compact list context

A compact list context selects an older compact range before the protected tail.

Inputs:

- `start_sequence`: highest sequence that compact selection may inspect.
- `window_width_tokens`: compact token budget.

Rules:

1. Walk backwards from `start_sequence`.
2. Only entries with `delta_compact_tokens IS NOT NULL` participate in token accumulation.
3. Entries with `delta_compact_tokens = NULL` do not add tokens and do not define range boundaries.
4. Accumulate `delta_compact_tokens` from newest to oldest.
5. If the first compact marker found already exceeds `window_width_tokens`, the compact list is empty.
6. Otherwise, include compact markers while the accumulated sum stays `<= window_width_tokens`.
7. The selected compact range starts at the oldest included compact marker.
8. The selected compact range ends at the newest included compact marker.
9. Return persisted entries inside that selected range in original sequence order.
10. Omit prunable entries from the returned compact list.
11. If there are no compact markers at or before `start_sequence`, the compact list is empty.

The compact list never extends past the newest included compact marker. This prevents a non-compact
entry between the newest compact marker and `start_sequence` from being included without a compact
weight.

Example:

`start_sequence = 9`, `window_width_tokens = 120`.

| sequence | delta_compact_tokens | accumulated | selected |
|---:|---:|---:|---|
| `9` | null | - | no |
| `8` | 30 | 30 | yes |
| `7` | 40 | 70 | yes |
| `6` | null | - | no |
| `5` | null | - | no |
| `4` | null | - | no |
| `3` | 35 | 105 | yes |
| `2` | 50 | 155 | no |

Selected compact range: `3..8`.

Returned compact entries: non-prunable entries inside `3..8`.


## List context window

A normal context window selects the most recent complete blocks that fit in the requested token
width.

The window is calculated from usage markers, not from every entry. Each usage marker contributes
its `delta_tokens` value to the window estimate.

Algorithm:

1. Read usage markers for the context.
2. Treat negative `delta_tokens` as `0`.
3. Accumulate `delta_tokens` backwards, from newest to oldest.
4. Select the oldest marker whose backward accumulation is still within `window_width_tokens`.
5. Start after the previous usage marker so the selected block is not cut in the middle.
6. Return entries from that start sequence in original sequence order.

The normal window never prunes entries.

## Compact session window

A compact session window composes two lists:

- `Protected list context`: recent complete blocks that must stay unpruned.
- `Compact list context`: older non-prunable entries selected with `delta_compact_tokens`.

Algorithm:

1. Normalize configured `keep_last` to `1..100`; internally it is handled as
   `keep_last_blocks`.
2. Build the protected list.
3. If the protected list already reaches `window_width_tokens`, return it.
4. Otherwise, use the remaining token budget to build the compact list before the protected list.
5. Return `compact_entries + protected_entries` in sequence order.

A compact session window never modifies persisted context. It only changes which persisted entries
are selected for the prompt window.
