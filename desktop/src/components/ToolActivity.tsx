import { toolKey, type ToolActivity as Activity } from "../state/reducer";

export function ToolActivity({ tools }: { tools: Activity[] }) {
  const recent = tools.slice(-5).reverse();
  return (
    <section className="tools" data-testid="tools">
      <h2>Tool activity</h2>
      {recent.length === 0 && <p className="muted">Nothing yet.</p>}
      {recent.map((t) => (
        <div key={toolKey(t)} className={`tool tool-${t.status}`}>
          <div>
            <code>{t.tool}</code> <span className="muted">{t.status === "running" ? t.label : t.status}</span>
          </div>
          {t.summary && <div className="summary">{t.summary}</div>}
          {t.results.length > 0 && (
            <ul>
              {t.results.map((r) => (
                <li key={r.id}>
                  <code>{r.id}</code> {r.title} <span className="muted">{r.subtitle}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      ))}
    </section>
  );
}
