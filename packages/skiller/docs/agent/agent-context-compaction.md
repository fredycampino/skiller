# Agent Context Compaction Specification

## Status and configuration


### Window state

Window pointers are persisted in a state object separate from context entries:

- `start_sequence`: first sequence in the current logical window.
- `compacted_sequence`: last compacted sequence, inclusive. It is `null` before the first
  compaction.

If `start_sequence = compacted_sequence + 1`, the compacted range is empty and the queue contains
only raw entries.

### Configuration

- `window_tokens`: token capacity assigned to the message queue.
- `keep_last_blocks`: maximum number of newest complete blocks to keep raw when they fit.
- `compaction_trigger_ratio = 0.8`: window ratio that triggers compaction.
- `compaction_target_ratio = 0.5`: window ratio that compaction must target.

Derived limits:

```text
compaction_trigger_tokens = floor(window_tokens * compaction_trigger_ratio)
compaction_target_tokens = floor(window_tokens * compaction_target_ratio)
```

Required relation:

```text
0 < compaction_target_ratio < compaction_trigger_ratio <= 1
```

## Block definition

A block contains the sequences after the previous usage marker through the current usage marker,
inclusive.

```text
seq 2  assistant final       usage.prompt_tokens: yes
seq 3  user_message          usage.prompt_tokens: no
seq 4  assistant tool_calls  usage.prompt_tokens: yes

previous_marker = seq 2
current_marker  = seq 4

selected block: {seq 3, seq 4}
weight: delta_tokens from seq 4
```

The first block starts at the first context sequence. Sequences after the current marker form the
open raw block.

```text
delta_compact_tokens = round(delta_tokens * entry_chars / block_chars)
```

The formula applies only to non-prunable entries. Prunable entries keep null.

### Shared result

Both queries reuse the existing result model:

```python
@dataclass(frozen=True)
class AgentContextWindowEntries:
    entries: list[AgentContextEntry]
    estimated_tokens: int
```

`entries` contains the selected entries in sequence order. `estimated_tokens` is their persisted
weight: `delta_tokens` from usage markers for raw entries and `delta_compact_tokens` for compacted
entries.

### Shared window query

```python
@dataclass(frozen=True)
class AgentContextWindowQuery:
    context_id: str
    start_sequence: int
    compacted_sequence: int | None
```

## Get Raw Entries

```python
def list_raw_entries(
    self,
    *,
    query: AgentContextWindowQuery,
) -> AgentContextWindowEntries: ...
```

Responsibility: resolve the raw start from the window query, retrieve every entry from that sequence
without pruning, and calculate its weight from `delta_tokens` on entries with
`usage.prompt_tokens`.

It starts at `start_sequence` when `compacted_sequence` is null; otherwise it starts after
`compacted_sequence`. It does not apply compaction limits or persist window state.

## Get Compacted Entries

```python
def list_compact_entries(
    self,
    *,
    query: AgentContextWindowQuery,
) -> AgentContextWindowEntries: ...
```

Responsibility: retrieve the visible entries where
`start_sequence <= sequence <= compacted_sequence`, exclude prunable entries, and calculate their
weight from `delta_compact_tokens`.

It returns no entries when `compacted_sequence` is null or before `start_sequence`. It does not
apply compaction limits, recover raw entries, or persist window state.

## Compaction algorithm

```text
1. Retrieve window_state.

2. Retrieve the current queue:

   query = AgentContextWindowQuery(
       context_id,
       start_sequence,
       compacted_sequence,
   )

   compacted = list_compact_entries(query)
   raw = list_raw_entries(query)

   entries = compacted.entries + raw.entries
   tokens = compacted.estimated_tokens + raw.estimated_tokens

3. If tokens < compaction_trigger_tokens:
   return entries

4. If tokens >= compaction_trigger_tokens:
   calculate the new start_sequence and compacted_sequence as defined in
   Calculate Compaction State.

5. Persist the new window_state atomically.

6. Retrieve compacted and raw again with the new boundaries.

7. Return the new queue.
```

## Calculate Compaction State

This operation calculates the new boundaries after compaction is triggered. It does not persist
window state or retrieve the final queue.

```python
@dataclass(frozen=True)
class AgentContextCompactionQuery:
    context_id: str
    start_sequence: int
    compacted_sequence: int | None
    compaction_id: int
    keep_last_blocks: int
    target_tokens: int


def select_compaction_state(
    self,
    *,
    query: AgentContextCompactionQuery,
) -> AgentContextState: ...
```

The selection is calculated efficiently in storage and follows these rules:

1. The open block remains raw.
2. Keep up to `keep_last_blocks` newest complete raw blocks when they fit within `target_tokens`.
3. If all protected raw blocks do not fit, keep only the newest complete blocks that fit.
4. Always keep the newest complete raw block, even when it alone exceeds `target_tokens`.
5. If the selected raw part occupies the target, return an empty compacted range:
   `compacted_sequence = start_sequence - 1`.
6. Otherwise, use the remaining capacity for compacted entries and move `start_sequence` by
   complete blocks until the complete queue fits within `target_tokens`.
7. Entries without persisted token weight add zero.

## Behavior cases

Defined:

1. Before the first compaction, compacted_sequence is null and the complete queue is raw. This also
   applies when there are fewer complete blocks than keep_last_blocks, provided tokens remain below
   compaction_trigger_tokens.
2. Below the trigger, the queue and window state remain unchanged.
3. Equality with the trigger starts compaction.
4. The open block remains raw. The algorithm keeps up to keep_last_blocks newest complete blocks
   raw when they fit.
5. Compaction always continues to the target after it is triggered.
6. Window movement uses complete blocks.
7. Entries without persisted token weight add zero to the compaction decision. Their real size is
   not estimated.
8. Repeated compactions advance from the current window state.
9. The new window_state is persisted atomically, outside context entries.
10. Context entries remain stored; compaction only changes prompt visibility.
11. `compaction_id` starts at `0` and increments when a new compaction state is
    persisted. Usage markers store the generation they belong to.
12. Publishing a usage marker reads the current `compaction_id` but does not
    update the compaction state.
14. If protected raw exceeds compaction_target_tokens, keep the newest complete protected blocks
    that fit and return no compacted entries. If the newest block does not fit, keep it complete.
15. Derived token limits are rounded down with floor.
16. A usage entry belongs to its measured block and its delta_tokens is distributed among the
    block's non-prunable entries as delta_compact_tokens.
17. An LLM request failure does not change or roll back window_state. A retry recovers the same
    queue.
18. If persisting window_state fails, the previous state remains unchanged, no LLM request is
    sent, and the operation fails. A retry recalculates from the previous state.
