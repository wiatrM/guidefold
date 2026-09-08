import {MemoryRouter} from 'react-router-dom';
import {ActionButton} from './index';

export default {title:'Guidefold/ActionButton',component:ActionButton};
// Existing neutral, system and human roles; disabled export has no confirmed decision.
export const Fixture={render:()=> <MemoryRouter><ActionButton>Inspect source</ActionButton>{' '}<ActionButton tone="system" href="/library">Open Library</ActionButton>{' '}<ActionButton tone="human">Record decision (local)</ActionButton>{' '}<ActionButton disabled>Export SKILL.md</ActionButton></MemoryRouter>};
