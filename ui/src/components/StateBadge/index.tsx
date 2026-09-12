import type {ReactNode} from 'react';
import {Badge} from '@/components/ui/badge';
import {cn} from '@/lib/utils';
import type {Tone} from '../../domain';
import css from './StateBadge.module.css';

/* Utilities repeat the module colours so neither cascade order nor a registry default (`text-foreground`) can override a tone. */
const toneClass:Record<Tone,string>={
 neutral:'border-line-strong bg-graphite-850 text-stone-300',
 system:'border-system bg-system-wash text-system-ink',
 human:'border-human bg-human-wash text-human-ink',
 warning:'border-warning bg-warning-wash text-warning-ink',
 error:'border-(--signal-red) bg-error-wash text-error-ink',
};
/** A labelled state. Colour repeats the word, it never replaces it (UX §6). */
export function StateBadge({children,tone='neutral'}:{children:ReactNode;tone?:Tone}){
 return <Badge variant="outline" data-tone={tone} className={cn(css.badge,css[tone],'h-auto max-w-full gap-1 rounded-md px-2 py-1 text-[length:var(--font-size-small)] font-medium whitespace-nowrap',toneClass[tone])}>{children}</Badge>;
}
