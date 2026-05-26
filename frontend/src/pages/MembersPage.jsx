import MemberTable from "../components/members/MemberTable";

function MembersPage() {
  return (
    <div className="stack">
      <header className="page-head">
        <h2>Members Workspace</h2>
        <p>Member management extracted into reusable table components.</p>
      </header>
      <MemberTable />
    </div>
  );
}

export default MembersPage;
