import { PageSkeleton } from '@gilbertus/ui';

export default function PeopleLoading() {
  return <PageSkeleton variant="table" rows={10} columns={5} />;
}
