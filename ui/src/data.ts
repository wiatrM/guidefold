import type {Fixture, Proposal, DataState} from './domain';

/** Public fixture boundary, composed by the application entrypoint.
 * It has no API client and does not assert a production data contract.
 */
export function createFixtureAdapter(input: Fixture) {
  const fixture = input;
  const proposalSkill = fixture.skills.find(skill => skill.name === 'postgres-auth');
  if (!proposalSkill) throw new Error('Fixture proposal source postgres-auth is missing.');
  const selectedProposalSkill = proposalSkill;
  const findSkill = (id: string | null | undefined) => fixture.skills.find(skill => skill.id === id);
  const visibleSkills = (state: DataState) => state === 'partial'
    ? [selectedProposalSkill, ...fixture.skills.filter(skill => skill.id !== selectedProposalSkill.id).slice(0, 7)]
    : fixture.skills;
  const sourceURL = (path: string) => 'https://github.com/wiatrM/guidefold/blob/' + fixture.commit + '/examples/monorepo/' + path;
  const defaultProposal = (): Proposal => ({stage: 'draft', candidate: selectedProposalSkill.raw, digest: selectedProposalSkill.revision, reason: ''});
  return {fixture, proposalSkill: selectedProposalSkill, findSkill, visibleSkills, sourceURL, defaultProposal};
}
export type FixtureAdapter = ReturnType<typeof createFixtureAdapter>;
