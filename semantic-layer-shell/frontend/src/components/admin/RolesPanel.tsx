import { useEffect, useState } from "react";
import { fetchJson } from "../../services/api";

export function RolesPanel() {
  const [me, setMe] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    fetchJson<Record<string, unknown>>("/api/v1/users/me").then(setMe).catch(() => setMe(null));
  }, []);

  return (
    <div className="panel">
      <h2>Admin — Current User</h2>
      {me ? <pre>{JSON.stringify(me, null, 2)}</pre> : <p>Unable to load user info.</p>}
    </div>
  );
}
