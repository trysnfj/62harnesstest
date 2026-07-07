import React, { useState } from "react";
import { Markdown } from "./Markdown";
import {
  Cpu, Globe, FileText, ShieldCheck, ShieldAlert, ShieldQuestion,
  Wrench, ChevronDown, ChevronRight, User, Layers, ThumbsUp, ThumbsDown, Brain,
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

export function ChatMessage({ msg, streaming, onFeedback }) {
  const [showDetails, setShowDetails] = useState(false);
  const [showThinking, setShowThinking] = useState(!!streaming);
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
            {meta.ensemble ? (
              <Badge testid="ensemble-badge"><Layers className="w-3 h-3" /> Ensemble · {meta.model}</Badge>
            ) : (
              <Badge testid="model-badge"><Cpu className="w-3 h-3" /> {meta.model}</Badge>
            )}
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

        {msg.thinking && (
          <div className="mb-2 border border-violet-200 rounded-sm bg-violet-50/50" data-testid="thinking-panel">
            <button
              data-testid="toggle-thinking"
              onClick={() => setShowThinking((v) => !v)}
              className="flex items-center gap-1.5 w-full px-3 py-1.5 font-mono text-[10px] uppercase tracking-widest text-violet-600 hover:text-violet-800 transition-colors"
            >
              <Brain className="w-3 h-3" />
              {streaming ? "Thinking…" : "Thought process"}
              {showThinking ? <ChevronDown className="w-3 h-3 ml-auto" /> : <ChevronRight className="w-3 h-3 ml-auto" />}
            </button>
            {showThinking && (
              <div className="px-3 pb-2 text-xs text-zinc-500 italic whitespace-pre-wrap max-h-60 overflow-y-auto leading-relaxed">
                {msg.thinking}
              </div>
            )}
          </div>
        )}

        <Markdown>{msg.content}</Markdown>
        {streaming && <span className="cursor-blink" />}

        {meta && <Sources sources={meta.sources} />}

        {/* Feedback (reinforcement signal) — only on finalized messages */}
        {meta && !streaming && onFeedback && (
          <div className="flex items-center gap-2 mt-3" data-testid="feedback-controls">
            <span className="font-mono text-[10px] uppercase tracking-widest text-zinc-400">Helpful?</span>
            <button
              data-testid="feedback-up"
              onClick={() => onFeedback(msg.id, "up")}
              className={`p-1.5 border rounded-sm transition-all active:scale-95 ${
                msg.feedback === "up" ? "bg-emerald-100 border-emerald-400 text-emerald-700" : "border-zinc-300 text-zinc-400 hover:text-zinc-700 hover:bg-zinc-100"
              }`}
            >
              <ThumbsUp className="w-3.5 h-3.5" />
            </button>
            <button
              data-testid="feedback-down"
              onClick={() => onFeedback(msg.id, "down")}
              className={`p-1.5 border rounded-sm transition-all active:scale-95 ${
                msg.feedback === "down" ? "bg-red-100 border-red-400 text-red-700" : "border-zinc-300 text-zinc-400 hover:text-zinc-700 hover:bg-zinc-100"
              }`}
            >
              <ThumbsDown className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

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
                {meta.ensemble && (
                  <>
                    <div className="text-zinc-400 pt-1">multi-model ensemble:</div>
                    <div>· drafter: {meta.ensemble.drafter}</div>
                    <div>· critic: {meta.ensemble.critic}</div>
                    <div>· fact-checker: {meta.ensemble.verifier}</div>
                    <div>· finalizer: {meta.ensemble.finalizer}</div>
                  </>
                )}
                {meta.validator_model && (
                  <div><span className="text-zinc-400">validated_by:</span> {meta.validator_model}</div>
                )}
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
