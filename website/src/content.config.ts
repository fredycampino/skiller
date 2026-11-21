import { glob } from 'astro/loaders';
import { z } from 'astro/zod';
import { defineCollection } from 'astro:content';
import { docsLoader } from '@astrojs/starlight/loaders';
import { docsSchema } from '@astrojs/starlight/schema';

export const collections = {
  blog: defineCollection({
    loader: glob({ pattern: '**/*.md', base: './src/content/blog' }),
    schema: z.object({ title: z.string(), description: z.string(), publishedAt: z.coerce.date() }),
  }),
  docs: defineCollection({ loader: docsLoader(), schema: docsSchema() }),
};
