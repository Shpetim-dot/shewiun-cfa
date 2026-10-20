const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const state = { projects: [], brain: [], agents: [], councils: [], activity: [] };
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const date = v => { try { return new Intl.DateTimeFormat(undefined,{month:"short",day:"numeric",hour:"2-digit",minute:"2-digit"}).format(new Date(v)); } catch { return ""; } };
const toast = (msg) => { const el=$("#toast"); el.textContent=msg; el.classList.add("show"); setTimeout(()=>el.classList.remove("show"),2600); };
async function api(path, options={}) { const r=await fetch(path,{headers:{"Content-Type":"application/json",...(options.headers||{})},...options}); if(!r.ok){let message="Request failed";try{message=(await r.json()).detail||message}catch{}throw new Error(message)} return r.json(); }
function projectMarkup(p){return `<div class="project-row"><div class="project-symbol">▦</div><div class="project-copy"><b>${esc(p.name)}</b><small>${esc(p.description||"No description yet")}</small></div><span class="badge">${esc(p.status)}</span></div>`}
function activityMarkup(a){return `<div class="activity-row"><div class="activity-mark" aria-hidden="true">•</div><div class="activity-copy"><b>${esc(a.action)}</b><p>${esc(a.detail)}</p><time>${date(a.created_at)}</time></div></div>`}
function brainMarkup(b){return `<article class="brain-card"><div class="brain-card-head"><span class="kind-tag ${esc(b.kind.toLowerCase())}">${esc(b.kind)}</span><span class="confidence"><span class="confidence-track"><span style="width:${b.confidence}%"></span></span><b>${b.confidence}%</b></span></div><h3>${esc(b.title)}</h3><p>${esc(b.content)}</p><div class="brain-meta"><span>↳ ${esc(b.source)}</span><time>${date(b.created_at)}</time></div></article>`}
function agentMarkup(a){const sym={Strategist:"↗",Skeptic:"⚑",Builder:"⌘",Synthesizer:"✳"};return `<article class="agent-card"><div class="agent-symbol ${esc(a.color)}">${sym[a.name]||"◎"}</div><h3>${esc(a.name)}</h3><p>${esc(a.role)}</p><div class="agent-provider">Provider · ${esc(a.provider)}</div><div class="agent-status"><span></span>${esc(a.status)}</div></article>`}
function messageMarkup(m){const synthesis=m.role==="Synthesizer";return `<article class="message-card ${synthesis?"synthesis":""}"><div class="message-top"><span class="message-avatar">${m.role==="Strategist"?"↗":m.role==="Skeptic"?"⚑":m.role==="Builder"?"⌘":"✳"}</span><b>${esc(m.role)}${synthesis?" · Final synthesis":""}</b><small>${synthesis?"CONCLUSION":"PERSPECTIVE"}</small></div><p>${esc(m.content)}</p></article>`}
async function refresh(){try{const [projects,brain,agents,councils,activity,health]=await Promise.all([api("/api/projects"),api("/api/brain"),api("/api/agents"),api("/api/council"),api("/api/activity"),api("/api/health")]);Object.assign(state,{projects,brain,agents,councils,activity});$("#api-status").textContent="API connected · v"+health.version;$("#mode-label").textContent=health.model_configured?(health.model_name||"Model configured"):"Free-tier model supported";document.documentElement.dataset.modelConfigured=health.model_configured?"true":"false";$("#health-title").textContent=health.model_configured?(health.model_provider||"Model configured"):"Gemini setup needed";$("#system-status").dataset.state=health.model_configured?"ready":"missing";$("#composer-status").textContent=health.model_configured?((health.model_provider||"Model")+" · "+(health.model_name||"configured")+(health.storage_persistent?"":" · storage is temporary")):"Gemini Flash available · add a server-side GEMINI_API_KEY to enable AI";render();await refreshApprovals();}catch(e){$("#api-status").textContent="API unavailable";$("#health-title").textContent="Runtime unavailable";$("#mode-label").textContent="Health check failed";$("#system-status").dataset.state="missing";$("#composer-status").textContent="Runtime unavailable · retry later";toast(e.message)}}
function render(){ $("#stat-projects").textContent=state.projects.length;$("#stat-brain").textContent=state.brain.length;$("#stat-agents").textContent=state.agents.length;$("#stat-councils").textContent=state.councils.length;$("#project-list").innerHTML=state.projects.slice(0,4).map(projectMarkup).join("")||'<div class="no-results">No projects yet.</div>';$("#control-project-list").innerHTML=state.projects.map(projectMarkup).join("")||'<div class="no-results">No projects yet.</div>';$("#activity-list").innerHTML=state.activity.slice(0,5).map(activityMarkup).join("")||'<div class="no-results">No activity yet.</div>';$("#security-activity").innerHTML=state.activity.map(activityMarkup).join("")||'<div class="no-results">No activity yet.</div>';$("#brain-count").textContent=state.brain.length+" ENTRIES";$("#brain-list").innerHTML=filteredBrain().map(brainMarkup).join("")||'<div class="no-results">No matching knowledge entries.</div>';$("#agent-grid").innerHTML=state.agents.map(agentMarkup).join("");$("#control-count").textContent=String(state.agents.length).padStart(2,"0");renderHistory();}
function filteredBrain(){const q=$("#brain-search").value.toLowerCase(),kind=$("#brain-filter").value;return state.brain.filter(b=>(kind==="All"||b.kind===kind)&&[b.title,b.content,b.source].join(" ").toLowerCase().includes(q))}
function renderHistory(){const host=$("#council-history");host.innerHTML=state.councils.map(c=>`<div class="history-row"><span class="round-icon">◎</span><div><b>${esc(c.topic)}</b><p>${esc(c.result)}</p></div><time>${date(c.created_at)}</time><button class="text-button" data-open-council="${esc(c.id)}">Open ↗</button></div>`).join("")||'<div class="no-results">No meetings yet. Start the first Council.</div>';$$("[data-open-council]").forEach(b=>b.addEventListener("click",()=>{const c=state.councils.find(x=>x.id===b.dataset.openCouncil);if(c)showCouncil(c)}));}
function showCouncil(c){$("#transcript-title").textContent=c.topic;$("#transcript-subtitle").textContent="Saved session · "+date(c.created_at);$("#session-mode").textContent=c.mode==="live"?"LIVE MODEL":"DEMO MODE";$("#transcript").classList.remove("empty-state");$("#transcript").innerHTML=(c.transcript||[]).map(messageMarkup).join("");}
function switchView(view){$(".view").forEach(v=>v.classList.toggle("active",v.id==="view-"+view));$(".nav-item").forEach(b=>b.classList.toggle("active",b.dataset.view===view));const names={overview:"New task",council:"Council",brain:"Brain",control:"Control",security:"Security"};const title=$("#task-title");if(title)title.textContent=names[view]||view;window.scrollTo({top:0,behavior:"smooth"});}
$("[data-view]").forEach(b=>b.addEventListener("click",()=>switchView(b.dataset.view)));$("[data-go]").forEach(b=>b.addEventListener("click",()=>switchView(b.dataset.go)));
$("#add-project").addEventListener("click",()=>$("#project-dialog").showModal());$("#control-add-project").addEventListener("click",()=>$("#project-dialog").showModal());
$("#project-form").addEventListener("submit",async e=>{if(e.submitter?.value==="cancel")return;e.preventDefault();try{await api("/api/projects",{method:"POST",body:JSON.stringify({name:$("#project-name").value,description:$("#project-description").value})});$("#project-dialog").close();$("#project-form").reset();await refresh();toast("Project created");}catch(err){toast(err.message)}});
$("#add-knowledge").addEventListener("click",()=>$("#brain-dialog").showModal());$("#knowledge-confidence").addEventListener("input",e=>$("#confidence-value").textContent=e.target.value);
$("#brain-form").addEventListener("submit",async e=>{if(e.submitter?.value==="cancel")return;e.preventDefault();try{await api("/api/brain",{method:"POST",body:JSON.stringify({title:$("#knowledge-title").value,content:$("#knowledge-content").value,kind:$("#knowledge-kind").value,source:$("#knowledge-source").value,confidence:Number($("#knowledge-confidence").value)})});$("#brain-dialog").close();$("#brain-form").reset();$("#knowledge-confidence").value=80;$("#confidence-value").textContent="80";$("#knowledge-source").value="User input";await refresh();toast("Knowledge saved");}catch(err){toast(err.message)}});
$("#brain-search").addEventListener("input",()=>{$("#brain-list").innerHTML=filteredBrain().map(brainMarkup).join("")||'<div class="no-results">No matching knowledge entries.</div>'});$("#brain-filter").addEventListener("change",()=>{$("#brain-list").innerHTML=filteredBrain().map(brainMarkup).join("")||'<div class="no-results">No matching knowledge entries.</div>'});
$("#start-council").addEventListener("click",async()=>{const topic=$("#council-topic").value.trim();if(topic.length<3){toast("Enter a discussion topic first");$("#council-topic").focus();return}const roles=$$('input[type=checkbox][value]:checked').map(x=>x.value);const btn=$("#start-council");btn.disabled=true;btn.textContent="Council is discussing…";$("#transcript").classList.add("empty-state");$("#transcript").innerHTML='<div class="empty-symbol">◎</div><h3>Perspectives are coming together.</h3><p>Waiting for the council to finish.</p>';try{const c=await api("/api/council",{method:"POST",body:JSON.stringify({topic,roles,rounds:1})});showCouncil(c);await refresh();showCouncil(c);toast(c.mode==="live"?"Council meeting completed":"Council completed in demo mode");}catch(err){toast(err.message);$("#transcript").classList.add("empty-state")}finally{btn.disabled=false;btn.innerHTML='✳ Start Council Meeting <span>→</span>'}});

refresh();

async function refreshApprovals(){
 try{
  const approvals=await api("/api/security/approvals");
  const host=$("#approval-list"); if(!host)return;
  host.innerHTML=approvals.map(a=>`<div class="approval-row"><div class="approval-main"><b>${esc(a.action_type)}</b><p>${esc(a.description)}</p><small>Requested by ${esc(a.requested_by)} · ${esc(a.risk_level)} risk · ${date(a.created_at)}</small></div><span class="approval-state ${esc(a.status)}">${esc(a.status)}</span>${a.status==="pending"?`<div class="approval-buttons"><button class="btn secondary" data-decision="rejected" data-id="${esc(a.id)}">Reject</button><button class="btn primary" data-decision="approved" data-id="${esc(a.id)}">Approve</button></div>`:""}</div>`).join("")||'<div class="no-results">No approval requests yet.</div>';
  $$("[data-decision]").forEach(b=>b.addEventListener("click",async()=>{b.disabled=true;try{await api("/api/security/approvals/"+b.dataset.id+"/decision",{method:"POST",body:JSON.stringify({decision:b.dataset.decision,decided_by:"workspace-owner",note:"Reviewed in CFA Security"})});await refreshApprovals();await refresh();toast("Approval decision recorded");}catch(e){toast(e.message);b.disabled=false}}));
 }catch(e){const host=$("#approval-list");if(host)host.innerHTML='<div class="no-results">Could not load approval queue.</div>';}
}
$("#refresh-approvals")?.addEventListener("click",refreshApprovals);
$("#verify-audit")?.addEventListener("click",async()=>{try{const result=await api("/api/security/audit/verify");$("#audit-integrity").textContent=result.valid?"Integrity valid · "+result.checked+" events checked":"Integrity check failed at event "+result.failed_event_id;$("#audit-integrity").className="integrity-line "+(result.valid?"valid":"invalid");}catch(e){toast(e.message)}});


// Workspace task composer and minimal blue CFA mascot.
const workspaceForm = $("#workspace-form");
const workspacePrompt = $("#workspace-prompt");
const workspaceResponse = $("#workspace-response");
const workspaceMascot = $("#workspace-mascot");
function setMascotMode(mode) {
  if (!workspaceMascot) return;
  workspaceMascot.classList.toggle("is-looking", mode === "looking" || mode === "working");
  workspaceMascot.classList.toggle("is-working", mode === "working");
}
workspacePrompt?.addEventListener("input", () => {
  setMascotMode(workspacePrompt.value.trim() ? "looking" : "idle");
});
workspacePrompt?.addEventListener("focus", () => {
  if (workspacePrompt.value.trim()) setMascotMode("looking");
});
workspacePrompt?.addEventListener("blur", () => {
  if (!workspacePrompt.value.trim()) setMascotMode("idle");
});
$("#sidebar-new-task")?.addEventListener("click", () => {
  switchView("overview");
  workspacePrompt?.focus();
  workspacePrompt?.scrollIntoView({behavior:"smooth",block:"center"});
});
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
function renderRuntimeProgress(topic, run) {
  const transcript = run?.state?.transcript || [];
  const status = run?.status || "queued";
  setMascotMode(["queued","running"].includes(status) ? "working" : "idle");
  workspaceResponse.hidden = false;
  workspaceResponse.innerHTML =
    '<div class="workspace-response-head"><b>CFA Council</b><small>State: ' + esc(status) + '</small></div>' +
    '<p class="workspace-user-prompt"></p>' +
    '<div class="runtime-status" role="status" aria-live="polite">' +
    esc(status === "completed" ? "Decision ready" : status === "failed" ? "Run failed" : "Council is working on the task") +
    '</div>' +
    transcript.map((message,index) => '<details class="workspace-answer" ' + (["completed","failed","cancelled"].includes(status) ? "" : "open") + '><summary><b>' +
      esc(message.role) + '</b></summary><p>' + esc(message.content) + '</p></details>').join("") +
    (status === "failed" ? '<p class="response-error"></p>' : "");
  workspaceResponse.querySelector(".workspace-user-prompt").textContent = topic;
  if (status === "failed") workspaceResponse.querySelector(".response-error").textContent = run.error || "The run failed. Retry after checking runtime configuration.";
}
workspaceForm?.addEventListener("submit", async event => {
  event.preventDefault();
  const topic = workspacePrompt.value.trim();
  if (topic.length < 3) {
    toast("Add a little more detail before starting.");
    workspacePrompt.focus();
    return;
  }
  if (document.documentElement.dataset.modelConfigured !== "true") {
    workspaceResponse.hidden = false;
    workspaceResponse.innerHTML = '<div class="no-model-banner"><b>Enable the free-tier agent</b><p>Shewiun supports Google Gemini Flash. Add GEMINI_API_KEY as a server-side Vercel environment variable to enable model-backed Council runs. The key is never requested in this page or exposed to the browser.</p><p>Until configured, no model result will be fabricated.</p></div>';
    workspaceResponse.scrollIntoView({behavior:"smooth",block:"nearest"});
    return;
  }
  const send = $("#workspace-send");
  send.disabled = true;
  setMascotMode("working");
  send.innerHTML = 'Working <span class="button-spinner" aria-hidden="true"></span>';
  workspaceResponse.hidden = false;
  workspaceResponse.innerHTML = '<div class="workspace-response-head"><span class="response-agent-dot is-animated" aria-hidden="true"><i></i><i></i></span><b>CFA Council</b><small>PREPARING</small></div><p class="workspace-user-prompt"></p><div class="workspace-answer"><p>Setting up the task and preparing the Council perspectives…</p></div>';
  workspaceResponse.querySelector(".workspace-user-prompt").textContent = topic;
  workspaceResponse.scrollIntoView({behavior:"smooth",block:"nearest"});
  try {
    const created = await api("/api/runtime/runs", {
      method: "POST",
      body: JSON.stringify({topic, roles:["Strategist","Skeptic","Builder"], rounds:1})
    });
    let run = null;
    const deadline = Date.now() + 120000;
    while (Date.now() < deadline) {
      run = await api("/api/runtime/runs/" + encodeURIComponent(created.id));
      renderRuntimeProgress(topic, run);
      if (["completed", "failed", "cancelled"].includes(run.status)) break;
      await wait(900);
    }
    if (!run || !["completed", "failed", "cancelled"].includes(run.status)) {
      workspaceResponse.innerHTML += '<p class="response-error">This task is still running. Check CFA Council for its status shortly.</p>';
      toast("Task continues in the background");
      return;
    }
    if (run.status === "completed") {
      workspacePrompt.value = "";
      setMascotMode("idle");
      await refresh();
      toast("Recommendation ready");
    } else if (run.status === "cancelled") {
      toast("Task cancelled");
    } else {
      toast("Task failed");
    }
  } catch (error) {
    setMascotMode("idle");
    workspaceResponse.innerHTML = '<div class="workspace-response-head"><span class="response-agent-dot" aria-hidden="true"><i></i><i></i></span><b>Could not start task</b></div><p class="response-error"></p>';
    workspaceResponse.querySelector(".response-error").textContent = error.message || "Unexpected error. Try again.";
  } finally {
    send.disabled = false;
    send.innerHTML = 'Start Council <span aria-hidden="true">→</span>';
    if (!workspacePrompt.value.trim()) setMascotMode("idle");
  }
});
workspacePrompt?.addEventListener("keydown", event => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    workspaceForm.requestSubmit();
  }
});



// Phase 1 shell interactions: command palette, keyboard navigation, theme and truthful runtime status.
(() => {
 const root=document.documentElement, shell=document.querySelector(".app-shell"), palette=$("#command-palette"), query=$("#palette-query");
 const storedTheme=localStorage.getItem("shewiun-theme");
 if(storedTheme==="dark"||storedTheme==="light")root.dataset.theme=storedTheme;
 const setTheme=()=>{const next=root.dataset.theme==="dark"?"light":"dark";root.dataset.theme=next;localStorage.setItem("shewiun-theme",next);};
 $("#theme-toggle")?.addEventListener("click",setTheme);
 const openPalette=()=>{if(!palette)return;palette.showModal();query.value="";filterPalette("");query.focus();};
 $("#open-command-palette")?.addEventListener("click",openPalette);
 $("#open-command-palette-top")?.addEventListener("click",openPalette);
 $("#top-menu")?.addEventListener("click",openPalette);
 function filterPalette(value){const q=value.toLowerCase();$$(".palette-items button").forEach(b=>b.hidden=!b.textContent.toLowerCase().includes(q));}
 query?.addEventListener("input",e=>filterPalette(e.target.value));
 $$(".palette-items button").forEach(b=>b.addEventListener("click",()=>{
  const action=b.dataset.action;palette.close();
  if(action==="new-task"){switchView("overview");$("#workspace-prompt")?.focus();}
  if(action==="council")switchView("council");
  if(action==="theme")setTheme();
  if(action==="export")$("#export-current")?.click();
 }));
 $("#sidebar-new-task")?.addEventListener("click",()=>{switchView("overview");$("#workspace-prompt")?.focus();});
 document.addEventListener("keydown",e=>{
  const mod=e.metaKey||e.ctrlKey;
  if(mod&&e.key.toLowerCase()==="k"){e.preventDefault();openPalette();}
  if(mod&&e.key.toLowerCase()==="b"){e.preventDefault();shell?.classList.toggle("sidebar-collapsed");}
  if(mod&&e.shiftKey&&e.key.toLowerCase()==="o"){e.preventDefault();switchView("overview");$("#workspace-prompt")?.focus();}
  if(e.key==="Escape"&&palette?.open)palette.close();
 });
 $$(".example-prompts [data-prompt]").forEach(b=>b.addEventListener("click",()=>{switchView("overview");const input=$("#workspace-prompt");input.value=b.dataset.prompt;input.focus();input.dispatchEvent(new Event("input",{bubbles:true}));}));
 $("#export-current")?.addEventListener("click",()=>{
  const host=$("#workspace-response");if(!host||host.hidden||!host.textContent.trim()){toast("There is no result to export yet.");return;}
  const blob=new Blob([host.innerText],{type:"text/markdown;charset=utf-8"}),url=URL.createObjectURL(blob),a=document.createElement("a");
  a.href=url;a.download="shewiun-decision.md";a.click();URL.revokeObjectURL(url);
 });
 const prompt=$("#workspace-prompt");
 prompt?.addEventListener("input",()=>{prompt.style.height="auto";prompt.style.height=Math.min(prompt.scrollHeight,240)+"px";});
})();
