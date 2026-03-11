# Skiller Webhooks: Vista Funcional

## Objetivo

Describir de forma funcional como debe operar `Skiller` para soportar el step `wait_webhook`.

Este documento explica comportamiento del sistema.
No detalla implementacion interna fina ni contratos de bajo nivel.

## 1. Que problema resuelve

Una skill puede necesitar detenerse hasta que ocurra un evento externo.

Ejemplos:

- un merge en GitHub
- una confirmacion de pago
- una aprobacion externa
- un callback de otro sistema

Para eso existe el step `wait_webhook`.

## 2. Flujo funcional esperado

El flujo completo debe ser este:

1. un run arranca y ejecuta steps normalmente
2. el run alcanza un step `wait_webhook`
3. el run queda en `WAITING`
4. se persiste una espera en `waits`
5. mas tarde entra un webhook externo
6. el proceso de `webhooks` lo recibe y lo persiste
7. el sistema determina si ese webhook satisface una espera activa
8. si hay coincidencia por `webhook + key`, se identifica el `run_id`
9. se despierta a `Skiller` con `python -m skiller resume <run_id>`
10. `Skiller` reanuda el run y continua el workflow

## 2.1 Shape minimo del step en v0

La forma minima prevista para `wait_webhook` es:

```yaml
- id: wait_merge
  type: wait_webhook
  webhook: github-pr-merged
  key: "{{results.create_pr.pr}}"
```

Semantica:

- `webhook` define el canal
- `key` define la correlacion concreta dentro de ese canal

La URL esperada del proceso `webhooks` es:

```text
POST /webhooks/<webhook>/<key>
```

## 3. Que significa `WAITING`

`WAITING` significa:

- el run esta pausado
- no puede seguir sin un evento externo
- el punto actual del workflow ya esta persistido
- la espera asociada tambien esta persistida

Un run en `WAITING` no puede depender de memoria del proceso.

Debe seguir existiendo si:

- `Skiller` se reinicia
- la maquina se apaga
- el webhook llega horas despues

## 4. Que se persiste al esperar

Cuando un run entra en `wait_webhook`, el sistema debe persistir al menos:

- el estado general del run en `runs`
- la espera activa en `waits`
- la informacion necesaria para deduplicar webhooks en `webhook_receipts`

Opcionalmente puede persistir tambien una cola explicita de eventos webhook.

Lo importante funcionalmente es que el sistema pueda:

- saber que run esta esperando
- saber que `webhook` y que `key` debe esperar
- decidir si un webhook recibido corresponde o no a esa espera

## 5. Papel del proceso de `webhooks`

El proceso de `webhooks` existe para manejar entrada HTTP externa sin bloquear el runtime principal.

Su responsabilidad funcional es:

- exponer endpoints webhook
- validar firma usando el secreto registrado para ese `webhook`
- recibir peticiones externas
- validar lo minimo necesario
- invocar el contrato del runtime equivalente a `skiller webhook receive <webhook> <key> --json ...`
- dejar que `Skiller` persista el evento, haga la correlacion y determine que runs reanudar
- despertar a `Skiller` cuando haya que continuar un run

No debe ejecutar la logica del workflow.

## 6. Relacion entre `Skiller` y `webhooks`

Son procesos separados:

- proceso A: runtime principal de `Skiller`
- proceso B: proceso de `webhooks`

Esa separacion existe para que:

- `Skiller` no tenga que quedarse escuchando HTTP
- el ciclo de vida del receptor de webhooks sea independiente
- sea posible reiniciar una parte sin mezclarla con la otra

Ubicacion inicial prevista en el repo:

```text
src/skiller/tools/webhooks/
```

Administracion minima prevista del canal webhook:

- `skiller webhook register <webhook>`
- `skiller webhook remove <webhook>`

Al registrar:

- se genera un secreto por canal
- se guarda en DB
- se muestra una sola vez
- se devuelve tambien la URL plantilla del webhook

## 7. Como se identifica el run correcto

En `v0`, la correlacion no se hace con un `match` libre.

Se hace con dos datos:

- `webhook`
- `key`

Cuando entra una peticion como:

```text
POST /webhooks/github-pr-merged/42
```

el sistema busca waits activos con:

- `webhook = github-pr-merged`
- `key = 42`

Si hay coincidencias, esos runs son los candidatos a reanudarse.

## 8. Como se despierta a `Skiller`

Cuando un webhook hace match con una espera activa, el propio sistema debe reanudar el run.

El mecanismo previsto es:

```text
python -m skiller resume <run_id>
```

La idea importante es:

- no hace falta que un usuario lance manualmente un `run`
- el sistema despierta por si solo el run correcto

## 9. Que hace `Skiller` al recibir `resume`

Cuando `Skiller` recibe `resume <run_id>`:

1. carga el run desde la persistencia
2. verifica que esta en un estado reanudable
3. resuelve la espera correspondiente
4. vuelve a poner el run en ejecucion
5. reentra en el loop
6. continua desde el punto correcto del workflow

## 10. Propiedades funcionales esperadas

El sistema debe poder:

- esperar horas o dias
- sobrevivir reinicios del proceso
- sobrevivir apagados de maquina
- deduplicar webhooks repetidos
- reanudar solo los runs correctos
- evitar que el runtime principal quede bloqueado esperando HTTP

## 11. Ejemplo corto

Caso:

1. un run llega a `wait_webhook`
2. se queda en `WAITING`
3. la espera queda guardada en `waits`
4. horas despues llega un webhook de GitHub a:
   - `POST /webhooks/github-pr-merged/42`
5. el proceso `webhooks` lo persiste
6. entrega ese webhook al runtime con el contrato equivalente a `skiller webhook receive ...`
7. `Skiller` persiste el evento, correlaciona por `webhook + key` y ejecuta `resume <run_id>`
8. `Skiller` reanuda el run

## 12. Resumen corto

`wait_webhook` hace que un run quede pausado en `WAITING`.

El proceso de `webhooks` recibe eventos externos y, cuando encuentra una coincidencia por `webhook + key`, despierta a `Skiller` con:

```text
python -m skiller resume <run_id>
```

`Skiller` entonces reanuda el run desde estado persistido.
