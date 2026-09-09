'use client';

import * as React from 'react';
import { BorderBeam, type BorderBeamColorVariant } from 'border-beam';
import { Search, X } from 'lucide-react';

import { cn } from '@/lib/utils';
import {useBeamMotion} from './use-beam-motion';
import { useSurfaceTheme, type SurfaceTheme } from '@/components/spectrumui/use-surface-theme';

export interface BeamSearchProps {
  label: string;
  value?: string;
  defaultValue?: string;
  onChange?: (value: string) => void;
  /** Fires on Enter with the current value */
  onSubmit?: (value: string) => void;
  placeholder?: string;
  /** Keep the beam running even without focus. Default false */
  alwaysOn?: boolean;
  /** Palette: "colorful" | "ocean" | "sunset" | "mono". Default "colorful" */
  colorVariant?: BorderBeamColorVariant;
  /** "auto" follows a `.dark`/`.light` class on <html>, then the OS. Default "auto" */
  theme?: SurfaceTheme;
  /** Right-hand slot, e.g. a keyboard hint */
  trailing?: React.ReactNode;
  className?: string;
}

export function BeamSearch({
  label,
  value,
  defaultValue = '',
  onChange,
  onSubmit,
  placeholder = 'Search…',
  alwaysOn = false,
  colorVariant = 'colorful',
  theme = 'auto',
  trailing,
  className,
}: BeamSearchProps) {
  const resolved = useSurfaceTheme(theme);
  const motionAllowed = useBeamMotion();
  const [inner, setInner] = React.useState(defaultValue);
  const [focused, setFocused] = React.useState(false);
  const inputRef = React.useRef<HTMLInputElement>(null);
  const current = value ?? inner;

  const update = (next: string) => {
    if (value === undefined) setInner(next);
    onChange?.(next);
  };

  return (
    <BorderBeam
      size="line"
      colorVariant={colorVariant}
      theme={resolved}
      active={motionAllowed && (alwaysOn || focused)}
      className={cn('w-full', className)}
    >
      <div
        className={cn(
          'flex h-12 w-full items-center gap-3 rounded-xl border border-black/10 bg-white px-3.5 transition-colors dark:border-white/12 dark:bg-neutral-950',
          focused && 'border-black/20 dark:border-white/20',
        )}
      >
        <Search className="size-4 shrink-0 text-neutral-400" aria-hidden />
        <input
          ref={inputRef}
          type="search"
          aria-label={label}
          value={current}
          placeholder={placeholder}
          onChange={(event) => update(event.target.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') onSubmit?.(current);
            if (event.key === 'Escape') update('');
          }}
          className="min-h-0 min-w-0 flex-1 rounded-none border-0 bg-transparent p-0 text-[15px] text-neutral-900 shadow-none placeholder:text-neutral-500 dark:text-neutral-100 dark:placeholder:text-neutral-400 [&::-webkit-search-cancel-button]:hidden"
        />
        {current ? (
          <button
            type="button"
            aria-label="Clear"
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => {
              update('');
              inputRef.current?.focus();
            }}
            className="flex size-11 shrink-0 items-center justify-center rounded-full text-neutral-500 transition-colors hover:bg-black/5 hover:text-neutral-700 dark:text-neutral-400 dark:hover:bg-white/8 dark:hover:text-neutral-200"
          >
            <X className="size-3.5" />
          </button>
        ) : (
          trailing
        )}
      </div>
    </BorderBeam>
  );
}
