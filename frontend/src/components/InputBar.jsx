import React, { useRef, useState } from "react";
import { Paperclip, Globe, FileText, Send, Loader2, Square, ChevronDown, Layers } from "lucide-react";

export function InputBar({
  value, onChange, onSend, onStop, streaming, uploading, onUpload,
  useRag, setUseRag, useWeb, setUseWeb, useMulti, setUseMulti, mode, setMode,
  models, manualModel, setManualModel,
}) {
  const fileRef = useRef(null);
  const [modelOpen, setModelOpen] = useState(false);

  const handleKey = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!streaming && value.trim()) onSend();
    }
  };

  return (
    <div className="w-full max-w-4xl mx-auto px-4 pb-5">
      <div className="bg-white border border-zinc-300 rounded-sm shadow-sm">
        <textarea
          data-testid="chat-input"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKey}
          rows={1}
          placeholder="Ask anything — the harness will route, retrieve, verify and validate…"
          className="w-full resize-none bg-transparent px-4 pt-4 pb-2 text-[15px] outline-none placeholder:text-zinc-400 max-h-40"
          style={{ minHeight: "48px" }}
        />

        {/* Controls row */}
        <div className="flex items-center gap-2 px-3 pb-3 flex-wrap">
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.docx,.txt,.csv,.md"
            className="hidden"
            data-testid="file-input"
            onChange={(e) => { if (e.target.files[0]) { onUpload(e.target.files[0]); e.target.value = ""; } }}
          />
          <button
            data-testid="upload-btn"
            onClick={() => fileRef.current?.click()}
            disabled={uploading}
            className="flex items-center gap-1.5 px-2.5 py-1.5 border border-zinc-300 rounded-sm text-xs font-medium hover:bg-zinc-100 transition-all active:scale-[0.98] disabled:opacity-50"
          >
            {uploading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Paperclip className="w-3.5 h-3.5" />}
            Upload
          </button>

          <button
            data-testid="rag-toggle"
            onClick={() => setUseRag(!useRag)}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 border rounded-sm text-xs font-medium transition-all active:scale-[0.98] ${
              useRag ? "bg-blue-600 text-white border-blue-600" : "border-zinc-300 hover:bg-zinc-100"
            }`}
          >
            <FileText className="w-3.5 h-3.5" /> RAG
          </button>

          <button
            data-testid="web-toggle"
            onClick={() => setUseWeb(!useWeb)}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 border rounded-sm text-xs font-medium transition-all active:scale-[0.98] ${
              useWeb ? "bg-blue-600 text-white border-blue-600" : "border-zinc-300 hover:bg-zinc-100"
            }`}
          >
            <Globe className="w-3.5 h-3.5" /> Internet
          </button>

          <button
            data-testid="multi-toggle"
            onClick={() => setUseMulti(!useMulti)}
            title="Multi-model critique: draft → critique → fact-check → finalize"
            className={`flex items-center gap-1.5 px-2.5 py-1.5 border rounded-sm text-xs font-medium transition-all active:scale-[0.98] ${
              useMulti ? "bg-yellow-400 text-black border-yellow-400" : "border-zinc-300 hover:bg-zinc-100"
            }`}
          >
            <Layers className="w-3.5 h-3.5" /> Ensemble
          </button>

          {/* Mode toggle */}
          <div className="flex items-center border border-zinc-300 rounded-sm overflow-hidden text-xs font-mono">
            <button
              data-testid="mode-auto-btn"
              onClick={() => setMode("auto")}
              className={`px-2.5 py-1.5 transition-all ${mode === "auto" ? "bg-zinc-950 text-white" : "hover:bg-zinc-100"}`}
            >
              AUTO
            </button>
            <button
              data-testid="mode-manual-btn"
              onClick={() => setMode("manual")}
              className={`px-2.5 py-1.5 transition-all ${mode === "manual" ? "bg-zinc-950 text-white" : "hover:bg-zinc-100"}`}
            >
              MANUAL
            </button>
          </div>

          {/* Manual model selector */}
          {mode === "manual" && (
            <div className="relative">
              <button
                data-testid="model-select-btn"
                onClick={() => setModelOpen((v) => !v)}
                className="flex items-center gap-1.5 px-2.5 py-1.5 border border-zinc-300 rounded-sm text-xs font-mono hover:bg-zinc-100 max-w-[180px]"
              >
                <span className="truncate">{manualModel || "select model"}</span>
                <ChevronDown className="w-3.5 h-3.5 shrink-0" />
              </button>
              {modelOpen && (
                <div
                  data-testid="model-dropdown"
                  className="absolute bottom-full mb-1 left-0 w-64 max-h-72 overflow-y-auto bg-white border border-zinc-300 rounded-sm shadow-lg z-20"
                >
                  {models.map((m) => (
                    <button
                      key={m}
                      data-testid={`model-option-${m}`}
                      onClick={() => { setManualModel(m); setModelOpen(false); }}
                      className={`w-full text-left px-3 py-2 text-xs font-mono hover:bg-zinc-100 ${
                        manualModel === m ? "bg-blue-50 text-blue-700" : ""
                      }`}
                    >
                      {m}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          <div className="flex-1" />

          {streaming ? (
            <button
              data-testid="stop-btn"
              onClick={onStop}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-zinc-950 text-white rounded-sm text-xs font-medium hover:bg-zinc-800 transition-all active:scale-[0.98]"
            >
              <Square className="w-3.5 h-3.5" /> Stop
            </button>
          ) : (
            <button
              data-testid="send-btn"
              onClick={onSend}
              disabled={!value.trim()}
              className="flex items-center gap-1.5 px-4 py-1.5 bg-blue-600 text-white rounded-sm text-sm font-medium hover:bg-blue-700 transition-all active:scale-[0.98] disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Send className="w-4 h-4" /> Send
            </button>
          )}
        </div>
      </div>
      <div className="text-center font-mono text-[10px] text-zinc-400 mt-2 uppercase tracking-widest">
        Harness · classify → route → retrieve → verify → validate → repair
      </div>
    </div>
  );
}
