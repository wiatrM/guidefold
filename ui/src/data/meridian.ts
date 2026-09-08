import rawFixture from './fixture.json';
import {createFixtureAdapter} from '../data';
import type {Fixture} from '../domain';

/** Explicit public Meridian fixture composition; no private data or network client. */
export const meridian = createFixtureAdapter(rawFixture as Fixture);
