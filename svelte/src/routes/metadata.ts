import type { FOLDER_TYPES } from './utils';

export interface FileMetadata {
  width: number | null;
  height: number | null;
  format: string;
  workflow: any;
  prompt: any;
  parameters: string | null;
}

export interface SamplerSummary {
  type: string;
  seed?: any;
  steps?: any;
  cfg?: any;
  sampler?: any;
  scheduler?: any;
  denoise?: any;
  positive?: string;
  negative?: string;
  positiveGenerated?: boolean;
  negativeGenerated?: boolean;
}

export interface GenerationSummary {
  models: Array<string>;
  loras: Array<{ name: string; strengthModel?: any; strengthClip?: any }>;
  samplers: Array<SamplerSummary>;
}

export async function fetchMetadata(
  comfyUrl: string,
  folderType: FOLDER_TYPES,
  file: any,
): Promise<FileMetadata | null> {
  const params = new URLSearchParams({
    folder_type: folderType,
    folder_path: file.folder_path || '',
    filename: file.name,
  });
  const res = await fetch(`${comfyUrl}/browser/files/metadata?${params}`);
  if (!res.ok) {
    return null;
  }

  return await res.json();
}

const MAX_DEPTH = 20;
const VALUE_KEYS = ['value', 'seed', 'noise_seed', 'int', 'float', 'number', 'boolean', 'text', 'string'];
// Inputs that carry text through utility nodes, most specific first:
// wildcard processors keep the expanded text in populated_text, previews pass it on through source.
const STRING_KEYS = [
  'populated_text', 'value', 'text', 'string', 'prompt', 'source', 'text_g', 'text_l', 'wildcard_text',
  'multiline_text',
];
// Inputs of text encoders that hold the prompt.
const TEXT_KEYS = ['populated_text', 'text', 'text_g', 'text_l', 'prompt', 'clip_l', 't5xxl', 'string', 'value'];
const CONDITIONING_KEYS = ['conditioning', 'conditioning_1', 'conditioning_to', 'conditioning_from'];

interface TextContext {
  // Set when the text comes from a node that writes it at run time (e.g. an LLM), so it is not in the file.
  generated: boolean;
}

function isLink(value: any) {
  return Array.isArray(value) && value.length === 2 && typeof value[0] === 'string';
}

function linkedNode(graph: any, value: any) {
  return isLink(value) ? graph[value[0]] : undefined;
}

// Switch nodes pick one of two inputs with a boolean.
function switchBranch(graph: any, inputs: any, depth: number) {
  if (!('switch' in inputs) || !('on_true' in inputs || 'on_false' in inputs)) {
    return undefined;
  }
  return resolveValue(graph, inputs.switch, depth + 1) ? inputs.on_true : inputs.on_false;
}

// Follows a link like ["12", 0] to a primitive value, e.g. a seed coming from a Primitive node.
function resolveValue(graph: any, value: any, depth = 0): any {
  if (!isLink(value)) {
    return value;
  }
  const node = graph[value[0]];
  if (!node || depth >= MAX_DEPTH) {
    return undefined;
  }
  const inputs = node.inputs || {};
  const branch = switchBranch(graph, inputs, depth);
  if (branch !== undefined) {
    return resolveValue(graph, branch, depth + 1);
  }
  for (const key of VALUE_KEYS) {
    if (key in inputs) {
      return resolveValue(graph, inputs[key], depth + 1);
    }
  }
  return undefined;
}

// Follows a link to the string it carries, through switches, previews, concatenation and wildcards.
function resolveString(graph: any, value: any, ctx: TextContext, depth = 0): string | undefined {
  if (typeof value === 'string') {
    return value;
  }
  const node = linkedNode(graph, value);
  if (!node || depth >= MAX_DEPTH) {
    return undefined;
  }
  const inputs = node.inputs || {};
  const classType: string = node.class_type || '';

  const branch = switchBranch(graph, inputs, depth);
  if (branch !== undefined) {
    return resolveString(graph, branch, ctx, depth + 1);
  }

  if ('string_a' in inputs && 'string_b' in inputs) {
    const parts = ['string_a', 'string_b', 'string_c', 'string_d']
      .filter((key) => key in inputs)
      .map((key) => resolveString(graph, inputs[key], ctx, depth + 1))
      .filter((v) => v);
    const delimiter = resolveString(graph, inputs.delimiter, ctx, depth + 1) ?? '';
    return parts.length > 0 ? parts.join(delimiter) : undefined;
  }

  // Prompt stylers output the styled positive on 0 and negative on 1.
  if ('text_positive' in inputs && 'text_negative' in inputs) {
    return resolveString(graph, value[1] === 1 ? inputs.text_negative : inputs.text_positive, ctx, depth + 1);
  }

  // An LLM rewrites the text at run time and the result isn't saved, so show what it was given.
  if (/TextGenerate|LLM|Ollama|Caption|Florence|Gemini|GPT/i.test(classType)) {
    ctx.generated = true;
    for (const key of ['prompt', 'text', 'user_prompt', 'input']) {
      if (key in inputs) {
        return resolveString(graph, inputs[key], ctx, depth + 1);
      }
    }
    return undefined;
  }

  for (const key of STRING_KEYS) {
    if (key in inputs) {
      const text = resolveString(graph, inputs[key], ctx, depth + 1);
      if (text) {
        return text;
      }
    }
  }
  return undefined;
}

// Follows a conditioning link back to the node holding the prompt text.
function resolveText(graph: any, link: any, ctx: TextContext, depth = 0): string | undefined {
  const node = linkedNode(graph, link);
  if (!node || depth >= MAX_DEPTH) {
    return undefined;
  }
  const inputs = node.inputs || {};

  // An empty conditioning made from another one; it carries no text of its own.
  if (node.class_type === 'ConditioningZeroOut') {
    return undefined;
  }

  const branch = switchBranch(graph, inputs, depth);
  if (branch !== undefined) {
    return resolveText(graph, branch, ctx, depth + 1);
  }

  // Encoders with both prompts output the negative conditioning on their second output.
  if ('negative_prompt' in inputs && link[1] === 1) {
    return resolveString(graph, inputs.negative_prompt, ctx, depth + 1);
  }

  const texts = TEXT_KEYS
    .filter((key) => key in inputs)
    .map((key) => resolveString(graph, inputs[key], ctx, depth + 1))
    .filter((v) => typeof v === 'string' && v.length > 0);
  if (texts.length > 0) {
    return [...new Set(texts)].join('\n');
  }

  // Pass-through nodes with both conditionings (ControlNet apply, reference latents)
  // output positive on 0 and negative on 1.
  if ('positive' in inputs && 'negative' in inputs) {
    return resolveText(graph, link[1] === 1 ? inputs.negative : inputs.positive, ctx, depth + 1);
  }
  for (const key of CONDITIONING_KEYS) {
    if (isLink(inputs[key])) {
      const text = resolveText(graph, inputs[key], ctx, depth + 1);
      if (text) {
        return text;
      }
    }
  }
  return undefined;
}

function summarizeSampler(graph: any, classType: string, inputs: any): SamplerSummary {
  // SamplerCustomAdvanced splits its settings over guider, noise, sampler and sigmas nodes.
  const guider = linkedNode(graph, inputs.guider)?.inputs || {};
  const noise = linkedNode(graph, inputs.noise)?.inputs || {};
  const sampler = linkedNode(graph, inputs.sampler)?.inputs || {};
  const sigmas = linkedNode(graph, inputs.sigmas)?.inputs || {};
  const pick = (...values: Array<any>) => values.map((v) => resolveValue(graph, v)).find((v) => v !== undefined);

  const positiveCtx = { generated: false };
  const negativeCtx = { generated: false };
  const positive = resolveText(graph, inputs.positive ?? guider.positive ?? guider.conditioning, positiveCtx);
  const negative = resolveText(graph, inputs.negative ?? guider.negative, negativeCtx);

  return {
    type: classType,
    seed: pick(inputs.seed, inputs.noise_seed, noise.noise_seed),
    steps: pick(inputs.steps, sigmas.steps),
    cfg: pick(inputs.cfg, guider.cfg),
    sampler: pick(inputs.sampler_name, sampler.sampler_name),
    scheduler: pick(inputs.scheduler, sigmas.scheduler),
    denoise: pick(inputs.denoise, sigmas.denoise),
    positive,
    negative,
    positiveGenerated: positiveCtx.generated,
    negativeGenerated: negativeCtx.generated,
  };
}

export function summarizePrompt(graph: any): GenerationSummary | null {
  if (!graph || typeof graph !== 'object') {
    return null;
  }

  const summary: GenerationSummary = { models: [], loras: [], samplers: [] };
  const nodes = Object.keys(graph)
    .sort((a, b) => a.localeCompare(b, undefined, { numeric: true }))
    .map((id) => graph[id])
    .filter((node) => node && node.inputs);

  for (const node of nodes) {
    const inputs = node.inputs;
    const classType: string = node.class_type || '';

    for (const key of ['ckpt_name', 'unet_name']) {
      const name = resolveValue(graph, inputs[key]);
      if (typeof name === 'string' && !summary.models.includes(name)) {
        summary.models.push(name);
      }
    }

    const loraName = resolveValue(graph, inputs.lora_name);
    if (typeof loraName === 'string') {
      summary.loras.push({
        name: loraName,
        strengthModel: resolveValue(graph, inputs.strength_model),
        strengthClip: resolveValue(graph, inputs.strength_clip),
      });
    }

    // latent_image tells real samplers apart from helpers such as KSamplerSelect.
    if ((classType.includes('KSampler') || classType.startsWith('SamplerCustom')) && 'latent_image' in inputs) {
      summary.samplers.push(summarizeSampler(graph, classType, inputs));
    }
  }

  if (summary.models.length === 0 && summary.loras.length === 0 && summary.samplers.length === 0) {
    return null;
  }
  return summary;
}

export async function copyText(text: string) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    // navigator.clipboard is unavailable on plain http other than localhost.
    const textarea = document.createElement('textarea');
    textarea.value = text;
    document.body.appendChild(textarea);
    textarea.select();
    const ok = document.execCommand('copy');
    textarea.remove();
    return ok;
  }
}

export function downloadJson(data: any, filename: string) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}
