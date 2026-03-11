# Spike: `if` y control de flujo en Skiller

## Objetivo

Poner por escrito el contexto real del problema de diseno que aparece al introducir `if` en `Skiller`.

La idea de este spike no es cerrar la solucion, sino dejar claro:

- cual es el modelo actual del runtime
- por que `if` no es "solo otro step"
- que aproximaciones se han explorado hasta ahora
- que preguntas de diseno siguen abiertas

## Contexto actual

Hoy `Skiller` ejecuta una skill como una lista lineal de `steps`.

El modelo operativo actual es este:

1. el run guarda `current` como `step_id`
2. `RenderCurrentStepUseCase` obtiene el step actual desde el puntero persistido del run
3. el runtime despacha a un use case segun `step.type`
4. cada use case actualiza el run con `next` explicito o termina el flujo

Esto funciona bien para steps lineales como:

- `notify`
- `assign`
- `llm_prompt`
- `mcp`
- `wait_webhook`

Incluso cuando el step tiene semantica especial, como `wait_webhook`, el modelo sigue siendo:

- ejecutar step actual
- persistir resultado o estado
- decidir siguiente posicion del run

## Problema de diseno

El problema no es evaluar una condicion.

El problema real es este:

> `Skiller` hoy asume un flujo lineal basado en indice.  
> Un step `if` necesita branching real.  
> Eso obliga a decidir como se modela el control de flujo no lineal en el runtime.

En otras palabras:

- con `notify` o `assign`, "siguiente step = indice + 1" sigue teniendo sentido
- con `if`, eso deja de ser suficiente

## Donde aparece la rotura

Ejemplo intuitivo:

```yaml
steps:
  - id: decide
    type: if
    left: "{{results.prepare.action}}"
    op: eq
    right: retry
    then: retry_notice
    else: human_notice

  - id: retry_notice
    type: notify
    message: "retry"

  - id: human_notice
    type: notify
    message: "ask human"
```

Si `if` salta a `retry_notice`, el problema es que `notify` hoy avanza por defecto al siguiente indice secuencial.

Eso significa que, despues de ejecutar `retry_notice`, el runtime caeria en `human_notice`.

Ese comportamiento no representa branching real.

## Verificacion del patron actual

En el runtime actual:

- el loop no decide a que step va cada tipo concreto
- el loop solo despacha por `step.type`
- el use case de cada step es el que actualiza el run

Eso ya pasa hoy con:

- `notify`
- `assign`
- `llm_prompt`
- `wait_webhook`

Por tanto, si existiera `if`, lo razonable seria mantener el mismo patron:

- el loop despacha
- `ExecuteIfStepUseCase` evalua y decide el siguiente paso

Pero esto no resuelve por si solo el problema del branching, porque el resto de steps sigue teniendo avance secuencial por defecto.

## Aproximaciones exploradas

### 1. `if` como comparador binario simple con `then` y `else`

Idea:

```yaml
- id: decide
  type: if
  left: "{{results.prepare.action}}"
  op: eq
  right: retry
  then: retry_notice
  else: human_notice
```

Ventajas:

- contrato pequeno
- sin lenguaje de expresiones
- facil de validar
- facil de testear

Problema:

- por si sola no cierra el control de flujo
- despues de saltar a una rama, los steps siguen avanzando secuencialmente
- eso puede hacer que una rama caiga en la otra

Estado de esta opcion:

- sirve como punto de partida conceptual
- no es suficiente como solucion completa

### 2. `if` con `then` y sin `else`

Idea:

- si la condicion es verdadera, saltar a `then`
- si es falsa, continuar al siguiente step fisico

Problemas:

- la rama falsa queda implicita
- la semantica depende demasiado del orden del YAML
- hace mas dificil leer la skill
- no cierra bien el contrato

Concluson:

- no parece una buena base para v0

### 3. `if` + `next` opcional en los steps

Idea:

- `if` decide entre `then` y `else`
- los steps normales pueden declarar un `next` explicito
- si `next` existe, se usa
- si no existe, se cae al siguiente indice secuencial

Ejemplo:

```yaml
- id: decide
  type: if
  left: "{{results.prepare.action}}"
  op: eq
  right: retry
  then: retry_notice
  else: human_notice

- id: retry_notice
  type: notify
  message: "retry"
  next: done

- id: human_notice
  type: notify
  message: "ask human"
  next: done

- id: done
  type: notify
  message: "finished"
```

Ventajas:

- resuelve la caida accidental entre ramas
- introduce transiciones explicitas sin romper del todo el modelo actual
- puede mantenerse compatibilidad con las skills existentes

Coste:

- `if` deja de ser el unico cambio; aparece una nocion general de transicion
- el runtime pasa a ser hibrido: indice secuencial por defecto + saltos explicitos opcionales

Estado de esta opcion:

- es la aproximacion pragmatica mas razonable explorada hasta ahora
- pero ya no es "solo implementar `if`"

### 4. "Cada step define su transicion"

Idea:

- pasar de workflow lineal a modelo mas cercano a maquina de estados o grafo
- cada step define a que `step_id` va despues
- el orden fisico de la lista deja de ser la semantica principal

Ejemplo:

```yaml
- id: analyze_issue
  type: llm_prompt
  ...
  next: prepare

- id: prepare
  type: assign
  ...
  next: decide

- id: decide
  type: if
  left: "{{results.prepare.action}}"
  op: eq
  right: retry
  then: retry_notice
  else: human_notice
```

Ventajas:

- branching real
- loops reales
- reconvergencia explicita
- mejor base para un runtime mas agentic

Coste:

- ya no es una extension menor
- obliga a revisar el contrato de `current`
- el runtime deja de apoyarse principalmente en el orden fisico
- hay que decidir compatibilidad con skills actuales

Estado de esta opcion:

- conceptualmente es la mas limpia
- operativamente es mas invasiva

### 5. `if / then / else / endif` como bloques estructurados

Idea:

- modelar `if` como estructura compuesta, no como step con saltos
- la rama `then` y la rama `else` serian bloques internos
- al terminar una rama, ambas convergen de forma implicita en el punto siguiente

Ventajas:

- es muy legible
- evita el problema de caer en la otra rama
- se parece a estructuras de control clasicas

Coste:

- el YAML deja de ser una lista plana de steps
- el runtime tendria que soportar estructura anidada
- `RenderCurrentStepUseCase`, persistencia, reanudacion y logs se complican mucho mas

Estado de esta opcion:

- valida a nivel conceptual
- probablemente demasiado invasiva para el estado actual de `Skiller`

## Analogias utiles exploradas

### Estilo `goto`

Una parte de la discusion llevo a una analogia tipo ensamblador o C clasico:

- `id` del step como label
- `next` como salto explicito
- `if` como salto condicional

Esta analogia ayuda a ver algo importante:

> sin una nocion de salto explicito, el branching real es muy dificil de modelar sobre una lista lineal

### Maquina de estados

Tambien se exploro la idea de que `if` en una maquina de estados si tiene sentido, pero no como "bloque imperativo".

Seria mas bien:

- un estado de decision
- con varias transiciones salientes

Eso apunta a un modelo mas cercano a:

- choice state
- exclusive gateway
- transition with guard

## Formulacion actual del problema

La formulacion mas util hasta ahora es esta:

> `if` no es simplemente un nuevo step.  
> Es el primer caso que obliga a definir si `Skiller` seguira siendo un runtime de flujo lineal con pequenas excepciones, o si evolucionara hacia un modelo de transiciones explicitas entre steps.

## Preguntas abiertas

1. `Skiller` debe seguir usando el orden fisico de `steps` como semantica principal?
2. `current` debe seguir apuntando a un `step_id` o conviene introducir otro puntero adicional?
3. Tiene sentido introducir `next` como transicion explicita general antes de implementar `if`?
4. `if` debe ser un step simple con saltos o una estructura de control mas rica?
5. Queremos compatibilidad gradual con las skills actuales o aceptamos un cambio mayor del contrato?
6. Queremos permitir loops de forma intencional en el runtime?

## Lectura provisional

Con lo explorado hasta ahora:

- `if` aislado sobre el modelo lineal actual parece insuficiente
- `if + next` parece el camino mas pragmatico
- "cada step define su transicion" parece el modelo mas limpio a medio plazo
- `if / then / else / endif` parece mas costoso de lo que conviene ahora

## TODO

Antes de decidir una direccion final, hace falta estudiar mas a fondo:

- como resuelven branching y transiciones aplicaciones similares
  - por ejemplo: AWS Step Functions, BPMN/Camunda, XState, Temporal, Argo Workflows u otras referencias comparables
- que conclusiones practicas se pueden extraer de esas referencias para `Skiller`
- que partes de esos modelos son compatibles con el runtime actual y cuales no
- referencias de workflow engines y state machines
- patrones de branching con menor impacto sobre un runtime lineal
- alternativas que introduzcan control de flujo explicito sin rehacer de golpe el diseno de `Skiller`
- posibles soluciones intermedias que reduzcan el coste de migracion y mantengan compatibilidad con skills actuales
