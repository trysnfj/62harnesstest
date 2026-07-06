import React from "react";
import { Plus, MessageSquare, FileText, Settings, Trash2, Cpu, X } from "lucide-react";

export function Sidebar({
  chats, activeChatId, onNewChat, onSelectChat, onDeleteChat,
  documents, onDeleteDocument, onOpenSettings, mobileOpen, onCloseMobile,
}) {
  return (
    <>
      {mobileOpen && (
        <div className="fixed inset-0 bg-black/40 z-30 md:hidden" onClick={onCloseMobile} />
      )}
      <aside
        data-testid="sidebar"
        className={`fixed md:static z-40 top-0 left-0 h-full w-72 bg-zinc-100 border-r-2 border-zinc-300 flex flex-col transition-transform duration-200 ${
          mobileOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"
        }`}
      >
        {/* Brand */}
        <div className="px-4 py-4 border-b border-zinc-300 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-blue-600 flex items-center justify-center rounded-sm">
              <Cpu className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="font-heading font-black text-sm leading-none tracking-tight">HARNESS</div>
              <div className="font-mono text-[10px] text-zinc-500 uppercase tracking-widest">AI Router</div>
            </div>
          </div>
          <button className="md:hidden" onClick={onCloseMobile} data-testid="close-sidebar-btn">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* New chat */}
        <div className="p-3">
          <button
            data-testid="new-chat-btn"
            onClick={onNewChat}
            className="w-full flex items-center gap-2 px-3 py-2.5 bg-zinc-950 text-white rounded-sm text-sm font-medium hover:bg-zinc-800 transition-all duration-200 active:scale-[0.98]"
          >
            <Plus className="w-4 h-4" /> New chat
          </button>
        </div>

        {/* Scrollable */}
        <div className="flex-1 overflow-y-auto px-3 pb-3 space-y-5">
          {/* Chats */}
          <div>
            <div className="font-mono text-[10px] uppercase tracking-widest text-zinc-500 px-1 mb-2">Chat history</div>
            <div className="space-y-0.5">
              {chats.length === 0 && (
                <div className="text-xs text-zinc-400 px-1 py-2">No chats yet</div>
              )}
              {chats.map((c) => (
                <div
                  key={c.id}
                  data-testid={`chat-item-${c.id}`}
                  onClick={() => onSelectChat(c.id)}
                  className={`group flex items-center gap-2 px-2.5 py-2 rounded-sm cursor-pointer transition-all duration-150 ${
                    activeChatId === c.id ? "bg-zinc-300/70" : "hover:bg-zinc-200/70"
                  }`}
                >
                  <MessageSquare className="w-3.5 h-3.5 text-zinc-500 shrink-0" />
                  <span className="text-sm truncate flex-1">{c.title}</span>
                  <button
                    data-testid={`delete-chat-${c.id}`}
                    onClick={(e) => { e.stopPropagation(); onDeleteChat(c.id); }}
                    className="opacity-0 group-hover:opacity-100 text-zinc-400 hover:text-red-600 transition-opacity"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Documents */}
          <div>
            <div className="font-mono text-[10px] uppercase tracking-widest text-zinc-500 px-1 mb-2">Uploaded documents</div>
            <div className="space-y-0.5">
              {documents.length === 0 && (
                <div className="text-xs text-zinc-400 px-1 py-2">No documents in this chat</div>
              )}
              {documents.map((d) => (
                <div
                  key={d.id}
                  data-testid={`doc-item-${d.id}`}
                  className="group flex items-center gap-2 px-2.5 py-2 rounded-sm hover:bg-zinc-200/70 transition-all"
                >
                  <FileText className="w-3.5 h-3.5 text-blue-600 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm truncate">{d.name}</div>
                    <div className="font-mono text-[10px] text-zinc-400">{d.num_chunks} chunks</div>
                  </div>
                  <button
                    data-testid={`delete-doc-${d.id}`}
                    onClick={() => onDeleteDocument(d.id)}
                    className="opacity-0 group-hover:opacity-100 text-zinc-400 hover:text-red-600"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Settings */}
        <div className="p-3 border-t border-zinc-300">
          <button
            data-testid="open-settings-btn"
            onClick={onOpenSettings}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-sm text-sm hover:bg-zinc-200/70 transition-all"
          >
            <Settings className="w-4 h-4" /> Settings & Router
          </button>
        </div>
      </aside>
    </>
  );
}
