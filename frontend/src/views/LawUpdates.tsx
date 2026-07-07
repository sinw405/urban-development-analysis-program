import { useEffect, useState } from "react";
import { listLawUpdates } from "../api/lawUpdates";
import type { LawUpdateEvent } from "../api/types";

export function LawUpdates() {
  const [items, setItems] = useState<LawUpdateEvent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setIsLoading(true);
    setError(null);
    try {
      const data = await listLawUpdates();
      setItems(data.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load law update events");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  return (
    <section className="panel">
      <div className="panelHeader">
        <h1>Law Update Events</h1>
        <button onClick={() => void load()} disabled={isLoading}>Refresh</button>
      </div>
      {error && <p className="error">{error}</p>}
      {isLoading ? <p className="empty">Loading events...</p> : null}
      {!isLoading && items.length === 0 ? <p className="empty">감지된 법령 개정 이벤트 없음</p> : null}
      {items.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>event_id</th>
              <th>change_type</th>
              <th>effective_date</th>
              <th>impacted_step_codes</th>
              <th>status</th>
              <th>source</th>
            </tr>
          </thead>
          <tbody>
            {items.map((event) => (
              <tr key={event.event_id}>
                <td>{event.event_id}</td>
                <td>{event.change_type}</td>
                <td>{event.effective_date ?? "-"}</td>
                <td>{event.impacted_step_codes.length > 0 ? event.impacted_step_codes.join(", ") : "[]"}</td>
                <td>{event.status}</td>
                <td>{event.source}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
