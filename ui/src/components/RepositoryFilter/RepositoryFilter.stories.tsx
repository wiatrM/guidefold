import {useState} from 'react';
import {RepositoryFilter} from './index';

const repos = [
  {repo_id: 'monorepo', name: 'Monorepo', git_host_url: null, created_at: null, created: false},
  {repo_id: 'platform', name: 'Platform', git_host_url: null, created_at: null, created: false},
];
function Selector() {
  const [repo, setRepo] = useState<string | null>(null);
  return <RepositoryFilter repos={repos} value={repo} onChange={setRepo} />;
}
export default {title: 'Guidefold/RepositoryFilter', component: RepositoryFilter};
// The organisation is the default; a repository narrows. A missing list still shows the address's value.
export const Default = {render: Selector};
export const ListMissing = {render: () => <RepositoryFilter repos={null} value="archive" onChange={() => {}} />};
