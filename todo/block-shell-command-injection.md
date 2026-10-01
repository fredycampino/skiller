# Endurecimiento mínimo de la allowlist de shell

Estado: propuesta pendiente de implementación. Este alcance sustituye el diseño anterior de parser general, AST tipado y refactor de validación de rutas.

## Objetivo

Cerrar los bypass conocidos que permiten iniciar curl u otros comandos no autorizados mediante sintaxis del shell exterior, manteniendo la interfaz command como texto y la arquitectura actual.

Es un endurecimiento focalizado, no una garantía completa sobre cualquier expresión shell. No se implementa Bash completo, un sandbox ni bloqueo general de Internet.

## Problema y reproducciones

La segmentación actual puede validar solo el primer ejecutable y omitir ejecuciones adicionales.

| Expresión | Allowlist relevante | Tratamiento propuesto |
| --- | --- | --- |
| `pwd` seguido de nueva línea y `curl --version` | pwd | Separar y validar ambos ejecutables |
| `pwd & curl --version` | pwd | Rechazar background |
| `pwd |& curl --version` | pwd | Rechazar operador |
| `pwd $(curl --version)` | pwd | Rechazar sustitución activa |
| pwd con sustitución mediante backticks | pwd | Rechazar sustitución activa |
| `cat <(curl --version)` | cat | Rechazar sustitución de proceso |
| `time curl --version` | time | Rechazar palabra reservada activa |
| `! curl --version` | ! | Rechazar negación de pipeline |

Con solo pwd permitido, time y ! ya se bloquean. Sus reproducciones requieren permitir esas primeras palabras. El problema no es específico de curl.

## Modelo de confianza y límites

- El comando autorizado se ejecuta sin reescribirlo.
- El entorno heredado del worker es confiable; no se contempla su alteración interna entre validación y ejecución.
- request.env es entrada de la llamada, no parte de esa confianza.
- Permitir intérpretes, scripts o programas que lanzan otros procesos delega su comportamiento: no se analizan argumentos internos de bash, Python, env, xargs, find, etc.
- allowed_paths conserva su contrato de validación de rutas visibles; no es confinamiento del sistema de archivos.
- Se mantiene la selección actual del shell. Las pruebas cubren Bash y la implementación disponible de /bin/sh, no todos los shells posibles.
- Un shell arbitrario seleccionado por el operador debe ser compatible; la confianza en su configuración no demuestra equivalencia de dialectos.

## Cambios incluidos

### 1. Completar la segmentación exterior

Reconocer comandos simples separados por nueva línea, `;`, `|`, `&&` y `||`. Validar el ejecutable de cada segmento antes de ejecutar la expresión completa.

Respetar comillas, escapes, comentarios y continuaciones de línea. Los separadores dentro de contenido literal no dividen comandos.

Conservar la semántica de heredocs citados, corrigiendo primero su detección contextual: solo sus cuerpos reales quedan fuera de comandos y candidatos de ruta, y la validación se reanuda tras el delimitador. Mantener las restricciones existentes sobre heredocs sin citar o sin cierre. La corrección del reconocimiento compartido no debe confundirse con aplicar toda la nueva gramática al modo sin allowlist.

### 2. Rechazar construcciones que ocultan ejecución

Con allowlist activa, rechazar en contexto sintáctico activo:

- Sustitución de comandos mediante `$()` o backticks.
- Sustitución de procesos mediante `<()` o `>()`.
- Background `&`.
- Operadores `|&`, `&>` y `&>>`.
- Grupos, subshells, funciones y estructuras de control.
- time, !, coproc y palabras reservadas con función estructural no soportada.

No basta buscar subcadenas mediante regex global. La comprobación debe distinguir sintaxis activa de literales, escapes, comentarios y cuerpos de heredoc citados. Por ejemplo, `printf '$(curl)'` no contiene ejecución anidada.

Rechazar & evita incorporar supervisión de procesos desacoplados. &> y &>> tampoco son seguros como subconjunto común: Bash los interpreta como redirecciones, mientras dash puede interpretar background. Para combinar salidas se conserva `>archivo 2>&1`.

Distinguir `&&` y duplicaciones como `2>&1` del operador de background. Si una forma no puede clasificarse con fiabilidad, rechazarla explícitamente, no asumir que es segura.

### 3. Exigir ejecutables literales

La palabra completa del ejecutable debe normalizarse sin expansiones activas.

- Admitir `pwd`, `'pwd'` y concatenaciones puramente literales como `p"w"d`.
- Rechazar `$COMMAND`, `${COMMAND}`, `cu${X}rl` y sus variantes parcialmente expandidas.
- Rechazar tilde, globbing, expansión aritmética y otras expansiones activas en el nombre del ejecutable.
- No reinterpretar valores expandidos de argumentos como sintaxis shell.

Mantener la normalización existente para cotejar nombres y rutas de ejecutables con allowed_commands. Los argumentos conservan las expansiones de rutas ya admitidas; las sustituciones ejecutables se rechazan en cualquier posición activa.

Las asignaciones iniciales siguen condicionadas por allow_env_prefix. No confundirlas ni confundir redirecciones con el ejecutable. Un segmento con ejecutable no identificable se rechaza, nunca se autoriza por defecto.

En esta contingencia, rechazar explícitamente cualquier redirección anterior al ejecutable con allowlist activa, incluso si aparece después de una asignación inicial. No saltarla para autorizar el ejecutable posterior: el extractor actual puede omitir su destino. Por ejemplo, `>/fuera/salida.txt pwd` y `</fuera/entrada.txt pwd` deben bloquearse antes del lanzamiento.

No ampliar ahora el soporte de esas formas ni introducir un AST de redirecciones. Las redirecciones posteriores al ejecutable conservan su contrato, con pruebas explícitas de destinos de lectura y escritura fuera de allowed_paths. Identificar mejor un ejecutable no debe convertir un bloqueo accidental anterior en una autorización sin validar sus rutas.

### 4. Restringir entorno proporcionado por la llamada

Con allowlist activa, request.env debe estar ausente o vacío. Rechazar un valor no vacío antes del lanzamiento.

Motivo: BASH_ENV puede iniciar un script antes del comando validado; otras variables pueden afectar carga o resolución de código. Una blacklist de BASH_ENV no resuelve el problema general.

allow_env_prefix sigue siendo una delegación explícita distinta: permite influir en el programa autorizado mediante asignaciones iniciales. No se promete identidad inmutable del binario ni neutralizar variables que afectan al programa delegado.

Sin allowlist, request.env conserva su comportamiento actual. No se diseña ahora una política de variables permitidas.

## Componentes y responsabilidad

Mantener ShellCommandPolicy y ShellCommandExpander; no introducir un AST de Bash ni contratos generales para redirecciones.

Extraer únicamente un analizador pequeño, unitariamente testeable, para la sintaxis exterior:

- Entrada: expresión command.
- Salida: segmentos fiables e información mínima necesaria para identificar ejecutables literales, o un error explícito.
- Responsabilidad: límites exteriores y detección contextual de construcciones rechazadas.
- No conoce allowed_commands, no ejecuta comandos ni expande variables del entorno.

El contrato concreto se define al revisar el código, usando tipos pequeños e inmutables si la información cruza componentes. Debe conservar contexto de comillas y escapes hasta comprobar el ejecutable; quitar comillas prematuramente recrearía errores anteriores.

La policy valida los ejecutables de esos segmentos y mantiene las reglas críticas y validación de rutas existentes. El expander conserva su responsabilidad actual y sus regresiones.

Reutilizar el tratamiento existente de heredocs únicamente después de corregir su reconocimiento contextual. No entregar al analizador texto saneado que pueda haber ocultado comandos reales. La detección debe respetar comentarios, comillas, escapes y continuaciones antes de excluir un cuerpo. No crear dos escáneres independientes; ajustar localmente el reconocimiento y sus interfaces.

Un operador dentro de un comentario no declara un heredoc. Una continuación tras una declaración tampoco inicia automáticamente el cuerpo en la siguiente línea física: la sintaxis activa anterior al verdadero cuerpo debe permanecer visible. Si no se puede distinguir con fiabilidad, rechazar la variante explícitamente en modo allowlist, sin eliminar contenido por aproximación.

No convertir esta tarea en un refactor general de extracción de rutas. Tampoco afirmar que toda validación consume un AST único: esa garantía del plan anterior se retira. Si una interacción concreta con la segmentación impide cerrar un bypass, corregirla localmente y cubrirla con una regresión.

## Comportamiento por modo

| Aspecto | Allowlist activa | Allowlist desactivada |
| --- | --- | --- |
| Análisis exterior nuevo | Aplicar | No introducir restricciones nuevas |
| Ejecutables de segmentos | Validar todos | Mantener comportamiento existente |
| Sintaxis rechazada por este cambio | Bloquear antes de ejecutar | Conservar contrato previo |
| request.env no vacío | Rechazar | Conservar |
| Rutas y reglas críticas | Mantener | Mantener |

No retirar restricciones previas del modo sin allowlist ni cambiar sus valores por defecto.

## Fuera de alcance

- Cambiar command por argv o eliminar el shell.
- Adoptar o implementar un parser completo de Bash.
- AST general de palabras, asignaciones y redirecciones.
- Refactor general de allowed_paths o expansión por palabras.
- Cambiar selección de shell, persistir effective_shell o rediseñar el worker.
- Supervisión de background, sandboxing o aislamiento de red.
- Interpretar el comportamiento interno de ejecutables permitidos.
- Cambios de TUI.

Si cerrar los casos enumerados exige recrear una parte sustancial de Bash o rediseñar las rutas, detener la implementación y revisar el alcance. No ampliar silenciosamente este plan.

## Pruebas y aceptación

### Analizador unitario

- Nueva línea, ;, |, && y || producen los segmentos esperados.
- Sustituciones, background y construcciones complejas enumeradas se rechazan.
- Operadores combinados se distinguen de redirecciones de descriptor.
- Comillas, escapes, comentarios y continuaciones no ocultan un segundo comando ni generan falsos positivos con literales.
- Heredocs citados conservan cuerpos literales y permiten validar comandos posteriores.
- Ejecutables totalmente y parcialmente dinámicos se rechazan; concatenaciones literales se normalizan.
- Sintaxis ambigua no produce una autorización parcial.

### Integración de policy

- Con pwd permitido, cada reproducción aplicable con curl no permitido queda bloqueada antes de iniciar el proceso.
- Con cat permitido, las sustituciones de proceso quedan bloqueadas.
- time y ! activos quedan bloqueados aunque aparezcan en allowed_commands.
- Los conectores admitidos funcionan cuando todos sus ejecutables están permitidos.
- Comandos normales, literales y redirecciones habituales mantienen su comportamiento.
- Probar allow_env_prefix activo e inactivo.
- Probar request.env ausente, vacío y no vacío en ambos modos.
- Mantener reglas críticas y las regresiones de rutas, especialmente `$TMP_TEST` y `${TMP_TEST}`.
- El modo sin allowlist no adquiere los nuevos bloqueos sintácticos.

### Regresiones obligatorias del review

Falso heredoc dentro de comentario:

```bash
pwd # <<'pwd'
printf 'COMANDO_OCULTO\n'
pwd
```

Con solo pwd y cat permitidos, el printf debe permanecer visible y causar rechazo. El comentario no declara un heredoc. Verificar que la corrección no excluye ese comando como supuesto cuerpo literal.

Continuación tras una declaración real:

```bash
cat <<'EOF' \
$(printf 'COMANDO_OCULTO')
texto literal
EOF
```

La sustitución es parte del comando, antes del cuerpo real. Debe detectarse y bloquearse, o rechazarse explícitamente toda la variante si excede el analizador mínimo. Nunca ocultarla como contenido literal.

Redirecciones y rutas:

- Rechazar `>/fuera/salida.txt pwd` y `</fuera/entrada.txt pwd`, incluidos equivalentes con prefijos de asignación, antes de iniciar el proceso.
- Comprobar que `pwd >/fuera/salida.txt` y `cat </fuera/entrada.txt` también se bloquean por sus destinos fuera de allowed_paths.
- Usar rutas de fixtures fuera de las raíces permitidas, sin tocar archivos reales del usuario.
- Verificar que el runner no se invoca tras el rechazo: ninguna apertura, creación o truncado debe ocurrir.
- Conservar controles positivos de heredocs citados y redirecciones posteriores a destinos permitidos.

Estos casos son requisitos de aceptación del endurecimiento, no trabajo diferido. Las reproducciones provienen del review; deben convertirse en pruebas antes de declarar resuelto el fallo.

### Ejecución segura

Usar fixtures temporales sin acceso a red ni cambios de configuración o datos del usuario. Para BASH_ENV, comprobar que se rechaza la petición antes del lanzamiento; si se usa un marcador temporal, no debe crearse.

Verificar casos representativos con Bash y /bin/sh disponible. Registrar la implementación de /bin/sh y no extrapolar a cualquier shell.

Si se realizan runs de QA, usar AGENT_DB_PATH aislado y comprobar argumentos y resultados reales de herramientas, no solo el resumen del agente.

Aceptación global: cerrar todos los bypass enumerados, conservar usos normales y regresiones previas, y documentar los límites sin presentar el resultado como garantía exhaustiva sobre shell.

## Antecedente de QA: rutas mediante variables

Este fallo es distinto de la ejecución de comandos ocultos y sus regresiones deben conservarse.

Run histórico ab41cbc4-8b63-4b43-bda9-31621466da09, agente ../qa/flows.yaml:

- `ls $TMP_TEST/develop/tmp`: ejecutado con exit code 0.
- `ls /home/max/develop/tmp`: bloqueado por allowed_paths.

Verificaciones posteriores reportadas con Skiller pipx 0.1.0-beta.41 y TMP_TEST=/home/max:

- a1f95c1c-31cd-4493-b184-f41cf360054d: `ls $TMP_TEST/tmp` bloqueado por /home/max/tmp.
- 5e25f2ae-b18f-4776-8c31-011feaee1639: `ls ${TMP_TEST}/tmp` bloqueado por la misma ruta.

Son evidencias conservadas de la conversación, no pruebas ejecutadas al actualizar este documento. No confirman los futuros cambios de segmentación ni deben confundirse con pruebas bloqueadas previamente por una asignación sin ejecutable o una variable inexistente.

## Entrega

1. Revisar arquitectura, estilo y código actual del paquete.
2. Añadir regresiones focales de los bypass conocidos.
3. Implementar el analizador mínimo e integrarlo en policy solo con allowlist activa.
4. Añadir el rechazo de request.env y probar ambos modos.
5. Verificar regresiones de herramientas, Ruff, formato y diff check; ampliar pruebas según el impacto real.
6. Actualizar agent-config-tools.md y steps/shell.md con sintaxis, restricciones y fronteras de confianza.

Referencias: application/tools/shell/policy.py, process_tool.py y command_expander.py dentro de packages/skiller/src/skiller; documentación de arquitectura y herramientas bajo packages/skiller/docs.

No crear commits ni publicar sin autorización. Este documento no declara implementado ni verificado el endurecimiento propuesto.
