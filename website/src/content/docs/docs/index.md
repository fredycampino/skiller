---
title: Documentation
description: Learn skiller.run through executable demos, guides, and reference documentation.
template: splash
hero:
  title: Build your first agentic workflow
  tagline: Start with a working YAML demo, then learn the runtime concepts behind it.
  actions:
    - text: Explore demos
      link: /docs/demos/
      icon: right-arrow
      variant: primary
    - text: Install skiller
      link: /docs/getting-started/installation/
      icon: download
---

import { Card, CardGrid } from '@astrojs/starlight/components';

## Start here

<CardGrid>
  <Card title="Demos" icon="rocket">
    Run small, complete workflows before reading the full reference.
  </Card>
  <Card title="Getting started" icon="open-book">
    Install skiller, run a flow, and inspect its persisted execution.
  </Card>
  <Card title="Concepts" icon="puzzle">
    Understand workflows, steps, runs, agents, waiting, and events.
  </Card>
  <Card title="Reference" icon="document">
    Look up YAML contracts, CLI commands, configuration, and runtime behavior.
  </Card>
</CardGrid>

## Recommended path

1. Run the [Hello workflow](/docs/demos/hello-workflow/).
2. Try the [Interactive flow](/docs/demos/interactive-flow/) to see persisted waiting and resume.
3. Configure an LLM and run the [Agent chat](/docs/demos/agent-chat/).
4. Use the reference when you need exact fields or commands.
