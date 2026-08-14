# Agent context: algoritmo de poda

La poda solo cambia qué entradas se envían en la siguiente petición al LLM.
Las filas de `agent_context_entries` son append-only y nunca se eliminan. El
algoritmo tiene dos fases independientes:

1. publicar marcadores al añadir mensajes del asistente;
2. seleccionar los bloques visibles cuando la ventana alcanza el umbral.

## 1. Publicación de marcadores

Las entradas se publican en orden de `sequence`:

- `user_message`;
- `assistant_message/tool_calls`;
- `tool_call`;
- `tool_result`;
- `assistant_message/final`.

Cada entrada `assistant_message` calcula y persiste `delta_tokens`. Se usa la
diferencia de `prompt_tokens` cuando es posible; si no, se estima con el
payload persistido. Solo una entrada con `usage.prompt_tokens` válido recibe
`compaction_id` y participa como marcador de uso. Una entrada sin usage sigue
teniendo `delta_tokens`, pero `compaction_id = NULL` y no cierra un bloque de
uso.

### Estado utilizado

Antes de publicar, el calculador lee `agent_context_state`:

```python
AgentContextState(
    context_id=...,
    start_sequence=...,
    compacted_sequence=...,
    compaction_id=...,
)
```

`compaction_id` identifica la generación actual. Empieza en `0` y solo aumenta
cuando la fase de compactación persiste un nuevo estado. Publicar un marcador
no actualiza el estado.

### Cálculo de `delta_tokens`

Se lee el último marcador que tenga `prompt_tokens` y `compaction_id`.

Si el marcador anterior pertenece a la generación actual y el nuevo valor de
`prompt_tokens` no disminuye:

```text
delta_tokens = current_prompt_tokens - previous_prompt_tokens
```

En cualquier otro caso se estima el primer delta de la generación usando el
bloque persistido desde `start_sequence` (o desde el marcador anterior) más el
payload que se está publicando:

```text
block_chars = persisted_payload_chars + current_payload_chars
delta_tokens = max(1, round(block_chars / 3))
```

La estimación se usa para el primer marcador, después de una compactación,
cuando no hay `usage.prompt_tokens`, o cuando el proveedor devuelve un prompt
menor. El `delta_tokens` estimado siempre se guarda. Solo cuando
`prompt_tokens` es válido se guarda también el `compaction_id` leído del
estado.

Después de guardar el marcador se calculan los `delta_compact_tokens` de su
bloque. El bloque va desde la entrada posterior al marcador anterior hasta el
marcador actual, ambos inclusive. El peso se reparte según los caracteres del
payload y solo se guarda en entradas no podables.

## 2. Prunables y poda

### Entradas podables

Son podables dentro del rango compactado:

- `tool_call`;
- `tool_result`;
- `assistant_message/tool_calls`.

No son podables:

- `user_message`;
- `assistant_message/final`.

Podable significa que se omite al reconstruir la parte compactada; la fila
original y la versión completa permanecen disponibles en la parte raw.

### Estado de la ventana

```python
AgentContextState(
    context_id: str,
    start_sequence: int,
    compacted_sequence: int | None,
    compaction_id: int,
)
```

- `start_sequence`: primera secuencia de la ventana lógica actual.
- `compacted_sequence`: última secuencia incluida en el rango compactado; es
  `None` antes de la primera compactación.
- `compaction_id`: generación de los marcadores publicados desde la última
  compactación.

Estado inicial:

```text
start_sequence = 1
compacted_sequence = null
compaction_id = 0
```

La ventana se reconstruye así:

```text
compactada: start_sequence .. compacted_sequence
raw:       compacted_sequence + 1 .. última secuencia
```

El rango raw conserva todas sus entradas, incluidas las podables. El rango
compactado excluye las podables y usa `delta_compact_tokens`.

### Activación y selección

Antes de cada petición se suman los pesos de la ventana actual:

```text
effective_tokens = min(configured_window_tokens, model_context_window_tokens)
trigger_tokens = floor(effective_tokens * compaction_trigger_ratio)
target_tokens = floor(effective_tokens * compaction_target_ratio)
```

Si `estimated_tokens < trigger_tokens`, no cambia nada. Si
`estimated_tokens >= trigger_tokens`:

1. se mantiene raw el bloque abierto;
2. se recorren hacia atrás los bloques completos más recientes;
3. se conservan hasta `keep_last_blocks` bloques raw, respetando `target_tokens`;
4. el bloque completo más reciente se conserva aunque supere el objetivo;
5. la capacidad restante se usa para un prefijo compacto de bloques antiguos,
   usando `delta_compact_tokens`;
6. se persiste atómicamente el nuevo `start_sequence`,
   `compacted_sequence` y `compaction_id + 1`;
7. se vuelve a leer la ventana con los nuevos límites.

La selección siempre respeta límites de bloque. Si ningún bloque antiguo cabe,
el rango compactado queda vacío y `start_sequence` avanza hasta el comienzo del
tail raw. La poda no corta un bloque por la mitad.

### Ejemplo de bloques

```text
sequence  entrada                         bloque
--------  -------------------------------  ----------------
1         user_message                    1: 1..2
2         assistant_message/final         1: 1..2 (marcador)
3         user_message                    2: 3..4
4         assistant_message/tool_calls    2: 3..4 (marcador)
5         tool_call                       3: 5..7
6         tool_result                     3: 5..7
7         assistant_message/final         3: 5..7 (marcador)
```

El bloque abierto que exista después del último marcador permanece raw hasta
que se publique su marcador.

## Invariantes

- Las entradas y sus marcadores son append-only.
- `compaction_id` solo cambia al persistir una compactación.
- Publicar consume el `compaction_id` vigente, pero no modifica el estado.
- Los marcadores de una misma generación pueden usar deltas de
  `prompt_tokens`.
- El primer marcador de una generación usa estimación si no puede calcular un
  delta de prompt válido.
- La poda nunca elimina filas ni divide bloques.
- Un fallo al guardar el estado no deja una ventana nueva publicada.
