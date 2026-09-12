/**
 * The landing page's citable-figure formatters, in one place because copy.md 6 requires
 * every published figure to be rendered from `src/data/research-evidence.json` and the
 * same number is quoted in more than one section: the hero proof rail, the research
 * headline, the ticker fallbacks and the results table all show Recall@10 against flat
 * search. Sharing the formatter is what makes "byte-identical" survive a refreshed
 * mirror; a second `toFixed` written by hand is how the hero and the headline drift.
 *
 * Values only, no data import: this module is pulled into the hero's first chunk, and
 * `ResearchEvidence` must stay able to hold the chart, `motion` and the ticker without
 * any of that reaching back here.
 */

/** Two decimals, the precision the results table publishes. */
export function formatFigure(value:number):string{return value.toFixed(2);}

/** The same figure as a signed change, the form a percentage-point delta is read in. */
export function formatDelta(value:number):string{return (value>0?'+':'')+formatFigure(value);}
