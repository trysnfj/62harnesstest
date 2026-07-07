import React, { useEffect, useRef, useState } from "react";
import "@/App.css";
import { Toaster, toast } from "sonner";
import { Menu, Cpu, Loader2, Sparkles } from "lucide-react";
import { Sidebar } from "@/components/Sidebar";
import { ChatMessage } from "@/components/ChatMessage";
import { InputBar } from "@/components/InputBar";
import { SettingsDialog } from "@/components/SettingsDialog";
import {
  listModels, listChats, createChat, deleteChat, getMessages,
  listDocuments, uploadDocument, deleteDocument, streamChat,
} from "@/lib/apiClient";

const STAGE_LABEL = {
  classify: "Classifying", route: "Routing", retrieve: "Retrieving docs",
  search: "Searching web", generate: "Generating", validate: "Validating", repair: "Repairing",
  draft: "Drafting (model A)", critique: "Critiquing (model B)",
  factcheck: "Fact-checking (model C)", finalize: "Finalizing (best model)",
};

export default function App() {
  const [chats, setChats] = useState([]);
  const [activeChatId, setActiveChatId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [models, setModels] = useState([]);

  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [stage, setStage] = useState(null);
  const [streamMsg, setStreamMsg] = useState(null);

  const [useRag, setUseRag] = useState(true);
  const [useWeb, setUseWeb] = useState(false);
  const [useMulti, setUseMulti] = useState(false);
  const [mode, setMode] = useState("auto");
  const [manualModel, setManualModel] = useState(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [mobileSidebar, setMobileSidebar] = useState(false);

  const abortRef = useRef(null);
  const scrollRef = useRef(null);

  useEffect(() => {
    listModels().then((m) => { setModels(m); if (m.length && !manualModel) setManualModel(m[0]); }).catch(() => {});
    refreshChats();
  }, []);

  useEffect(() => {
    if (activeChatId) {
      getMessages(activeChatId).then(setMessages).catch(() => setMessages([]));
      listDocuments(activeChatId).then(setDocuments).catch(() => setDocuments([]));
    } else {
      setMessages([]); setDocuments([]);
    }
  }, [activeChatId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, streamMsg, stage]);

  const refreshChats = async () => {
    const c = await listChats();
    setChats(c);
    return c;
  };

  const handleNewChat = () => { setActiveChatId(null); setMessages([]); setDocuments([]); setMobileSidebar(false); };

  const handleSelectChat = (id) => { setActiveChatId(id); setMobileSidebar(false); };

  const handleDeleteChat = async (id) => {
    await deleteChat(id);
    if (activeChatId === id) handleNewChat();
    refreshChats();
  };

  const handleUpload = async (file) => {
    let chatId = activeChatId;
    if (!chatId) {
      const c = await createChat();
      chatId = c.id;
      setActiveChatId(c.id);
      refreshChats();
    }
    setUploading(true);
    try {
      await uploadDocument(file, chatId);
      const docs = await listDocuments(chatId);
      setDocuments(docs);
      setUseRag(true);
      toast.success(`Uploaded ${file.name}`);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteDocument = async (id) => {
    await deleteDocument(id);
    setDocuments((d) => d.filter((x) => x.id !== id));
    toast.success("Document removed");
  };

  const handleStop = () => {
    abortRef.current?.abort();
    setStreaming(false);
    setStage(null);
  };

  const handleSend = async () => {
    const text = input.trim();
    if (!text || streaming) return;

    let chatId = activeChatId;
    if (!chatId) {
      const c = await createChat();
      chatId = c.id;
      setActiveChatId(c.id);
    }

    setInput("");
    setMessages((m) => [...m, { id: `u-${Date.now()}`, role: "user", content: text }]);
    setStreaming(true);
    setStage("classify");

    const draft = { id: `a-${Date.now()}`, role: "assistant", content: "", meta: null };
    setStreamMsg(draft);

    const controller = new AbortController();
    abortRef.current = controller;

    let errored = false;
    let watchdog = null;
    const resetWatchdog = () => {
      if (watchdog) clearTimeout(watchdog);
      watchdog = setTimeout(() => { errored = true; controller.abort(); }, 240000);
    };
    resetWatchdog();

    try {
      await streamChat(
        { chat_id: chatId, message: text, mode, manual_model: manualModel, use_rag: useRag, use_web: useWeb, use_multi: useMulti },
        (evt) => {
          resetWatchdog();
          if (evt.type === "status") setStage(evt.stage);
          else if (evt.type === "meta") {
            draft.meta = {
              ...(draft.meta || {}),
              model: evt.model, role: evt.role, category: evt.classification?.category,
              route_reason: evt.route_reason, ensemble: evt.ensemble || draft.meta?.ensemble,
            };
            setStreamMsg({ ...draft });
          } else if (evt.type === "token") {
            draft.content += evt.text;
            setStreamMsg({ ...draft });
          } else if (evt.type === "replace") {
            draft.content = evt.text;
            setStreamMsg({ ...draft });
          } else if (evt.type === "done") {
            draft.content = evt.content;
            draft.meta = {
              model: evt.model, role: evt.role, category: evt.category, route_reason: evt.route_reason,
              validator_model: evt.validator_model, ensemble: evt.ensemble,
              used_rag: evt.used_rag, used_web: evt.used_web, sources: evt.sources,
              validation: evt.validation, repaired: evt.repaired, confidence: evt.confidence,
              verify_status: evt.verify_status,
            };
            setStreamMsg({ ...draft });
          } else if (evt.type === "error") {
            errored = true;
            toast.error(evt.message || "Generation failed");
          }
        },
        controller.signal
      );
      // finalize
      if (errored && !draft.content) {
        setMessages((m) => [...m, {
          id: draft.id, role: "assistant",
          content: "⚠️ The model was unavailable (rate-limited). Please try again.",
          meta: { model: "—", verify_status: "UNCERTAIN", confidence: 0, category: "error" },
        }]);
      } else {
        setMessages((m) => [...m, { ...draft }]);
        refreshChats();
      }
      setStreamMsg(null);
    } catch (e) {
      if (e.name === "AbortError" && !errored) {
        // user pressed Stop — keep partial
        if (draft.content) setMessages((m) => [...m, { ...draft }]);
      } else {
        toast.error("Connection lost. Please retry.");
        if (draft.content) {
          setMessages((m) => [...m, { ...draft }]);
        } else {
          setMessages((m) => [...m, {
            id: draft.id, role: "assistant",
            content: "⚠️ Something went wrong. Please try again.",
            meta: { model: "—", verify_status: "UNCERTAIN", confidence: 0, category: "error" },
          }]);
        }
      }
      setStreamMsg(null);
    } finally {
      if (watchdog) clearTimeout(watchdog);
      setStreaming(false);
      setStage(null);
      abortRef.current = null;
    }
  };

  const showEmpty = messages.length === 0 && !streamMsg;

  return (
    <div className="h-screen flex overflow-hidden bg-zinc-50 text-zinc-950">
      <Toaster position="top-center" richColors />
      <Sidebar
        chats={chats}
        activeChatId={activeChatId}
        onNewChat={handleNewChat}
        onSelectChat={handleSelectChat}
        onDeleteChat={handleDeleteChat}
        documents={documents}
        onDeleteDocument={handleDeleteDocument}
        onOpenSettings={() => setSettingsOpen(true)}
        mobileOpen={mobileSidebar}
        onCloseMobile={() => setMobileSidebar(false)}
      />

      <div className="flex-1 flex flex-col min-w-0">
        {/* Top bar */}
        <header className="h-14 border-b border-zinc-300 flex items-center gap-3 px-4 bg-white/80 backdrop-blur">
          <button className="md:hidden" onClick={() => setMobileSidebar(true)} data-testid="open-sidebar-btn">
            <Menu className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-2">
            <span className="font-heading font-black tracking-tight">
              {mode === "auto" ? "Auto routing" : "Manual mode"}
            </span>
            <span className="font-mono text-[10px] uppercase tracking-widest text-zinc-400 hidden sm:inline">
              {mode === "manual" ? manualModel : "harness selects best model"}
            </span>
          </div>
        </header>

        {/* Messages */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto" data-testid="messages-area">
          {showEmpty ? (
            <div className="h-full flex flex-col items-center justify-center px-6 text-center">
              <div className="w-14 h-14 bg-blue-600 rounded-sm flex items-center justify-center mb-5">
                <Cpu className="w-8 h-8 text-white" />
              </div>
              <h1 className="font-heading font-black text-3xl sm:text-4xl tracking-tight mb-3">
                Harness-based AI chat
              </h1>
              <p className="text-zinc-500 max-w-md text-[15px] mb-6">
                Every query is classified, routed to the best model, grounded in your documents & the web,
                then validated and self-repaired before you see it.
              </p>
              <div className="flex flex-wrap gap-2 justify-center max-w-lg">
                {["Explain transformers simply", "Write a Python web scraper", "Summarise my uploaded PDF", "What's the latest on Mars missions?"].map((s) => (
                  <button
                    key={s}
                    data-testid={`suggestion-${s.slice(0,10)}`}
                    onClick={() => setInput(s)}
                    className="flex items-center gap-1.5 px-3 py-2 border border-zinc-300 rounded-sm text-xs hover:bg-zinc-100 transition-all bg-white"
                  >
                    <Sparkles className="w-3 h-3 text-blue-600" /> {s}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="max-w-4xl mx-auto px-4 py-6 space-y-6">
              {messages.map((m) => (
                <ChatMessage key={m.id} msg={m} />
              ))}
              {streamMsg && (
                <>
                  {stage && streaming && (
                    <div className="max-w-4xl flex items-center gap-2 pl-12 font-mono text-[11px] uppercase tracking-widest text-blue-600" data-testid="stage-indicator">
                      <Loader2 className="w-3 h-3 animate-spin" />
                      {STAGE_LABEL[stage] || stage}…
                    </div>
                  )}
                  <ChatMessage msg={streamMsg} streaming={streaming} />
                </>
              )}
            </div>
          )}
        </div>

        {/* Input */}
        <InputBar
          value={input}
          onChange={setInput}
          onSend={handleSend}
          onStop={handleStop}
          streaming={streaming}
          uploading={uploading}
          onUpload={handleUpload}
          useRag={useRag}
          setUseRag={setUseRag}
          useWeb={useWeb}
          setUseWeb={setUseWeb}
          useMulti={useMulti}
          setUseMulti={setUseMulti}
          mode={mode}
          setMode={setMode}
          models={models}
          manualModel={manualModel}
          setManualModel={setManualModel}
        />
      </div>

      <SettingsDialog open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  );
}
