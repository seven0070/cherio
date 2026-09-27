import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { ArrowUp, Check, ChevronDown, Download, Menu, MessageSquare, Mic, Moon, Pencil, Pin, PinOff, Plus, Search, Settings2, SquarePen, Sun, Trash2, X } from "lucide-react";
import { Button } from "./components/ui/button";

type Task = {id:string; goal:string; state:string; result:string};
type State = {tasks:Task[]; models:string[]; selected_model:string; status:string; handoff_available:boolean};
const session = new URLSearchParams(location.search).get('session') || '';
const preview = import.meta.env.DEV && !session;
async function api<T>(name:string, data:unknown = {}):Promise<T> {
  if(preview) throw new Error('Visual preview only. Start bella-desktop for local actions.');
  const response=await fetch('/api/'+name,{method:'POST',headers:{'Content-Type':'application/json','X-Bella-Session':session},body:JSON.stringify(data)});
  const body=await response.json();
  if(!response.ok) throw new Error(body.error || 'Local request failed');
  return body as T;
}

type Message = { role: "user" | "assistant"; content: string };
type Chat = { id: string; title: string; messages: Message[]; pinned?: boolean };

function BellaMark({ className = "" }: { className?: string }) { return <span className={className} aria-hidden="true">✦</span>; }

export default function App() {
  const isMac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.userAgent);
  const newChatTitle = isMac ? "New chat (⌘⇧O)" : "New chat (Ctrl+Shift+O)";
  const [text, setText] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [chats, setChats] = useState<Chat[]>([]);
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [mode, setMode] = useState<"Fast" | "Think" | "Bella">("Fast");
  const [taskComposer,setTaskComposer] = useState(false);
  const [state, setState] = useState<State>({tasks:[],models:[],selected_model:"",status:"Connecting locally...",handoff_available:true});
  const [selectedTask,setSelectedTask] = useState("");

  const [confirm,setConfirm] = useState<Task|null>(null);
  const [busy,setBusy] = useState(false);
  const [recording,setRecording] = useState(false);
  const [voiceReply,setVoiceReply] = useState(false);
  const [bellaTyping,setBellaTyping] = useState(false);
  const [voiceTranscript,setVoiceTranscript] = useState(false);
  const [modeOpen, setModeOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [dark, setDark] = useState(true);
  const [notice, setNotice] = useState("");
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameText, setRenameText] = useState("");
  const [askText, setAskText] = useState("");
  const [askAnswer, setAskAnswer] = useState("");
  const [filterText, setFilterText] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const chatRef = useRef<HTMLDivElement>(null);

  async function refresh(){try{setState(await api<State>('state'));}catch(e){setNotice(String(e))}}
  useEffect(()=>{
    if(preview){setState({tasks:[],models:[],selected_model:'',status:'Visual preview: start bella-desktop for local actions.',handoff_available:false});return;}
    void refresh();
    let cancelled=false;
    void api<{chats:Chat[]}>('chats/list').then(v=>{if(!cancelled)setChats(v.chats)}).catch(e=>{if(!cancelled)setNotice(String(e))});
    return ()=>{cancelled=true};
  },[]);

  async function submit(event?: FormEvent) {
    event?.preventDefault();
    const content=text.trim();
    if(!content || busy)return;
    if(taskComposer){
      if(!state.handoff_available){setNotice('Task handoff needs the editable source install.');return;}
      setBusy(true);
      try {const result=await api<{task:Task}>('task/propose',{goal:content});setSelectedTask(result.task.id);setTaskComposer(false);setText('');await refresh();setNotice('Task proposed. Nothing ran. Review the full text before approving.');}
      catch(e){setNotice(String(e))}finally{setBusy(false)}
      return;
    }
    if(!state.selected_model){setNotice('Choose an installed Ollama model in Settings first.');setSettingsOpen(true);return;}
    const userMessage:Message={role:'user',content};
    const currentMessages=messages;
    const currentChatId=activeChatId;
    setMessages(previous=>[...previous,userMessage]);setText('');setVoiceTranscript(false);setBusy(true);
    try {
      const answer=await api<{answer:string}>(mode==='Bella'?'chat':'cheerio/answer',mode==='Bella'?{text:content,model:state.selected_model,speak:voiceReply}:{text:content,model:state.selected_model,mode});
      const next=[...currentMessages,userMessage,{role:'assistant',content:answer.answer} as Message];
      setMessages(next);
      const title=currentChatId?chats.find(c=>c.id===currentChatId)?.title||content.slice(0,42):content.slice(0,42);
      const saved=await api<{id:string}>('chats/save',{id:currentChatId,title,messages:next});
      setActiveChatId(saved.id);
      setChats(previous=>{const rest=previous.filter(c=>c.id!==saved.id);return [{id:saved.id,title,messages:next,pinned:previous.find(c=>c.id===saved.id)?.pinned},...rest]});
    }catch(e){setNotice(e instanceof Error?e.message:String(e));setText(content);setMessages(currentMessages);setVoiceTranscript(false);}
    finally{setBusy(false)}
    requestAnimationFrame(()=>chatRef.current?.scrollTo({top:chatRef.current.scrollHeight,behavior:'smooth'}));
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); submit(); }
  }



  function startNewChat() {
    setMessages([]);
    setActiveChatId(null);
    setText("");
    setNotice("");
    setBellaTyping(false);
    setVoiceTranscript(false);
    setTaskComposer(false);
    setSelectedTask("");
    inputRef.current?.focus();
  }

  function openChat(chat: Chat) {
    setActiveChatId(chat.id);
    setMessages(chat.messages);
    setVoiceTranscript(false);
    setBellaTyping(false);
    setTaskComposer(false);
    setSelectedTask("");
    setNotice("");
    setSidebarOpen(false);
  }

  async function deleteChat(id: string) {
    try{await api('chats/delete',{id});setChats(previous=>previous.filter(chat=>chat.id!==id));if(activeChatId===id)startNewChat();}
    catch(e){setNotice(String(e))}
  }

  async function togglePin(id: string) {
    const chat=chats.find(c=>c.id===id);if(!chat)return;
    try{await api('chats/pin',{id,pinned:!chat.pinned});setChats(previous=>previous.map(c=>c.id===id?{...c,pinned:!c.pinned}:c));}
    catch(e){setNotice(String(e))}
  }

  function startRename(chat: Chat) {
    setRenamingId(chat.id);
    setRenameText(chat.title);
  }

  async function commitRename() {
    const title=renameText.trim(),id=renamingId;setRenamingId(null);if(!id||!title)return;
    try{await api('chats/rename',{id,title});setChats(previous=>previous.map(c=>c.id===id?{...c,title}:c));}
    catch(e){setNotice(String(e))}
  }

  function exportChat(chat: Chat) {
    const lines = [
      `${chat.title}`,
      `Exported ${new Date().toLocaleString()}`,
      "",
      ...chat.messages.map(m => `${m.role === "user" ? "You" : "Assistant"}: ${m.content}`),
    ];
    const blob = new Blob([lines.join("\n\n")], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${chat.title.replace(/[^a-z0-9]+/gi, "-").replace(/^-+|-+$/g, "").toLowerCase() || "chat"}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function askAboutSavedChats(event?:FormEvent){
    event?.preventDefault();const query=askText.trim().toLowerCase();
    if(!query)return;
    const matches=chats.flatMap(c=>c.messages.filter(m=>m.content.toLowerCase().includes(query)).map(m=>`${c.title}: ${m.content}`));
    setAskAnswer(matches.length?matches.slice(0,5).join('\n\n'):'No matching local messages. AI search is disabled in this private build.');
  }
  async function microphone(){if(busy && !recording)return;setBusy(true);
    try{if(!recording){await api('mic/start');setRecording(true)}
      else{setRecording(false);const result=await api<{text:string}>('mic/stop');setText(result.text);setVoiceTranscript(true);setNotice('Review the transcript, then click Send. Voice never approves tasks.');inputRef.current?.focus()}}
    catch(e){setNotice(String(e));setRecording(false)}finally{setBusy(false)}
  }
  async function rejectTask(id:string){try{await api('task/reject',{id});await refresh();setNotice('Task rejected. Nothing ran.')}catch(e){setNotice(String(e))}}
  async function approve(){if(!confirm)return;const id=confirm.id;setConfirm(null);setBusy(true);
    try{await api<{result:string}>('task/approve',{id});setNotice('Cheerio returned a local-model answer. No external action was done.');}
    catch(e){setNotice(String(e))}finally{await refresh();setBusy(false)}
  }
  async function selectModel(model:string){try{setState(await api<State>('model/select',{model}));}catch(e){setNotice(String(e))}}

  const query = filterText.trim().toLowerCase();
  const sortedChats = [...chats]
    .filter(chat => !query || chat.title.toLowerCase().includes(query) || chat.messages.some(m => m.content.toLowerCase().includes(query)))
    .sort((a, b) => Number(!!b.pinned) - Number(!!a.pinned));

  // Global shortcuts: ⌘/Ctrl+Shift+O starts a new chat, "/" focuses the composer.
  useEffect(() => {
    function onShortcut(event: globalThis.KeyboardEvent) {
      const mod = event.metaKey || event.ctrlKey;
      const target = event.target as HTMLElement | null;
      const typing = !!target && (target.tagName === "TEXTAREA" || target.tagName === "INPUT" || target.isContentEditable);
      if (mod && event.shiftKey && event.key.toLowerCase() === "o") {
        event.preventDefault();
        startNewChat();
      } else if (event.key === "/" && !mod && !typing) {
        event.preventDefault();
        inputRef.current?.focus();
      }
    }
    window.addEventListener("keydown", onShortcut);
    return () => window.removeEventListener("keydown", onShortcut);
  }, []);

  return <div className={`grok-app ${dark ? "dark" : ""}`}>
    <header className="grok-header">
      <div className="grok-header-left">
        <Button variant="ghost" size="icon" className="mobile-menu" title="Chat history" aria-label="Chat history" aria-expanded={sidebarOpen} onClick={() => setSidebarOpen(!sidebarOpen)}><Menu /></Button>
        <Button variant="ghost" size="icon" className="mark-button" title={newChatTitle} aria-label={newChatTitle} onClick={startNewChat}><BellaMark className="grok-mark" /></Button>
      </div>
      <nav className={`grok-nav ${menuOpen ? "is-open" : ""}`} aria-label="Main navigation">
        <Button type="button" variant="ghost" className={`bella-button ${mode === "Bella" ? "is-active" : ""}`} aria-pressed={mode === "Bella"} title="Bella" onClick={() => { setMode("Bella"); setTaskComposer(false); setMenuOpen(false); }}>Bella {mode === "Bella" && <Check size={15}/>}</Button>

        <div className="settings-wrap">
          <Button variant="ghost" size="icon" aria-label="Settings" title="Settings" onClick={() => setSettingsOpen(!settingsOpen)}><Settings2 size={18} /></Button>
          {settingsOpen && <div className="settings-menu"><span className="menu-heading">Appearance</span><Button variant="ghost" onClick={() => { setDark(false); setSettingsOpen(false); }}><Sun size={16}/> Light {!dark && <Check size={15} className="check"/>}</Button><Button variant="ghost" onClick={() => { setDark(true); setSettingsOpen(false); }}><Moon size={16}/> Dark {dark && <Check size={15} className="check"/>}</Button><span className="menu-heading">{state.status}</span><span className="menu-heading">Local Ollama model</span><select aria-label="Local model" value={state.selected_model} onChange={e=>void selectModel(e.target.value)}><option value="">Choose installed model</option>{state.models.map(m=><option key={m} value={m}>{m}</option>)}</select><Button variant="ghost" onClick={()=>void refresh()}>Find installed models</Button><label className="voice-toggle"><input type="checkbox" checked={voiceReply} onChange={e=>setVoiceReply(e.target.checked)}/> Speak Bella replies locally</label></div>}
        </div>
      </nav>
    </header>

    <div className="grok-body">
    <aside className={`chat-sidebar ${sidebarOpen ? "is-open" : ""}`} aria-label="Chat history">
      <div className="sidebar-top">
        <span className="menu-heading">Chats</span>
        <Button variant="ghost" size="icon" title={newChatTitle} aria-label={newChatTitle} onClick={startNewChat}><SquarePen size={16} /></Button>
      </div>
      <div className="sidebar-filter">
        <Search size={14} />
        <input value={filterText} aria-label="Filter chats" placeholder="Search chats…" onChange={event => setFilterText(event.target.value)} />
        {filterText && <Button variant="ghost" size="icon" aria-label="Clear search" onClick={() => setFilterText("")}><X size={13} /></Button>}
      </div>
      <div className="sidebar-list">
        {chats.length === 0 && <p className="sidebar-empty">No previous chats yet. Start a conversation and it will appear here.</p>}
        {chats.length > 0 && sortedChats.length === 0 && <p className="sidebar-empty">No chats match “{filterText.trim()}”.</p>}
        {sortedChats.map(chat => (
          <div key={chat.id} className={`sidebar-chat ${chat.id === activeChatId ? "is-active" : ""} ${chat.pinned ? "is-pinned" : ""}`}>
            {renamingId === chat.id ? (
              <form className="sidebar-chat-rename" onSubmit={event => { event.preventDefault(); commitRename(); }}>
                <input autoFocus value={renameText} aria-label="Rename chat" onChange={event => setRenameText(event.target.value)} onKeyDown={event => { if (event.key === "Escape") setRenamingId(null); }} onBlur={commitRename} />
              </form>
            ) : (
              <button type="button" className="sidebar-chat-open" onClick={() => openChat(chat)} title={chat.title}>
                {chat.pinned ? <Pin size={14} className="pin-icon" /> : <MessageSquare size={14} />}
                <span>{chat.title}</span>
              </button>
            )}
            <div className="sidebar-chat-actions">
              <Button variant="ghost" size="icon" className="sidebar-chat-action" aria-label={`Export ${chat.title}`} title="Export as text file" onClick={() => exportChat(chat)}><Download size={13} /></Button>
              <Button variant="ghost" size="icon" className="sidebar-chat-action" aria-label={`Rename ${chat.title}`} title="Rename" onClick={() => startRename(chat)}><Pencil size={13} /></Button>
              <Button variant="ghost" size="icon" className="sidebar-chat-action" aria-label={chat.pinned ? `Unpin ${chat.title}` : `Pin ${chat.title}`} title={chat.pinned ? "Unpin" : "Pin to top"} onClick={() => togglePin(chat.id)}>{chat.pinned ? <PinOff size={13} /> : <Pin size={13} />}</Button>
              <Button variant="ghost" size="icon" className="sidebar-chat-action" aria-label={`Delete ${chat.title}`} title="Delete" onClick={() => deleteChat(chat.id)}><Trash2 size={13} /></Button>
            </div>
          </div>
        ))}
      </div>
      {state.tasks.length > 0 && <div className="sidebar-tasks"><span className="menu-heading">Cheerio tasks · model only</span>{state.tasks.map(t=><button type="button" key={t.id} className={selectedTask===t.id ? "is-active" : ""} onClick={()=>{setSelectedTask(t.id);setSidebarOpen(false)}}><small>{t.state.toUpperCase()} · {t.id}</small><span>{t.goal}</span></button>)}</div>}
      <form className="sidebar-ask" onSubmit={askAboutSavedChats}>
        <span className="menu-heading">Search chat messages locally</span>
        <div className="sidebar-ask-row">
          <input value={askText} aria-label="Ask a question about your saved chats" placeholder="Ask about your chats…" onChange={event => setAskText(event.target.value)} />
          <Button type="submit" variant="ghost" size="icon" aria-label="Search local chats" title="Search local chats" disabled={!askText.trim()}><Search size={15} /></Button>
        </div>
        {askAnswer && <p className="sidebar-ask-answer">{askAnswer}</p>}
      </form>
    </aside>
    {sidebarOpen && <button type="button" className="sidebar-scrim" aria-label="Close chat history" onClick={() => setSidebarOpen(false)} />}
    <main id="grok-content-area" className={`grok-main ${messages.length || selectedTask ? "has-messages" : ""}`}>
      {messages.length || selectedTask ? <div className="conversation" ref={chatRef} aria-live="polite">{messages.map((message, i) => <div className={`message message-${message.role}`} key={i}>{message.role === "assistant" && <BellaMark className="message-mark" />}<div>{message.content}</div></div>)}{state.tasks.filter(t=>t.id===selectedTask).map(t=><div key={t.id} className="inline-task"><small>{t.state.toUpperCase()} · {t.id}</small><p>{t.goal}</p>{t.result && <div className="inline-result">{t.result}</div>}{t.state==='pending' && <div className="inline-actions"><button type="button" disabled={busy||!state.handoff_available} onClick={()=>setConfirm(t)}>Review and approve</button><button type="button" disabled={busy} onClick={()=>void rejectTask(t.id)}>Reject</button></div>}</div>)}</div> : <h1>{mode === "Bella" ? "Bella is with you" : "What should we explore?"}</h1>}
      {mode === "Bella" && !messages.length && !selectedTask && !taskComposer ? <div className="bella-arrival" aria-label="Bella companion avatar"><div className="bella-arrival-face"/><div className="bella-arrival-caption">Bella is here · {recording ? "listening" : busy ? "thinking" : "ready to talk"}</div><Button type="button" variant="outline" onClick={()=>void microphone()} disabled={busy}><Mic size={17}/>{recording ? "Stop and review" : "Talk to Bella"}</Button><Button type="button" variant="ghost" onClick={()=>{setBellaTyping(true);requestAnimationFrame(()=>inputRef.current?.focus())}}>Type to Bella</Button><Button type="button" variant="ghost" onClick={()=>setMode("Fast")}>Ask Cheerio directly</Button><div className="bella-arrival-hint">Voice is transcribed for review. It never approves a task.</div></div> : null}
      {mode === "Bella" && voiceTranscript && !recording && text && <div className="bella-transcript">Review transcript before sending</div>}
      {(mode !== "Bella" || taskComposer || (mode === "Bella" && (bellaTyping || !!text))) && <form className="composer" onSubmit={submit}>
        <textarea ref={inputRef} aria-label="Ask anything" title="Press / to focus, Enter to send, Shift+Enter for a new line" value={text} rows={2} placeholder={taskComposer ? "Propose a model-only Cheerio task..." : mode === "Bella" ? "Talk to Bella..." : "Ask Cheerio..."} onChange={event => {setText(event.target.value);setVoiceTranscript(false)}} onKeyDown={onKeyDown} />
        <div className="composer-bottom">
          <Button type="button" variant="ghost" size="icon" className="add-button" aria-label={taskComposer ? "Cancel task proposal" : "Propose a Cheerio task"} title="Propose a model-only task" onClick={() => {setTaskComposer(v=>!v);setText('');setBellaTyping(true);requestAnimationFrame(()=>inputRef.current?.focus())}}>{taskComposer ? <X size={19}/> : <Plus size={19}/>}</Button>
          <div className="composer-actions"><div className="mode-wrap"><Button type="button" variant="ghost" className="mode-button" aria-expanded={modeOpen} onClick={() => setModeOpen(!modeOpen)}>{mode}<ChevronDown size={14}/></Button>{modeOpen && <div className="mode-menu"><Button type="button" variant="ghost" onClick={() => { setMode("Fast"); setModeOpen(false); setTaskComposer(false); }}>Fast {mode === "Fast" && <Check size={14}/>}</Button><Button type="button" variant="ghost" onClick={() => { setMode("Think"); setModeOpen(false); setTaskComposer(false); }}>Think {mode === "Think" && <Check size={14}/>}</Button></div>}</div><Button type="button" variant="ghost" size="icon" aria-label={recording ? "Stop microphone" : "Start microphone"} title="Voice text is staged for review" onClick={()=>void microphone()} disabled={busy}><Mic size={18}/></Button><Button type="submit" size="icon" className="send-button" aria-label="Send message" title="Send message" disabled={!text.trim() || busy}><ArrowUp size={18} strokeWidth={2.2}/></Button></div>
        </div>
      </form>}
    </main>
    </div>

    {confirm&&<div className="work-confirm" role="dialog" aria-modal="true" aria-label="Approve task"><div><h2>Approve this exact task?</h2><p>Cheerio will answer with a local model only. No browsing, code, files, messaging or payments.</p><pre>{confirm.id}\n\n{confirm.goal}</pre><div className="work-row"><button onClick={()=>setConfirm(null)}>Cancel</button><button onClick={()=>void approve()}>Approve once</button></div></div></div>}
    {notice && <div className="notice" role="status"><span>{notice}</span><Button variant="ghost" size="icon" aria-label="Dismiss" onClick={() => setNotice("")}><X size={16}/></Button></div>}
  </div>;
}
