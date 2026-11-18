# Basic Headless LM Studio Usage

This guide explains the concepts and workflow for serving models with LM Studio. The commands match the installation used in this experience; options may change between versions. Refer to the installed tool's help and the [official documentation](https://lmstudio.ai/docs/developer) for details.

## Components and Prerequisites

- **`llmster`**: the LM Studio background service that allows operation without opening the graphical application.
- **`lms`**: the LM Studio command-line tool. It manages the service, models, and HTTP server. It is not the Skiller command-line tool.

Verify that these components are installed. If they are missing, request their installation.

Also request permission to run the `lms` command and access its installation path. If `lms` is not on the PATH, use its installed location. Run management commands on the machine that will host the models.

## 1. Start the Background Service

On the server machine, check the status of `llmster` and start it if stopped:

```bash
lms daemon status
lms daemon up
```

## 2. Start the HTTP Server

Start the server on the host's local network IP address:

```bash
lms server start --bind <LOCAL_IP> --port 1234
```

## 3. Choose a Model

List the models available on disk and the instances currently loaded in memory:

```bash
lms ls
lms ps
```

## 4. Load, Unload, and Switch Models

Load a model, for example Qwen 27B IQ4_XS with maximum GPU offload, a 32K context, one slot, and MTP disabled:

```bash
lms load qwen3.8-27b@iq4_xs --gpu max --context-length 32768 --parallel 1 --no-speculative-draft-mtp
lms ps
```

**Load only once** and reuse the instance. Repeating `lms load` may create a duplicate instance and consume more VRAM. The 32K context is a limit, not the number of tokens used by each request.

To unload an instance, use its identifier from `lms ps`:

```bash
lms unload qwen3.8-27b@iq4_xs
```

To switch models, wait for requests to finish, unload the current model, and load the new one:

```bash
lms unload <CURRENT_IDENTIFIER>
lms load <NEW_MODEL>
lms ps
```

Also update the model identifier in the client. Refer to `lms load --help` to adjust the load settings for the new model.

To unload all instances and free their memory:

```bash
lms unload --all
```

## 5. Stop the HTTP Server

```bash
lms server stop
lms server status
```

This stops the API; do not use it as a substitute for unloading models. To also free memory and shut down the background service:

```bash
lms unload --all
lms daemon down
```

## Idle Power Consumption

A loaded model occupies VRAM and may increase GPU power consumption even when no inference is running. The increase depends on the hardware, model, and runtime configuration.

**Unload the model when it will not be used** to free VRAM and reduce idle power consumption. The HTTP server can remain running:

```bash
lms unload --all
```
