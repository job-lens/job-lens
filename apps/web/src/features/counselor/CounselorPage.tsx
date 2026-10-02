import { useSearchParams } from 'react-router';
import { CaseList } from './CaseList';
import { Dashboard } from './Dashboard';

export function CounselorPage() {
  const [searchParams] = useSearchParams();
  return searchParams.get('tab') === 'cases' ? <CaseList /> : <Dashboard />;
}
