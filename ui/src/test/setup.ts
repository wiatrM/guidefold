import '@testing-library/jest-dom/vitest';
import {cleanup} from '@testing-library/react';
import {afterEach} from 'vitest';
// jsdom has no layout, so the shell's scroll reset would log "Not implemented".
window.scrollTo=()=>{};
afterEach(()=>cleanup());
