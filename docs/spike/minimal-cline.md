# Minimal Cline en Skiller

## Objetivo

Explorar como se veria un agente tipo Cline sobre `Skiller`, sin intentar copiar toda su complejidad.

La idea no es construir un workflow lineal largo, sino un loop simple de:

1. leer contexto
2. pensar
3. actuar
4. verificar
5. pedir confirmacion si hace falta

## Diferencia clave

`Skiller` hoy esta mas cerca de un workflow engine duradero.

- tiene steps
- tiene estado persistido
- puede esperar y reanudarse
- puede usar tools por `mcp`

Un sistema tipo Cline necesita ademas una dinamica mas iterativa:

- leer archivos
- ejecutar comandos
- observar resultados
- decidir el siguiente paso
- repetir

## Minimo conjunto de steps

Un "minimal cline" sobre `Skiller` podria arrancar con estos steps:

1. `llm_prompt`
- genera plan
- interpreta errores
- decide siguiente accion

2. `read`
- lee archivos
- busca texto
- inspecciona contexto del repo

3. `command`
- ejecuta shell
- captura salida

4. `write`
- crea o modifica archivos

5. `if`
- decide si seguir, corregir, parar o pedir ayuda

6. `assign`
- guarda variables limpias en contexto

7. `conversation_wait`
- pausa para pedir aprobacion o nueva instruccion humana

## Flujo ejemplo

Caso: "Arregla un test roto".

1. `read`
- abre el test y el codigo relacionado

2. `llm_prompt`
- propone hipotesis del fallo

3. `command`
- ejecuta `pytest`

4. `llm_prompt`
- interpreta el error

5. `write`
- corrige el archivo

6. `command`
- vuelve a ejecutar tests

7. `if`
- si pasa, seguir
- si falla, volver a leer/pensar

8. `conversation_wait`
- pide aprobacion para ejecutar mas tests o hacer commit

## Por que Skiller encaja

`Skiller` ya tiene varias piezas utiles:

- `skill_snapshot`
- contexto persistido
- `mcp`
- `wait_webhook`
- `resume`

Eso lo hace una buena base para agentes que:

- no viven en una sola ejecucion
- pueden esperar eventos externos
- pueden retomar trabajo despues

## Limite actual

Hoy `Skiller` todavia no es un runtime agentic completo.

Le faltan, al menos:

- steps de lectura y escritura explicitos
- un step LLM canonico
- branching mas rico
- espera conversacional

## Conclusión

Un "minimal cline" en `Skiller` no seria un chatbot generico.

Seria un agente iterativo y duradero para tareas de coding, montado sobre:

- tools
- estado persistido
- decisiones explicitas
- pausas y reanudacion

La base del runtime ya existe. Lo que falta es el set minimo de steps para convertir workflows lineales en un loop agente simple.
