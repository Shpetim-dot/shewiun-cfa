const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const state = { projects: [], brain: [], agents: [], councils: [], activity: [] };
let selectedAgentId="local-planner";
let brainView="graph";
const ICONS={compass:'<circle cx="12" cy="12" r="9"/><path d="m16 8-3 6-5 2 2-5 6-3Z"/>',shield:'<path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11Z"/><path d="m9 12 2 2 4-4"/>',wrench:'<path d="M14 7a5 5 0 0 0-6 6l-5 5 3 3 5-5a5 5 0 0 0 6-6l-4 4-3-3 4-4Z"/>',workflow:'<rect x="3" y="3" width="6" height="6" rx="1"/><rect x="15" y="15" width="6" height="6" rx="1"/><path d="M6 9v3a3 3 0 0 0 3 3h6M15 6h3a3 3 0 0 1 3 3v6"/>',book:'<path d="M12 7v14"/><path d="M3 18V5a2 2 0 0 1 2-2h2a5 5 0 0 1 5 5 5 5 0 0 1 5-5h2a2 2 0 0 1 2 2v13h-4a5 5 0 0 0-5 3 5 5 0 0 0-5-3H3Z"/>',chart:'<path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-5 5"/>',search:'<circle cx="11" cy="11" r="7"/><path d="m16 16 4 4"/>',bot:'<rect x="4" y="8" width="16" height="12" rx="3"/><path d="M12 4v4M9 13h.01M15 13h.01M9 17h6"/>',plus:'<path d="M12 5v14M5 12h14"/>',trash:'<path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6M10 10v6M14 10v6"/>',network:'<circle cx="5" cy="6" r="2"/><circle cx="18" cy="5" r="2"/><circle cx="12" cy="18" r="2"/><path d="m7 6 9-1M6 8l5 8M14 18h3M18 7v8"/>',grid:'<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>'};
function icon(name,size=18){name=name==="shield-check"?"shield":name==="book-open"?"book":name==="chart-no-axes-combined"?"chart":name;return '<svg viewBox="0 0 24 24" width="'+size+'" height="'+size+'" aria-hidden="true" focusable="false">'+(ICONS[name]||ICONS.bot)+'</svg>';}

const esc = (v) => String(v ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const date = v => { try { return new Intl.DateTimeFormat(undefined,{month:"short",day:"numeric",hour:"2-digit",minute:"2-digit"}).format(new Date(v)); } catch { return ""; } };
const toast = (msg) => { const el=$("#toast"); el.textContent=msg; el.classList.add("show"); setTimeout(()=>el.classList.remove("show"),2600); };
async function api(path, options={}) { const r=await fetch(path,{headers:{"Content-Type":"application/json",...(options.headers||{})},...options}); if(!r.ok){let message="Request failed";try{message=(await r.json()).detail||message}catch{}throw new Error(message)} return r.json(); }
function projectMarkup(p){return `<div class="project-row"><div class="project-symbol">▦</div><div class="project-copy"><b>${esc(p.name)}</b><small>${esc(p.description||"No description yet")}</small></div><span class="badge">${esc(p.status)}</span></div>`}
function activityMarkup(a){return `<div class="activity-row"><div class="activity-mark" aria-hidden="true">•</div><div class="activity-copy"><b>${esc(a.action)}</b><p>${esc(a.detail)}</p><time>${date(a.created_at)}</time></div></div>`}
function brainMarkup(b){return `<article class="brain-card"><div class="brain-card-head"><span class="kind-tag ${esc(b.kind.toLowerCase())}">${esc(b.kind)}</span><span class="confidence"><span class="confidence-track"><span style="width:${b.confidence}%"></span></span><b>${b.confidence}%</b></span></div><h3>${esc(b.title)}</h3><p>${esc(b.content)}</p><div class="brain-meta"><span>↳ ${esc(b.source)}</span><time>${date(b.created_at)}</time></div></article>`}
function agentMarkup(a){return `<article class="agent-card"><div class="agent-symbol ${esc(a.color)}">${icon(a.icon||"bot")}</div>${a.custom?`<button type="button" class="agent-delete" data-delete-agent="${esc(a.id)}" aria-label="Delete ${esc(a.name)}" title="Delete agent">${icon("trash",15)}</button>`:""}<h3>${esc(a.name)}</h3><p>${esc(a.role)}</p><div class="agent-provider">Provider · ${esc(a.provider)}</div><div class="agent-status"><span></span>${esc(a.status)}</div></article>`}
function messageMarkup(m){const synthesis=m.role==="Synthesizer";return `<article class="message-card ${synthesis?"synthesis":""}"><div class="message-top"><span class="message-avatar">${m.role==="Strategist"?"S":m.role==="Skeptic"?"R":m.role==="Builder"?"B":"C"}</span><b>${esc(m.role)}${synthesis?" · Final synthesis":""}</b><small>${synthesis?"CONCLUSION":"PERSPECTIVE"}</small></div><p>${esc(m.content)}</p></article>`}
async function refresh(){try{const [projects,brain,agents,councils,activity,health]=await Promise.all([api("/api/projects"),api("/api/brain"),api("/api/agents"),api("/api/council"),api("/api/activity"),api("/api/health")]);Object.assign(state,{projects,brain,agents,councils,activity});$("#api-status").textContent="API connected · v"+health.version;$("#mode-label").textContent=health.model_configured?(health.model_name||"Model configured"):"Free-tier model supported";document.documentElement.dataset.modelConfigured=health.model_configured?"true":"false";$("#health-title").textContent=health.model_configured?(health.model_provider||"Model configured"):"Gemini setup needed";$("#system-status").dataset.state=health.model_configured?"ready":"missing";$("#composer-status").textContent=health.model_configured?((health.model_provider||"Model")+" · "+(health.model_name||"configured")+(health.storage_persistent?"":" · storage is temporary")):"Free Local Planner ready · add GEMINI_API_KEY for model-backed agents";$("#model-setup").hidden=!!health.model_configured;const readinessTitle=$("#security-readiness-title"),readinessCopy=$("#security-readiness-copy");if(readinessTitle)readinessTitle.textContent=health.production_ready?"Production checks passed":"Production readiness: blockers remain";if(readinessCopy)readinessCopy.textContent=(health.readiness_blockers||[]).length?(health.readiness_blockers.join(" · ")):"No reported blockers. This status is not a security certification.";render();await refreshApprovals();await refreshReviewAdmin();}catch(e){$("#api-status").textContent="API unavailable";$("#health-title").textContent="Runtime unavailable";$("#mode-label").textContent="Health check failed";$("#system-status").dataset.state="missing";$("#composer-status").textContent="Runtime unavailable · retry later";toast(e.message)}}
function renderAgentDock(){
 const host=$("#agent-dock-list");if(!host)return;
 if(!state.agents.length){host.textContent="No agents available.";return;}
 if(!state.agents.some(a=>a.id===selectedAgentId))selectedAgentId=state.agents.some(a=>a.id==="local-planner")?"local-planner":state.agents[0].id;
 host.innerHTML=state.agents.map(a=>'<button type="button" class="agent-dock-chip" data-select-agent="'+esc(a.id)+'" aria-pressed="'+(a.id===selectedAgentId)+'">'+icon(a.icon||"bot",15)+'<span>'+esc(a.name)+'</span>'+(a.id==="local-planner"?'<small>FREE</small>':'')+'</button>').join("");
 host.querySelectorAll("[data-select-agent]").forEach(b=>b.addEventListener("click",()=>{selectedAgentId=b.dataset.selectAgent;renderAgentDock();const a=state.agents.find(x=>x.id===selectedAgentId);if(a)$("#composer-status").textContent=a.id==="local-planner"?"Free local planner · no API key needed":a.provider;}));
}
function renderCouncilRoles(){
 const host=$("#council-role-list");if(!host)return;
 const roles=state.agents.filter(a=>a.name!=="Synthesizer");
 host.innerHTML=roles.map(a=>'<label class="role-option"><input type="checkbox" name="council-role" value="'+esc(a.name)+'" '+(["Strategist","Skeptic","Builder"].includes(a.name)?"checked":"")+'><span class="role-avatar">'+icon(a.icon||"bot",16)+'</span><span><b>'+esc(a.name)+'</b><small>'+esc(a.role)+'</small></span><i></i></label>').join("")||'<p class="no-results">Create an agent to start a Council.</p>';
}
function renderBrainGraph(){
 const host=$("#brain-graph");if(!host)return;
 const entries=filteredBrain(),count=$("#brain-graph-count");if(count)count.textContent=entries.length+" nodes";
 if(!entries.length){host.innerHTML='<div class="brain-graph-empty"><b>No matching notes</b><p>Add knowledge or change the search to explore your notes.</p></div>';return;}
 const width=900,height=340,cx=450,cy=170,n=entries.length;
 const points=entries.map((entry,i)=>{const angle=i*2.399963+.3;const radius=n===1?0:Math.min(138,28+Math.sqrt(i+1)*38);return{x:cx+Math.cos(angle)*radius,y:cy+Math.sin(angle)*radius*.78,entry,index:i};});
 const openLink=String.fromCharCode(91,91),closeLink=String.fromCharCode(93,93),byTitle=new Map(points.map(p=>[p.entry.title.trim().toLowerCase(),p])),edges=[];points.forEach(p=>String(p.entry.content||"").split(openLink).slice(1).forEach(part=>{const target=byTitle.get(part.split(closeLink)[0].trim().toLowerCase());if(target&&target.index!==p.index)edges.push('<line class="brain-edge" x1="'+p.x+'" y1="'+p.y+'" x2="'+target.x+'" y2="'+target.y+'"/>');}));
 const nodes=points.map(p=>{const title=p.entry.title.length>19?p.entry.title.slice(0,18)+"…":p.entry.title;return '<g class="brain-node" tabindex="0" data-brain-node="'+esc(p.entry.id)+'"><circle cx="'+p.x+'" cy="'+p.y+'" r="29"/><text x="'+p.x+'" y="'+(p.y-1)+'" text-anchor="middle">'+esc(title)+'</text><text class="node-kind" x="'+p.x+'" y="'+(p.y+12)+'" text-anchor="middle">'+esc(p.entry.kind||"Note")+'</text></g>';}).join("");
 host.innerHTML='<svg viewBox="0 0 '+width+' '+height+'" preserveAspectRatio="xMidYMid meet">'+edges.join("")+nodes+'</svg>';
 host.querySelectorAll("[data-brain-node]").forEach(node=>{const open=()=>{const entry=entries.find(x=>x.id===node.dataset.brainNode);if(entry){brainView="entries";updateBrainView();$("#brain-search").value=entry.title;$("#brain-list").innerHTML=filteredBrain().map(brainMarkup).join("");}};node.addEventListener("click",open);node.addEventListener("keydown",e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();open();}});});
}
function updateBrainView(){const graph=$("#brain-graph-panel"),list=$("#brain-list");if(graph)graph.hidden=brainView!=="graph";if(list)list.hidden=brainView!=="entries";document.querySelectorAll("[data-brain-view]").forEach(b=>{const active=b.dataset.brainView===brainView;b.classList.toggle("active",active);b.setAttribute("aria-selected",String(active));});}
function render(){ renderAgentDock();renderCouncilRoles();renderBrainGraph();$("#stat-projects").textContent=state.projects.length;$("#stat-brain").textContent=state.brain.length;$("#stat-agents").textContent=state.agents.length;$("#stat-councils").textContent=state.councils.length;$("#project-list").innerHTML=state.projects.slice(0,4).map(projectMarkup).join("")||'<div class="no-results">No projects yet.</div>';$("#control-project-list").innerHTML=state.projects.map(projectMarkup).join("")||'<div class="no-results">No projects yet.</div>';$("#activity-list").innerHTML=state.activity.slice(0,5).map(activityMarkup).join("")||'<div class="no-results">No activity yet.</div>';$("#security-activity").innerHTML=state.activity.map(activityMarkup).join("")||'<div class="no-results">No activity yet.</div>';$("#brain-count").textContent=state.brain.length+" ENTRIES";$("#brain-list").innerHTML=filteredBrain().map(brainMarkup).join("")||'<div class="no-results">No matching knowledge entries.</div>';$("#agent-grid").innerHTML=state.agents.map(agentMarkup).join("");document.querySelectorAll("[data-delete-agent]").forEach(b=>b.addEventListener("click",async e=>{e.stopPropagation();if(!window.confirm("Delete this custom agent?"))return;b.disabled=true;try{await api("/api/agents/"+encodeURIComponent(b.dataset.deleteAgent),{method:"DELETE"});if(selectedAgentId===b.dataset.deleteAgent)selectedAgentId="local-planner";await refresh();toast("Agent deleted");}catch(err){toast(err.message);b.disabled=false;}}));$("#control-count").textContent=String(state.agents.length).padStart(2,"0");renderHistory();}
function filteredBrain(){const q=$("#brain-search").value.toLowerCase(),kind=$("#brain-filter").value;return state.brain.filter(b=>(kind==="All"||b.kind===kind)&&[b.title,b.content,b.source].join(" ").toLowerCase().includes(q))}
function renderHistory(){const host=$("#council-history");host.innerHTML=state.councils.map(c=>`<div class="history-row"><span class="round-icon">◎</span><div><b>${esc(c.topic)}</b><p>${esc(c.result)}</p></div><time>${date(c.created_at)}</time><button class="text-button" data-open-council="${esc(c.id)}">Open ↗</button></div>`).join("")||'<div class="no-results">No meetings yet. Start the first Council.</div>';$$("[data-open-council]").forEach(b=>b.addEventListener("click",()=>{const c=state.councils.find(x=>x.id===b.dataset.openCouncil);if(c)showCouncil(c)}));}
function showCouncil(c){$("#transcript-title").textContent=c.topic;$("#transcript-subtitle").textContent="Saved session · "+date(c.created_at);$("#session-mode").textContent=c.mode==="live"?"LIVE MODEL":"DEMO MODE";$("#transcript").classList.remove("empty-state");$("#transcript").innerHTML=(c.transcript||[]).map(messageMarkup).join("");}
function switchView(view){$$(".view").forEach(v=>v.classList.toggle("active",v.id==="view-"+view));$$(".nav-item").forEach(b=>b.classList.toggle("active",b.dataset.view===view));const names={overview:"New task",council:"Council",brain:"Brain",control:"Control",security:"Security"};const title=$("#task-title");if(title)title.textContent=names[view]||view;window.scrollTo({top:0,behavior:"smooth"});}
$$("[data-view]").forEach(b=>b.addEventListener("click",()=>switchView(b.dataset.view)));$$("[data-go]").forEach(b=>b.addEventListener("click",()=>switchView(b.dataset.go)));
$("#add-project").addEventListener("click",()=>$("#project-dialog").showModal());$("#control-add-project").addEventListener("click",()=>$("#project-dialog").showModal());
$("#project-form").addEventListener("submit",async e=>{if(e.submitter?.value==="cancel")return;e.preventDefault();try{await api("/api/projects",{method:"POST",body:JSON.stringify({name:$("#project-name").value,description:$("#project-description").value})});$("#project-dialog").close();$("#project-form").reset();await refresh();toast("Project created");}catch(err){toast(err.message)}});
$("#add-agent")?.addEventListener("click",()=>{const form=$("#agent-form");form?.reset();$("#agent-form-error").hidden=true;$("#agent-dialog").showModal();$("#agent-name").focus();});
$("#agent-form")?.addEventListener("submit",async e=>{if(e.submitter?.value==="cancel")return;e.preventDefault();const btn=$("#save-agent"),error=$("#agent-form-error");btn.disabled=true;error.hidden=true;try{const agent=await api("/api/agents",{method:"POST",body:JSON.stringify({name:$("#agent-name").value,role:$("#agent-role").value,instructions:$("#agent-instructions").value,icon:$("#agent-icon").value})});$("#agent-dialog").close();$("#agent-form").reset();selectedAgentId=agent.id;await refresh();toast("Agent created");}catch(err){error.textContent=err.message;error.hidden=false;}finally{btn.disabled=false;}});
$("#add-knowledge").addEventListener("click",()=>$("#brain-dialog").showModal());$("#knowledge-confidence").addEventListener("input",e=>$("#confidence-value").textContent=e.target.value);
$("#brain-form").addEventListener("submit",async e=>{if(e.submitter?.value==="cancel")return;e.preventDefault();try{await api("/api/brain",{method:"POST",body:JSON.stringify({title:$("#knowledge-title").value,content:$("#knowledge-content").value,kind:$("#knowledge-kind").value,source:$("#knowledge-source").value,confidence:Number($("#knowledge-confidence").value)})});$("#brain-dialog").close();$("#brain-form").reset();$("#knowledge-confidence").value=80;$("#confidence-value").textContent="80";$("#knowledge-source").value="User input";await refresh();toast("Knowledge saved");}catch(err){toast(err.message)}});
$("#brain-search").addEventListener("input",()=>{$("#brain-list").innerHTML=filteredBrain().map(brainMarkup).join("")||'<div class="no-results">No matching knowledge entries.</div>';renderBrainGraph();});$("#brain-filter").addEventListener("change",()=>{$("#brain-list").innerHTML=filteredBrain().map(brainMarkup).join("")||'<div class="no-results">No matching knowledge entries.</div>';renderBrainGraph();});document.querySelectorAll("[data-brain-view]").forEach(b=>b.addEventListener("click",()=>{brainView=b.dataset.brainView;updateBrainView();renderBrainGraph();}));
$("#start-council").addEventListener("click",async()=>{const topic=$("#council-topic").value.trim();if(topic.length<3){toast("Enter a discussion topic first");$("#council-topic").focus();return}const roles=$$('input[name="council-role"]:checked').map(x=>x.value);const btn=$("#start-council");btn.disabled=true;btn.textContent="Council is discussing…";$("#transcript").classList.add("empty-state");$("#transcript").innerHTML='<h3>Perspectives are coming together.</h3><p>Waiting for the council to finish.</p>';try{const c=await api("/api/council",{method:"POST",body:JSON.stringify({topic,roles,rounds:1})});showCouncil(c);await refresh();showCouncil(c);toast("Council meeting completed");}catch(err){toast(err.message);$("#transcript").classList.add("empty-state")}finally{btn.disabled=false;btn.innerHTML='Start Council Meeting <span aria-hidden="true">→</span>'}});


async function refreshApprovals(){
 try{
  const approvals=await api("/api/security/approvals");
  const host=$("#approval-list"); if(!host)return;
  host.innerHTML=approvals.map(a=>`<div class="approval-row"><div class="approval-main"><b>${esc(a.action_type)}</b><p>${esc(a.description)}</p><small>Requested by ${esc(a.requested_by)} · ${esc(a.risk_level)} risk · ${date(a.created_at)}</small></div><span class="approval-state ${esc(a.status)}">${esc(a.status)}</span>${a.status==="pending"?`<div class="approval-buttons"><button class="btn secondary" data-decision="rejected" data-id="${esc(a.id)}">Reject</button><button class="btn primary" data-decision="approved" data-id="${esc(a.id)}">Approve</button></div>`:""}</div>`).join("")||'<div class="no-results">No approval requests yet.</div>';
  $$("[data-decision]").forEach(b=>b.addEventListener("click",async()=>{b.disabled=true;try{await api("/api/security/approvals/"+b.dataset.id+"/decision",{method:"POST",body:JSON.stringify({decision:b.dataset.decision,decided_by:"workspace-owner",note:"Reviewed in CFA Security"})});await refreshApprovals();await refresh();toast("Approval decision recorded");}catch(e){toast(e.message);b.disabled=false}}));
 }catch(e){const host=$("#approval-list");if(host)host.innerHTML='<div class="no-results">Could not load approval queue.</div>';}
}
async function refreshReviewAdmin(){
 const analyticsHost=$("#review-analytics"),requestsHost=$("#review-requests");if(!analyticsHost||!requestsHost)return;
 try{
  const [summary,requests]=await Promise.all([api("/api/review/agent-launch/admin/analytics?days=30"),api("/api/review/agent-launch/admin/requests?limit=30")]);
  const events=summary.events||{};
  analyticsHost.innerHTML='<div class="review-metric-grid"><div><b>'+esc(summary.submissions||0)+'</b><span>Submissions</span></div><div><b>'+esc(summary.leads||0)+'</b><span>Unlocked memos</span></div><div><b>'+esc(summary.authorization_test_requests||0)+'</b><span>Test requests</span></div><div><b>'+esc(events.pdf_downloaded||0)+'</b><span>PDF prints</span></div></div>';
  requestsHost.innerHTML='<h4>Authorization Test requests</h4>'+(requests.length?requests.map(item=>{const q=item.request||{};return '<article class="review-request-row"><div><b>'+esc(q.name||"Unnamed contact")+' · '+esc(q.company||"No company")+'</b><p>'+esc(q.email||"")+' · '+esc(q.role||"")+'</p><p>'+esc(q.use_case||"")+'</p><small>'+esc(item.created_at||"")+' · ID '+esc(item.id||"")+'</small></div></article>'}).join(""):'<p class="no-results">No requests have been submitted.</p>');
 }catch(e){analyticsHost.innerHTML='<p class="no-results">Review analytics unavailable. Configure PostgreSQL and sign in with an authorized workspace account.</p>';requestsHost.innerHTML="";}
}
$("#refresh-approvals")?.addEventListener("click",refreshApprovals);
$("#refresh-review-admin")?.addEventListener("click",refreshReviewAdmin);
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
workspaceForm?.addEventListener("submit",async event=>{
 event.preventDefault();const topic=workspacePrompt.value.trim();
 if(topic.length<3){toast("Add a little more detail before starting.");workspacePrompt.focus();return;}
 const send=$("#workspace-send"),agent=state.agents.find(a=>a.id===selectedAgentId)||state.agents.find(a=>a.id==="local-planner");
 send.disabled=true;setMascotMode("working");send.textContent="Working…";
 workspaceResponse.hidden=false;
 workspaceResponse.innerHTML='<div class="workspace-response-head"><span class="response-agent-dot is-animated"><i></i><i></i></span><b>Preparing '+esc(agent?.name||"agent")+'</b><small>WORKING</small></div><p class="workspace-user-prompt"></p><div class="workspace-answer">Reviewing your task and relevant Brain notes…</div>';
 workspaceResponse.querySelector(".workspace-user-prompt").textContent=topic;
 try{
  const result=await api("/api/agents/run",{method:"POST",body:JSON.stringify({topic,agent_id:agent?.id||"local-planner"})});
  workspaceResponse.innerHTML='<div class="workspace-response-head"><span class="response-agent-dot"><i></i><i></i></span><b>'+esc(result.agent?.name||"CFA Agent")+'</b><small>'+esc(result.mode_label||"Free local rules")+'</small></div><p class="workspace-user-prompt"></p><div class="workspace-answer">'+esc(result.result)+'</div><div class="response-actions"><span class="response-mode"><span class="mode-dot"></span>'+esc(result.mode_label||"Free local rules")+'</span><button type="button" class="btn secondary" id="save-agent-result">Save to Brain</button></div>';
  workspaceResponse.querySelector(".workspace-user-prompt").textContent=topic;
  $("#save-agent-result").addEventListener("click",async()=>{const save=$("#save-agent-result");save.disabled=true;try{await api("/api/brain",{method:"POST",body:JSON.stringify({title:topic.slice(0,140),content:result.result,kind:"Decision",source:"Agent run · "+(result.agent?.name||"CFA Agent"),confidence:65})});await refresh();save.textContent="Saved to Brain";toast("Result saved to Brain");}catch(error){save.disabled=false;toast(error.message);}});
  workspacePrompt.value="";setMascotMode("idle");await refresh();toast("Agent result ready");
 }catch(error){
  workspaceResponse.innerHTML='<div class="workspace-response-head"><span class="response-agent-dot"><i></i><i></i></span><b>Could not start task</b></div><p class="response-error"></p>';
  workspaceResponse.querySelector(".response-error").textContent=error.message||"Unexpected error. Try again.";setMascotMode("idle");
 }finally{send.disabled=false;send.innerHTML='Run selected agent <span aria-hidden="true">→</span>';if(!workspacePrompt.value.trim())setMascotMode("idle");}
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
  if(action==="brain")switchView("brain");
  if(action==="control")switchView("control");
  if(action==="security")switchView("security");
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
const authGate=$("#auth-gate"), appShell=$("#app-shell"), authForm=$("#auth-form"), authError=$("#auth-error"), authSetup=$("#auth-setup"), authPassword=$("#auth-password"), authLogout=$("#auth-logout");
function showAuthGate(message, setup=false){
  authGate.hidden=false; appShell.hidden=true; authSetup.hidden=!setup;
  authForm.hidden=setup; $("#auth-description").textContent=setup?"Workspace access is locked until the server-side credentials are configured.":(message||"Your workspace is protected. Sign in to continue.");
  if(setup) $("#auth-title").textContent="Workspace setup required";
  else {$("#auth-title").textContent="Sign in to your workspace";authPassword.focus();}
}
function showWorkspace(){
  authGate.hidden=true;appShell.hidden=false;authLogout.hidden=!window.__cfaAuthRequired;refresh();
}
async function bootstrapAuth(){
  try{
    const status=await api("/api/auth/status");
    window.__cfaAuthRequired=!!status.required;
    if(status.required&&!status.configured){showAuthGate(status.setup_message,true);return;}
    if(status.required&&!status.authenticated){showAuthGate();return;}
    showWorkspace();
  }catch(e){showAuthGate("Could not verify access configuration. Reload and try again.");}
}
authForm?.addEventListener("submit",async e=>{
  e.preventDefault();const btn=$("#auth-submit");btn.disabled=true;authError.hidden=true;
  try{await api("/api/auth/login",{method:"POST",body:JSON.stringify({password:authPassword.value})});authPassword.value="";showWorkspace();}
  catch(err){authError.textContent=err.message;authError.hidden=false;}
  finally{btn.disabled=false;}
});
authLogout?.addEventListener("click",async()=>{
  try{await api("/api/auth/logout",{method:"POST"});}catch{}
  showAuthGate("You have signed out.");
});
bootstrapAuth();
})();
