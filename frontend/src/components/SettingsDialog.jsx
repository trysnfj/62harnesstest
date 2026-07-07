import React, { useEffect, useState } from "react";
import { X, Cpu, BarChart3 } from "lucide-react";
import { getConfig, getStats } from "../lib/apiClient";

export function SettingsDialog({ open, onClose }) {
  const [config, setConfig] = useState(null);
  const [stats, setStats] = useState(null);
  const [tab, setTab] = useState("router");

  useEffect(() => {
    if (open) {
      getConfig().then(setConfig).catch(() => {});
      getStats().then(setStats).catch(() => {});
    }
  }, [open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40" onClick={onClose}>
      <div
        data-testid="settings-dialog"
        className="bg-white border border-zinc-300 rounded-sm shadow-xl w-full max-w-2xl max-h-[85vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-zinc-300">
          <h2 className="font-heading font-black text-lg tracking-tight">Settings & Model Router</h2>
          <button onClick={onClose} data-testid="close-settings-btn"><X className="w-5 h-5" /></button>
        </div>

        <div className="flex gap-1 px-5 pt-3 border-b border-zinc-200">
          {["router", "performance"].map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              data-testid={`settings-tab-${t}`}
              className={`px-3 py-2 text-sm font-mono uppercase tracking-wider border-b-2 -mb-px transition-all ${
                tab === t ? "border-blue-600 text-blue-600" : "border-transparent text-zinc-500 hover:text-zinc-800"
              }`}
            >
              {t}
            </button>
          ))}
        </div>

        <div className="overflow-y-auto p-5">
          {tab === "router" && config && (
            <div className="space-y-4">
              <p className="text-sm text-zinc-600">
                In <strong>Auto</strong> mode the harness classifies each query and routes it to the best model below.
                Switch to <strong>Manual</strong> in the input bar to pick a specific model.
              </p>
              <div className="border border-zinc-200 rounded-sm overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-zinc-100 font-mono text-[10px] uppercase tracking-widest text-zinc-500">
                    <tr>
                      <th className="text-left px-3 py-2">Role</th>
                      <th className="text-left px-3 py-2">Model</th>
                      <th className="text-left px-3 py-2">Use</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(config.model_roles).map(([role, model]) => (
                      <tr key={role} className="border-t border-zinc-200">
                        <td className="px-3 py-2 font-mono text-xs">{role}</td>
                        <td className="px-3 py-2 font-mono text-xs text-blue-600">{model}</td>
                        <td className="px-3 py-2 text-xs text-zinc-500">{config.role_notes?.[role] || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {tab === "performance" && (
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-sm text-zinc-600">
                <BarChart3 className="w-4 h-4" />
                Model performance memory — {stats?.total_runs || 0} total runs logged
              </div>
              {stats?.info_quality && Object.keys(stats.info_quality).length > 0 && (
                <div className="border border-zinc-200 rounded-sm p-3" data-testid="info-quality">
                  <div className="font-mono text-[10px] uppercase tracking-widest text-zinc-500 mb-2">
                    Information quality by topic (reinforcement signal)
                  </div>
                  <div className="space-y-1">
                    {Object.entries(stats.info_quality).map(([cat, d]) => {
                      const esc = (stats.escalated || []).includes(cat);
                      const pct = Math.max(0, Math.min(100, Math.round(d.info_quality * 100)));
                      return (
                        <div key={cat} className="text-xs font-mono flex items-center gap-2">
                          <span className="w-40 truncate text-zinc-600">{cat}</span>
                          <div className="flex-1 h-2 bg-zinc-100 rounded-sm overflow-hidden">
                            <div className={`h-full ${esc ? "bg-yellow-400" : "bg-emerald-500"}`} style={{ width: `${pct}%` }} />
                          </div>
                          <span className="text-zinc-500 w-10 text-right">{pct}%</span>
                          <span className="text-zinc-400 w-24 text-right">👍{d.up} 👎{d.down} · {d.runs}r</span>
                          {esc && <span className="text-yellow-600" title="Auto-escalated: grounds & verifies harder">⤴ verify+</span>}
                        </div>
                      );
                    })}
                  </div>
                  <div className="text-[10px] text-zinc-400 mt-2">
                    Low-scoring topics (yellow / more 👎) are auto-escalated: the harness adds web grounding and stricter independent verification — it improves the <strong>information</strong>, it does not favour any model.
                  </div>
                </div>
              )}
              {stats && Object.keys(stats.by_model || {}).length > 0 ? (
                <div className="border border-zinc-200 rounded-sm overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="bg-zinc-100 font-mono text-[10px] uppercase tracking-widest text-zinc-500">
                      <tr>
                        <th className="text-left px-3 py-2">Model</th>
                        <th className="text-left px-3 py-2">Runs</th>
                        <th className="text-left px-3 py-2">Avg conf.</th>
                        <th className="text-left px-3 py-2">Repairs</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(stats.by_model).map(([m, d]) => (
                        <tr key={m} className="border-t border-zinc-200">
                          <td className="px-3 py-2 font-mono text-xs text-blue-600">{m}</td>
                          <td className="px-3 py-2 font-mono text-xs">{d.runs}</td>
                          <td className="px-3 py-2 font-mono text-xs">{d.avg_confidence}%</td>
                          <td className="px-3 py-2 font-mono text-xs">{d.repairs}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="text-sm text-zinc-400 py-6 text-center">No runs yet. Send some messages first.</div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
