'use client';

import { useEffect, useRef, useState } from 'react';
import { Check, ChevronDown, Copy, FileCode2 } from 'lucide-react';
import { cn } from '@/lib/utils';

export type CodeBlockVariant = 'Default' | 'Numbered';

export interface CodeBlockProps {
  code: string;
  filename?: string;
  language?: string;
  collapsedLines?: number;
  variant?: CodeBlockVariant;
  className?: string;
}

export function CodeBlock({
  code,
  filename,
  language = 'tsx',
  collapsedLines = 8,
  variant = 'Default',
  className,
}: CodeBlockProps) {
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  useEffect(() => () => clearTimeout(timer.current), []);

  const lines = code.replace(/\n$/, '').split('\n');
  const collapsible = lines.length > collapsedLines;
  const visible = expanded || !collapsible ? lines : lines.slice(0, collapsedLines);

  async function copy() {
    setCopyError(false);
    setCopied(false);
    try {
      await navigator.clipboard.writeText(code);
    } catch {
      setCopyError(true);
      return;
    }
    setCopied(true);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setCopied(false), 1600);
  }

  return (
    <figure
      className={cn(
        'w-full overflow-hidden rounded-xl border border-[var(--line-strong)] bg-[var(--graphite-850)]',
        className,
      )}
    >
      <div className="flex items-center justify-between gap-3 border-b border-black/[0.06] px-3 py-1.5 dark:border-white/[0.07]">
        <span className="flex min-w-0 items-center gap-1.5">
          <FileCode2 aria-hidden="true" className="size-4 shrink-0 text-[var(--system-ink)]" />
          <span className="truncate font-mono text-xs text-[var(--stone-300)]">
            {filename ?? language}
          </span>
        </span>
        <button
          type="button"
          onClick={copy}
          aria-label={copied ? 'Code copied' : 'Copy code'}
          className="bg-transparent grid size-11 shrink-0 place-items-center rounded-md text-[var(--stone-300)] hover:text-[var(--stone-100)] focus-visible:outline-2 focus-visible:outline-[var(--survey-teal)]"
        >
          <span className="relative grid size-3.5 place-items-center">
            <Copy
              aria-hidden="true"
              className={cn(
                'absolute size-3.5 transition-[opacity,filter] duration-200 motion-reduce:transition-none ease-[cubic-bezier(0.23,1,0.32,1)]',
                copied ? 'opacity-0 blur-[2px]' : 'opacity-100 blur-0',
              )}
            />
            <Check
              aria-hidden="true"
              className={cn(
                'absolute size-3.5 text-[var(--system-ink)] transition-[opacity,filter] duration-200 motion-reduce:transition-none ease-[cubic-bezier(0.23,1,0.32,1)]',
                copied ? 'opacity-100 blur-0' : 'opacity-0 blur-[2px]',
              )}
            />
          </span>
        </button>
      </div>

      <div className="overflow-x-auto py-4" tabIndex={0} role="region" aria-label={filename ?? 'Code'}>
        {visible.map((line, index) => (
          <div key={index} className="flex whitespace-pre-wrap px-4 py-1 font-mono text-xs leading-relaxed">
            {variant === 'Numbered' && (
              <span
                aria-hidden
                className="mr-3 w-5 shrink-0 select-none text-right tabular-nums text-[var(--stone-300)]"
              >
                {index + 1}
              </span>
            )}
            <span className="min-w-0 break-words text-[var(--stone-100)]">{line || ' '}</span>
          </div>
        ))}
      </div>

      {collapsible && (
        <button
          type="button"
          aria-expanded={expanded}
          onClick={() => setExpanded((value) => !value)}
          className="bg-transparent flex min-h-11 w-full items-center justify-center gap-2 border-t border-[var(--line-strong)] px-3 text-xs text-[var(--stone-300)] hover:bg-[var(--graphite-800)] hover:text-[var(--stone-100)] focus-visible:outline-2 focus-visible:outline-[var(--survey-teal)]"
        >
          {expanded ? 'collapse' : `${lines.length - collapsedLines} more lines`}
          <ChevronDown
            aria-hidden="true"
            className={cn(
              'size-3 transition-transform duration-200 motion-reduce:transition-none ease-[cubic-bezier(0.23,1,0.32,1)]',
              expanded && 'rotate-180',
            )}
          />
        </button>
      )}
      <span role="status" className={copyError?'block px-4 py-2 text-xs text-[var(--error-ink)]':'sr-only'}>{copyError?'Clipboard unavailable. Select the source text to copy it.':copied?'Source copied to clipboard.':''}</span>
    </figure>
  );
}

export default CodeBlock;
