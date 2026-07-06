import React, { useState } from "react";
import { Markdown } from "./Markdown";
import {
  Cpu, Globe, FileText, ShieldCheck, ShieldAlert, ShieldQuestion,
  Wrench, ChevronDown, ChevronRight, User,
} from "lucide-react";

function VerifyBadge({ status, confidence }) {
  const map = {
    VERIFIED: { cls: "bg-emerald-100 text-emerald-700 border-emerald-300", Icon: ShieldCheck },
    LIKELY: { cls: "bg-blue-100 text-blue-700 border-blue-300", Icon: ShieldQuestion },
    UNCERTAIN: { cls: "bg-yellow-100 text-yellow-800 border-yellow-400", Icon: ShieldAlert },
  };
  const { cls, Icon } = map[status] || map.LIKELY;
  return (
    <span
      data-testid="verify-badge"
      className={`inline-flex items-center gap-1 font-mono text-[10px] px-2 py-1 border rounded-sm uppercase tracking-wider ${cls}`}
    >
      <Icon className="w-3 h-3" /> {status} {confidence != null ? `· ${confidence}%` : ""}
    </span>
  );
}

function Badge({ children, testid }) {
  return (
    <span
      data-testid={testid}
      className="inline-flex items-center gap-1 font-mono text-[10px] px-2 py-1 border border-zinc-300 bg-zinc-50 rounded-sm uppercase tracking-wider text-zinc-600"
    >
      {children}
    </span>
  );
}

function Sources({ sources }) {
  if (!sources || sources.length === 0) return null;
  return (
    <div className="mt-3 border border-zinc-200 rounded-sm bg-zinc-50/60" data-testid="sources-list">
      <div className="font-mono text-[10px] uppercase tracking-widest text-zinc-500 px-3 pt-2">Sources</div>
      <div className="p-2 space-y-1">
        {sources.map((s) => (
          <div key={s.n} className="flex items-start gap-2 text-xs px-1 py-1">
            <span className="font-mono text-blue-600 font-semibold shrink-0">[S{s.n}]</span>
            {s.url ? (
              <a href={s.url} target="_blank" rel="noreferrer" className="text-zinc-700 hover:text-blue-600 truncate">
                {s.type === "web" ? <Globe className="w-3 h-3 inline mr-1" /> : <FileText className="w-3 h-3 inline mr-1" />}
                {s.label}
              </a>
            ) : (
              <span className="text-zinc-700 truncate">
                <FileText className="w-3 h-3 inline mr-1" />{s.label}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export function ChatMessage({ msg, streaming }) {
  const [showDetails, setShowDetails] = useState(false);
  const isUser = msg.role === "user";
  const meta = msg.meta;

  if (isUser) {
    return (
      <div className="flex gap-4 fade-in-up" data-testid="user-message">
        <div className="w-8 h-8 shrink-0 bg-zinc-200 border border-zinc-300 rounded-sm flex items-center justify-center">
          <User className="w-4 h-4 text-zinc-600" />
        </div>
        <div className="flex-1 pt-1">
          <div className="text-[15px] leading-relaxed whitespace-pre-wrap">{msg.content}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-4 fade-in-up" data-testid="assistant-message">
      <div className="w-8 h-8 shrink-0 bg-blue-600 rounded-sm flex items-center justify-center">
        <Cpu className="w-4 h-4 text-white" />
      </div>
      <div className="flex-1 min-w-0">
        {/* Meta badges */}
        {meta && (
          <div className="flex flex-wrap items-center gap-1.5 mb-2">
            <VerifyBadge status={meta.verify_status} confidence={meta.confidence} />
            <Badge testid="model-badge"><Cpu className="w-3 h-3" /> {meta.model}</Badge>
            {meta.category && <Badge>{meta.category}</Badge>}
            {meta.used_rag && <Badge testid="rag-badge"><FileText className="w-3 h-3" /> RAG</Badge>}
            {meta.used_web && <Badge testid="web-badge"><Globe className="w-3 h-3" /> WEB</Badge>}
            {meta.repaired && (
              <Badge testid="repaired-badge"><Wrench className="w-3 h-3" /> Self-repaired</Badge>
            )}
            {meta.validator_model && meta.validator_model !== "heuristic" && (
              <Badge testid="validator-badge"><ShieldCheck className="w-3 h-3" /> Verified by {meta.validator_model}</Badge>
            )}
          </div>
        )}

        <Markdown>{msg.content}</Markdown>
        {streaming && <span className="cursor-blink" />}

        {meta && <Sources sources={meta.sources} />}

        {/* Harness details */}
        {meta && (
          <div className="mt-2">
            <button
              data-testid="toggle-harness-details"
              onClick={() => setShowDetails((v) => !v)}
              className="flex items-center gap-1 font-mono text-[10px] uppercase tracking-widest text-zinc-400 hover:text-zinc-700 transition-colors"
            >
              {showDetails ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
              Harness trace
            </button>
            {showDetails && (
              <div className="mt-2 border border-zinc-200 rounded-sm p-3 bg-zinc-50 font-mono text-[11px] text-zinc-600 space-y-1">
                <div><span className="text-zinc-400">route:</span> {meta.route_reason}</div>
                <div><span className="text-zinc-400">role:</span> {meta.role}</div>
                {meta.validation && (
                  <>
                    <div><span className="text-zinc-400">hallucination_risk:</span> {meta.validation.hallucination_risk}</div>
                    <div><span className="text-zinc-400">addresses_question:</span> {String(meta.validation.addresses_question)}</div>
                    {meta.validation.issues?.length > 0 && (
                      <div><span className="text-zinc-400">issues:</span> {meta.validation.issues.join("; ")}</div>
                    )}
                  </>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
