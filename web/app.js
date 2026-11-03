// Memory Duel page. Plain JS + SVG; all data comes from the local API.
const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const fmt = n => n >= 1000 ? (n/1000).toFixed(n >= 10000 ? 0 : 1) + 'k' : String(Math.round(n));
const usd = n => n == null ? '–' : n < 0.01 ? '$' + n.toFixed(4) : n < 1 ? '$' + n.toFixed(3) : '$' + n.toFixed(2);

const state = {
  step: 'basics', slide: 0, sess: 11, cp: 20, W: 3, q: 'city',
  status: {}, hist: null, res: null, shown: null, job: null, anim: null, animT: null, confirm: null,
};
let ORDER = ['full','window','summary','facts','rag','notes'];
let INFO = {};

const OUT = {
  right:{c:'#7ee39a', l:'Right'}, partly:{c:'#ffd95e', l:'Partly'}, stored:{c:'#ff8a8a', l:'Still stored'},
  stale:{c:'#ffb347', l:'Stale'}, missed:{c:'#8fb09c', l:'Missed'}, invented:{c:'#c4b0ff', l:'Invented'},
  wrong:{c:'#ff6b6b', l:'Wrong'}, leaked:{c:'#ff4d4d', l:'Leaked'},
};
const OUT_ORDER = ['right','partly','stored','stale','missed','invented','wrong','leaked'];
const SCORE = {right:1, partly:.5, stored:.5};
const ST = {
  current:{c:'#7ee39a', l:'Current'}, stale:{c:'#ffb347', l:'Stale'}, partial:{c:'#ffd95e', l:'Partial'},
  conflict:{c:'#ffd95e', l:'Conflicting', hatch:true}, missing:{c:null, l:'Missing'}, leak:{c:'#ff6b6b', l:'Should be forgotten'},
  gone:{c:null, l:'Forgotten as asked'}, na:{c:null, l:'Not true yet'},
};
const TYPE_LABEL = {recall:'Recall', update:'Update', time_order:'Time order', combining:'Combining facts', forgetting:'Forgetting', false_memory:'False memory'};

async function api(path, opts) {
  const r = await fetch(path, opts);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || `Request failed (${r.status})`);
  return j;
}
const post = (path, body) => api(path, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body||{})});

const tip = $('#tip');
function showTip(e, html){ tip.innerHTML = html; tip.hidden = false; const x = Math.min(e.clientX+14, innerWidth - tip.offsetWidth - 8); tip.style.left = x+'px'; tip.style.top = (e.clientY+14)+'px'; }
function hideTip(){ tip.hidden = true; }
function bindTips(el){
  el.addEventListener('mousemove', e => { const g = e.target.closest('[data-tip]'); if (g) { const [a,b] = g.dataset.tip.split('|'); showTip(e, `<div class="t">${a}</div>${b??''}`); } else hideTip(); });
  el.addEventListener('mouseleave', hideTip);
}

// ================= data helpers =================
const H = () => state.hist;
const N = () => H().sessions.length;
const CPS = () => H().checkpoints.map(c => c.after);
const qsAt = cp => (H().checkpoints.find(c => c.after === cp) || {questions:[]}).questions;
const factLabel = k => (H().facts.find(f => f.key === k) || {}).label || k;
function entry(cid){
  const R = state.res; if (!R || !R.contestants) return null;
  if (cid === 'window' && R.window_variants && R.window_variants[state.W]) return R.window_variants[state.W];
  return R.contestants[cid] || null;
}
const shown = () => ORDER.filter(c => state.shown.has(c));
const color = cid => (INFO[cid] || {}).color || '#93b4a0';
const cname = cid => (INFO[cid] || {}).name || cid;
function answerOf(cid, cp, qid){ const e = entry(cid); const c = e && e.checkpoints[String(cp)]; return c ? c.answers.find(a => a.id === qid) : null; }
function scoreOf(cid, cp){ const qs = qsAt(cp); let s = 0, n = 0; qs.forEach(q => { const a = answerOf(cid, cp, q.id); if (a && a.grade) { s += SCORE[a.grade] || 0; n++; } }); return n ? s/n : null; }
function truthAt(key, t){ const f = H().facts.find(x => x.key === key); let v; let known = false; for (const [s,val] of f.truth) if (s <= t) { v = val; known = true; } return known ? v : undefined; }

function keywords(q){
  const words = new Set();
  const add = s => String(s||'').toLowerCase().match(/[a-záéíóúñ0-9:]+/g)?.forEach(w => { if (w.length > 3 && !STOP.has(w)) words.add(w); });
  if (q.key) { const f = H().facts.find(x => x.key === q.key); f.truth.forEach(([,v]) => add(v)); Object.values(f.mentions||{}).forEach(add); }
  add(q.question);
  if (q.type === 'false_memory') { words.add('cat'); words.add('dog'); words.add('dogs'); }
  if (q.type === 'forgetting') { ['forget','address','elm'].forEach(w => words.add(w)); }
  return [...words];
}
const STOP = new Set('what when where which with your have about does more than used that this from they them their there were been into make like just only last now did how who whom whose'.split(' '));
function mark(text, words){
  let h = esc(text);
  if (!words.length) return h;
  const re = new RegExp('\\b(' + words.map(w => w.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')).join('|') + ')\\w*', 'gi');
  return h.replace(re, m => `<mark>${m}</mark>`);
}

// ================= logo =================
function drawLogo(){
  const svg = $('#logo'), W = 48;
  const ctx = document.createElement('canvas').getContext('2d');
  const m = t => { ctx.font = "700 100px 'Oswald', 'Arial Narrow', sans-serif"; const r = ctx.measureText(t); return {w:r.width, cap:r.actualBoundingBoxAscent||72}; };
  const sw = Math.max(1, W/30), pad = W*0.13, inner = W-2*pad, m1 = m('MEMORY'), m2 = m('DUEL');
  const fs1 = 100*inner/m1.w, fs2 = 100*inner/m2.w, c1 = m1.cap*fs1/100, c2 = m2.cap*fs2/100, gap = W*0.07;
  const y1 = (W-(c1+gap+c2))/2+c1, y2 = y1+gap+c2;
  svg.setAttribute('viewBox', `0 0 ${W} ${W}`);
  svg.innerHTML = `<defs><linearGradient id="mdEdge" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#6ff0a8"/><stop offset="1" stop-color="#ffa266"/></linearGradient></defs>
    <rect x="${sw/2}" y="${sw/2}" width="${W-sw}" height="${W-sw}" rx="${W*0.12}" fill="#08160f" stroke="url(#mdEdge)" stroke-width="${sw}"/>
    <text x="${pad}" y="${y1}" style="font-family:Oswald,'Arial Narrow',sans-serif;font-weight:700;font-size:${fs1}px" fill="#e8f3ec">MEMORY</text>
    <text x="${pad}" y="${y2}" style="font-family:Oswald,'Arial Narrow',sans-serif;font-weight:700;font-size:${fs2}px" fill="#e8f3ec">DUEL</text>`;
}

// ================= BASICS =================
const T = (x,y,s,o={}) => `<text x="${x}" y="${y}" font-size="${o.fs||13}" fill="${o.fill||'#e8f3ec'}" ${o.anchor?`text-anchor="${o.anchor}"`:''} ${o.mono?'font-family="JetBrains Mono, monospace"':''} ${o.w?`font-weight="${o.w}"`:''}>${s}</text>`;
const R = (x,y,w,h,o={}) => `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${o.rx??8}" fill="${o.fill||'#0e2118'}" stroke="${o.stroke||'#2a5139'}" stroke-width="${o.sw||1}" ${o.dash?`stroke-dasharray="${o.dash}"`:''} ${o.op!=null?`opacity="${o.op}"`:''}/>`;

const SLIDES = [
 {h:'The context window is the only working memory',
  p:["A language model remembers nothing between calls. Each answer is written from one block of text, the context window: instructions, whatever memory the app chose to include, and the conversation so far.",
     "So every “memory system” is really a decision about what to put back into that window, and what to leave out."],
  art:()=>{
    let s=R(170,20,250,250,{fill:'#08160f',stroke:'#ffa266',sw:2,rx:14})+T(295,46,'CONTEXT WINDOW',{anchor:'middle',fs:11,mono:true,fill:'#ffa266'});
    const rows=[['Instructions','#5e7e6a'],['Memory: facts about Nell','#7cc8ff'],['Memory: a past chat','#6ff0a8'],['Earlier in this chat','#93b4a0'],['Earlier in this chat','#93b4a0'],['Nell: “Where do I live?”','#ffa266']];
    rows.forEach(([l,c],i)=>{ s+=R(186,60+i*32,218,24,{fill:'#0e2118',stroke:c,rx:6})+T(196,76+i*32,l,{fs:12}); });
    s+=`<path d="M420 145 H470" stroke="#93b4a0" stroke-width="1.5" marker-end="url(#ar)"/>`+R(474,120,92,50,{fill:'#12291e',rx:10})+T(520,150,'Model',{anchor:'middle',w:700});
    s+=T(40,90,'Memory store',{fs:12,fill:'#93b4a0'})+R(30,100,110,100,{fill:'#0e2118',dash:'4 4'})+T(85,145,'chats, facts,',{anchor:'middle',fs:11,fill:'#93b4a0'})+T(85,162,'notes…',{anchor:'middle',fs:11,fill:'#93b4a0'});
    s+=`<path d="M140 150 H180" stroke="#93b4a0" stroke-width="1.5" stroke-dasharray="3 3" marker-end="url(#ar)"/>`+T(40,225,'Only what is copied in',{fs:11,fill:'#5e7e6a'})+T(40,240,'can be used.',{fs:11,fill:'#5e7e6a'});
    return s; }},
 {h:'Long memory costs more, and gets read less carefully',
  p:["The window is re-sent with every turn, so a long history is paid for again and again. Ten turns with 50,000 tokens of history means sending 500,000 tokens.",
     "Bigger windows also get less careful attention. Studies find models use facts at the start and end of a long input better than facts in the middle (“lost in the middle”)."],
  art:()=>{
    let s=T(20,24,'Tokens sent per turn, carrying full history',{fs:12,fill:'#93b4a0'});
    for(let i=0;i<10;i++){ const h=20+i*19; s+=`<rect x="${30+i*30}" y="${250-h}" width="20" height="${h}" rx="3" fill="#6ff0a8" opacity="${.35+i*.065}"/>`; }
    s+=T(30,270,'turn 1',{fs:10,mono:true,fill:'#5e7e6a'})+T(300,270,'turn 10',{fs:10,mono:true,fill:'#5e7e6a',anchor:'end'});
    s+=T(360,24,'How well a fact is used, by position',{fs:12,fill:'#93b4a0'});
    s+=`<path d="M370 90 C 420 210, 520 210, 570 80" fill="none" stroke="#ffa266" stroke-width="3"/>`;
    s+=`<line x1="370" y1="230" x2="570" y2="230" stroke="#2a5139"/>`+T(370,250,'start',{fs:10,mono:true,fill:'#5e7e6a'})+T(470,250,'middle',{fs:10,mono:true,fill:'#5e7e6a',anchor:'middle'})+T(570,250,'end',{fs:10,mono:true,fill:'#5e7e6a',anchor:'end'});
    s+=T(470,180,'dip',{fs:11,anchor:'middle',fill:'#ffa266'});
    return s; }},
 {h:'Three kinds of memory',
  p:["Psychology’s split works well for assistants too. Most systems handle the first two; the third is what makes an assistant feel like it knows you."],
  list:["<b>Episodic:</b> what happened. “Nell moved to Boise in March.”","<b>Semantic:</b> facts that hold now. “Nell lives in Boise.”","<b>Procedural:</b> how the user likes things done. “Nell wants short answers with a checklist.”"],
  art:()=>{
    const cols=[['EPISODIC','#6ff0a8','Mar 24: moved','Mar 31: drives','Apr 7: forget address'],['SEMANTIC','#7cc8ff','home: Boise','job: UX designer','allergy: tree nuts'],['PROCEDURAL','#c4b0ff','short answers','checklists','metric units']];
    let s='';
    cols.forEach(([h,c,...it],i)=>{ const x=20+i*190; s+=R(x,30,170,220,{fill:'#0e2118',stroke:c,rx:12})+T(x+85,58,h,{anchor:'middle',mono:true,fs:11,fill:c});
      it.forEach((t,j)=>{ s+=R(x+14,78+j*52,142,38,{fill:'#08160f',stroke:'#1e3d2d',rx:8})+T(x+85,102+j*52,t,{anchor:'middle',fs:12}); }); });
    return s; }},
 {h:'One message, six kinds of memory',
  p:["Here is what each strategy keeps from one message Nell sends in session 11. These are the six contestants in the duel."],
  art:()=>{
    let s=R(20,10,560,46,{fill:'#163526',stroke:'#2a5139',rx:12})+T(36,38,'Nell: “We moved to Boise this weekend! Sold my bike, it didn’t fit in the truck.”',{fs:12.5});
    const six=[['Full transcript','#6ff0a8','The whole message, word for word,','sent with every future answer.'],
      ['Sliding window','#ff8f5a','The message, until it scrolls','out of the last N sessions.'],
      ['Rolling summary','#ffd95e','“…moved from Denver to Boise','in March; sold her bike.”'],
      ['Fact memory','#7cc8ff','+ Lives in Boise','– Lives in Denver (if it remembers to retire it)'],
      ['RAG over past chats','#f28bb8','Stored in a search index;','found when a question resembles it.'],
      ['Self-editing memory','#c4b0ff','The assistant edits its own notes:','“Home: Boise (moved Mar). No bike.”']];
    six.forEach(([n,c,a,b],i)=>{ const x=20+(i%2)*285, y=70+Math.floor(i/2)*66;
      s+=R(x,y,275,58,{fill:'#0e2118',stroke:c,rx:10})+T(x+12,y+19,n,{fs:12,w:700,fill:c})+T(x+12,y+36,a,{fs:11.5,fill:'#93b4a0'})+T(x+12,y+51,b,{fs:11.5,fill:'#93b4a0'}); });
    return s; }},
 {h:'Write policy: what to save, and when',
  p:["Anything that writes memory has to decide what is worth keeping, when to write it (every turn, end of session, or when asked), and what to do when new information contradicts old.",
     "Contradictions are the hard part. When Nell says she moved, the old city has to be retired, not just joined by the new one."],
  art:()=>{
    let s=T(20,30,'After session 11, a careless write:',{fs:12,fill:'#93b4a0'});
    s+=R(20,42,260,92,{fill:'#08160f',rx:10})+T(36,70,'#3  Lives in Denver',{fs:13,mono:true})+T(36,96,'#14 Moved to Boise in March',{fs:13,mono:true})+T(36,122,'→ Where does Nell live?',{fs:11.5,fill:'#ffd95e'});
    s+=T(320,30,'A careful write:',{fs:12,fill:'#93b4a0'});
    s+=R(320,42,260,92,{fill:'#08160f',rx:10})+`<text x="336" y="70" font-size="13" font-family="JetBrains Mono, monospace" fill="#5e7e6a" text-decoration="line-through">#3  Lives in Denver</text>`+T(336,96,'#14 Lives in Boise (since Mar)',{fs:13,mono:true})+T(336,122,'✓ one current answer',{fs:11.5,fill:'#7ee39a'});
    s+=T(20,175,'Questions every write policy answers',{fs:12,fill:'#93b4a0'});
    ['Is this durable, or just today?','Is it new, an update, or a fix?','Does the user want it kept?'].forEach((q,i)=>{ s+=R(20+i*190,188,180,52,{fill:'#0e2118',rx:10})+T(30+i*190,219,q,{fs:11.5}); });
    return s; }},
 {h:'Updating and forgetting',
  p:["A memory can be wrong in two quiet ways: stale (an old value after an update) and leaky (a deleted fact that is still stored).",
     "When a user says “forget this,” checking the answer is not enough. The fact has to be gone from memory itself, or it can resurface later. Memory Duel checks both."],
  art:()=>{
    let s=T(20,26,'One fact over time',{fs:12,fill:'#93b4a0'});
    s+=`<line x1="30" y1="90" x2="570" y2="90" stroke="#2a5139" stroke-width="2"/>`;
    [[60,'s8','told','#7ee39a'],[250,'s11','moved: now outdated','#ffb347'],[430,'s13','“please forget it”','#ff6b6b']].forEach(([x,ss,l,c])=>{ s+=`<circle cx="${x}" cy="90" r="7" fill="${c}"/>`+T(x,70,ss,{anchor:'middle',mono:true,fs:11,fill:'#93b4a0'})+T(x,116,l,{anchor:'middle',fs:12}); });
    [['CURRENT','#7ee39a','right value,','right time',30],['STALE','#ffb347','was true once,','not anymore',215],['LEAKED','#ff6b6b','asked to forget,','still stored',400]].forEach(([h,c,a,b,x])=>{
      s+=R(x,150,170,90,{fill:'#0e2118',stroke:c,rx:10})+T(x+85,176,h,{anchor:'middle',mono:true,fs:11,fill:c})+T(x+85,202,a,{anchor:'middle',fs:12})+T(x+85,220,b,{anchor:'middle',fs:12}); });
    return s; }},
 {h:'Compression: summaries trade detail for space',
  p:["A rolling summary rewrites the history into a short running note after each session. It stays small, but every rewrite decides again what matters.",
     "Details that looked minor (a 10-minute bike ride) tend to vanish, and you can’t get them back."],
  art:()=>{
    let s='';
    for(let i=0;i<6;i++) s+=R(30+i*8,40+i*6,150,180,{fill:'#0e2118',stroke:'#2a5139',rx:8,op:.5+i*.1});
    s+=T(110,250,'thousands of tokens of chat',{anchor:'middle',fs:12,fill:'#93b4a0'});
    s+=`<path d="M225 80 L330 120 L330 160 L225 200 Z" fill="#ffd95e" opacity=".14" stroke="#ffd95e"/>`+T(277,145,'summarize',{anchor:'middle',fs:11,mono:true,fill:'#ffd95e'});
    s+=R(345,95,230,90,{fill:'#08160f',stroke:'#ffd95e',rx:10})+T(360,122,'Nell moved from Denver',{fs:12.5})+T(360,142,'to Boise in March and',{fs:12.5})+T(360,162,'now drives to work.',{fs:12.5});
    s+=T(460,210,'≈ 25 tokens',{anchor:'middle',fs:12,fill:'#93b4a0'})+T(460,232,'(the bike is gone)',{anchor:'middle',fs:11.5,fill:'#5e7e6a'});
    return s; }},
 {h:'Retrieval: searching your own past',
  p:["RAG over past chats stores old messages in a search index and pulls back the few that look most like the new question. It scales to years of history at a flat cost per answer.",
     "It inherits retrieval’s blind spots: if the question uses different words than the old message, the search can miss it, and it can’t tell which of two mentions is current. (Retrieval Duel covers search in depth.)"],
  art:()=>{
    let s=T(20,26,'Past messages, placed by meaning',{fs:12,fill:'#93b4a0'});
    const pts=[[80,80],[120,150],[160,60],[200,200],[240,120],[90,210],[300,70],[330,180],[260,230],[150,110],[360,120],[60,140]];
    pts.forEach(([x,y],i)=>{ s+=`<circle cx="${x}" cy="${y}" r="6" fill="${[4,7,10].includes(i)?'#f28bb8':'#2a5139'}"/>`; });
    s+=`<circle cx="320" cy="140" r="9" fill="none" stroke="#ffa266" stroke-width="2.5"/>`+T(320,112,'question',{anchor:'middle',fs:11,mono:true,fill:'#ffa266'});
    s+=`<circle cx="320" cy="140" r="58" fill="none" stroke="#f28bb8" stroke-dasharray="4 4"/>`;
    s+=R(420,60,160,160,{fill:'#0e2118',stroke:'#f28bb8',rx:10})+T(500,86,'CLOSEST FOUND',{anchor:'middle',mono:true,fs:11,fill:'#f28bb8'});
    ['s11: moved to Boise','s12: drive 35 min','s14: Boise library'].forEach((t,i)=>{ s+=T(436,118+i*30,t,{fs:12}); });
    return s; }},
 {h:'Memory in the weights',
  p:["You could fine-tune a model on a user’s history so the facts live in its parameters. It’s rarely a good fit for personal memory.",
     "Training is slow and costly, it can’t cleanly update or delete one fact, and it mixes one person’s details into a model. Weights suit skills and style; personal facts belong in a store you can edit."],
  art:()=>{
    let s='';
    for(let i=0;i<9;i++) for(let j=0;j<6;j++){ const x=60+i*36,y=50+j*30; s+=`<circle cx="${x}" cy="${y}" r="5" fill="#2a5139"/>`; if(i<8) s+=`<line x1="${x}" y1="${y}" x2="${x+36}" y2="${50+((j*7+i)%6)*30}" stroke="#1e3d2d"/>`; }
    s+=`<circle cx="204" cy="110" r="7" fill="#ffa266"/>`+T(204,240,'“Lives in Denver” is in here somewhere…',{anchor:'middle',fs:12,fill:'#93b4a0'});
    s+=R(420,60,160,150,{fill:'#0e2118',rx:10})+T(500,90,'To change one fact',{anchor:'middle',fs:12,fill:'#93b4a0'})+T(500,120,'retrain',{anchor:'middle',fs:15,w:700,fill:'#ffa266'})+T(500,150,'To delete one fact',{anchor:'middle',fs:12,fill:'#93b4a0'})+T(500,180,'no clean way',{anchor:'middle',fs:15,w:700,fill:'#ff6b6b'});
    return s; }},
 {h:'Privacy: memory is personal data',
  p:["A memory system is a file about a person. Good ones avoid storing what they shouldn’t (ID numbers, passwords), let the user see and edit what’s kept, and delete for real when asked.",
     "Each strategy makes this easier or harder: a fact list is easy to show and edit; a full transcript, a search index or a summary is not."],
  art:()=>{
    let s='';
    [['SEE','What does it know about me?','#7cc8ff'],['EDIT','Fix a wrong fact','#ffd95e'],['DELETE','Gone from storage, not just hidden','#ff6b6b'],['LIMIT','Never store IDs or passwords','#c4b0ff']].forEach(([h,t,c],i)=>{
      const x=20+(i%2)*285, y=30+Math.floor(i/2)*110;
      s+=R(x,y,275,95,{fill:'#0e2118',stroke:c,rx:12})+T(x+16,y+30,h,{mono:true,fs:12,fill:c})+T(x+16,y+60,t,{fs:13}); });
    return s; }},
 {h:'How memory gets tested',
  p:["Published benchmarks quiz assistants on long multi-session chats. LongMemEval tests extracting facts, reasoning across sessions, time, updated knowledge, and saying “I don’t know.” LoCoMo uses very long conversations across many sessions.",
     "Memory Duel does the same on a scale you can watch: a scripted history, checkpoint quizzes graded by a judge, and a check of what each memory actually holds."],
  art:()=>{
    let s='';
    const types=[['Recall','“What’s my dog’s name?”'],['Update','“Where do I live?”'],['Time order','“What did I do before?”'],['Combining','“Is my commute longer?”'],['Forgetting','“What was my old address?”'],['False memory','“What’s my cat’s name?”']];
    types.forEach(([h,q],i)=>{ const x=20+(i%2)*285, y=20+Math.floor(i/2)*78;
      s+=R(x,y,275,64,{fill:'#0e2118',rx:10})+T(x+14,y+24,h.toUpperCase(),{mono:true,fs:11,fill:'#ffa266'})+T(x+14,y+47,q,{fs:13}); });
    return s; }},
];

function renderSlide(){
  const sl = SLIDES[state.slide];
  $('#slide').innerHTML = `<div class="txt"><div class="eyebrow">Basics · ${state.slide+1} of ${SLIDES.length}</div><h2>${sl.h}</h2>${sl.p.map((p,i)=>`<p class="${i?'m':''}">${p}</p>`).join('')}${sl.list?`<ul>${sl.list.map(l=>`<li>${l}</li>`).join('')}</ul>`:''}</div>
    <div class="art"><svg viewBox="0 0 600 280" role="img" aria-label="${esc(sl.h)}"><defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="#93b4a0"/></marker></defs>${sl.art()}</svg></div>`;
  $('#dots').innerHTML = SLIDES.map((_,i)=>`<button aria-label="Slide ${i+1}" aria-current="${i===state.slide}" data-i="${i}"></button>`).join('');
  $('#prev').disabled = state.slide === 0;
  $('#nextSlide').textContent = state.slide === SLIDES.length-1 ? `Next: meet ${H()?H().user:'the user'} →` : 'Next →';
}
$('#dots').addEventListener('click', e => { const b = e.target.closest('button'); if (b) { state.slide = +b.dataset.i; renderSlide(); } });
$('#prev').onclick = () => { if (state.slide > 0) { state.slide--; renderSlide(); } };
$('#nextSlide').onclick = () => { if (state.slide < SLIDES.length-1) { state.slide++; renderSlide(); } else go('history'); };

// ================= HISTORY =================
function eventsOf(n){
  const evs = [];
  H().facts.forEach(f => f.truth.forEach(([s,v],i) => {
    if (s !== n) return;
    if (v === null) evs.push(['del', `forget: ${f.label.toLowerCase()}`]);
    else if (i === 0) evs.push(['new', `${f.label.toLowerCase()}: ${v}`]);
    else evs.push(['upd', `${f.label.toLowerCase()}: ${v} (was ${f.truth[i-1][1]})`]);
  }));
  return evs;
}
function renderTrack(){
  const W = 1000, n = N(), x = i => 40 + (W-80)*(i-1)/(n-1), toks = H().session_tokens, mx = Math.max(...toks);
  let s = `<line x1="${x(1)}" y1="44" x2="${x(n)}" y2="44" stroke="#2a5139" stroke-width="2"/>`;
  for (let i = 1; i <= n; i++) {
    const on = i === state.sess, ses = H().sessions[i-1], has = eventsOf(i).length;
    const r = 8 + 8*Math.sqrt(toks[i-1]/mx);
    s += `<g class="node" data-s="${i}" tabindex="0" role="button" aria-label="Session ${i}, ${ses.date}: ${esc(ses.topic)}">
      <circle cx="${x(i)}" cy="44" r="${r+5}" fill="transparent"/>
      <circle cx="${x(i)}" cy="44" r="${r}" fill="${on?'#ffa266':has?'#12291e':'#0e2118'}" stroke="${on?'#ffa266':has?'#93b4a0':'#2a5139'}" stroke-width="${on?2:1.5}"/>
      <text x="${x(i)}" y="48" text-anchor="middle" font-size="10.5" font-family="JetBrains Mono, monospace" fill="${on?'#08160f':'#e8f3ec'}">${i}</text>
      <text x="${x(i)}" y="86" text-anchor="middle" font-size="10.5" fill="#5e7e6a">${shortDate(ses.date)}</text></g>`;
    if (CPS().includes(i)) s += `<path d="M${x(i) + (x(2)-x(1))/2} 12 l6 6 l-6 6 l-6 -6 z" fill="#ffa266"/>`;
  }
  $('#track').innerHTML = s;
}
function shortDate(d){ const [y,m,dd] = d.split('-'); return ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][+m-1] + ' ' + (+dd); }
$('#track').addEventListener('click', e => { const g = e.target.closest('.node'); if (g) { state.sess = +g.dataset.s; renderHistory(); } });
$('#track').addEventListener('keydown', e => { const g = e.target.closest('.node'); if (g && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); state.sess = +g.dataset.s; renderHistory(); document.querySelector(`.node[data-s="${state.sess}"]`)?.focus(); } });

function renderSession(){
  const i = state.sess, s = H().sessions[i-1], evs = eventsOf(i);
  const words = [];
  H().facts.forEach(f => { const m = (f.mentions||{})[String(i)]; if (m) String(m).toLowerCase().match(/[a-z0-9:]+/g).forEach(w => { if (w.length > 3) words.push(w); }); });
  $('#sess').innerHTML = `<div class="sess-head"><h3>Session ${i} · ${esc(s.topic)}</h3><span class="meta">${shortDate(s.date)} · ${s.turns.length} messages · ${H().session_tokens[i-1].toLocaleString()} tokens</span></div>
    <div class="evs">${evs.length ? evs.map(([k,t]) => `<span class="ev ${k}">${k==='new'?'+':k==='upd'?'↻':'✕'} ${esc(t)}</span>`).join('') : '<span class="ev">no change to the facts in the answer key</span>'}</div>
    <div class="chat">${s.turns.map(t => `<div class="bub ${t.role}"><span class="who">${t.role==='user'?esc(H().user):'Assistant'}</span>${mark(t.text, words)}</div>`).join('')}</div>`;
}
function renderLog(){
  const W = 560, L = 104, R0 = 12, top = 26, rh = 31, n = N(), x = s => L + (W-L-R0)*(s-1)/n, cw = (W-L-R0)/n;
  let s = '';
  for (let i = 1; i <= n; i++) if (i === 1 || i % 5 === 0) s += `<text x="${x(i)+cw/2}" y="14" text-anchor="middle" font-size="10" font-family="JetBrains Mono, monospace" fill="#5e7e6a">s${i}</text>`;
  H().facts.forEach((f, r) => {
    const y = top + r*rh;
    s += `<text x="0" y="${y+18}" font-size="12" fill="#93b4a0">${esc(f.label)}</text>`;
    s += `<rect x="${L}" y="${y+3}" width="${W-L-R0}" height="${rh-8}" rx="4" fill="#0b1c13"/>`;
    f.truth.forEach(([s0, v], j) => {
      const s1 = (f.truth[j+1]?.[0] ?? n+1);
      if (v === null) { s += `<text x="${x(s0)+4}" y="${y+18}" font-size="11" font-family="JetBrains Mono, monospace" fill="#ff6b6b">✕ forgotten on request</text>`; return; }
      s += `<g data-tip="${esc(f.label)} · sessions ${s0}–${s1-1}|${esc(v)}"><rect x="${x(s0)+1}" y="${y+3}" width="${x(s1)-x(s0)-2}" height="${rh-8}" rx="4" fill="${j%2?'#1d4a33':'#163b29'}" stroke="#2a5139"/>`;
      const room = Math.floor((x(s1)-x(s0)-12)/6.1), lab = v.length > room ? v.slice(0, Math.max(1, room-1)) + '…' : v;
      s += `<text x="${x(s0)+6}" y="${y+18}" font-size="11" fill="#e8f3ec">${esc(lab)}</text></g>`;
    });
  });
  const sx = x(state.sess) + cw/2, bottom = top + H().facts.length*rh;
  s += `<line x1="${sx}" y1="${top-4}" x2="${sx}" y2="${bottom}" stroke="#ffa266" stroke-width="2"/>`;
  s += `<text x="${sx}" y="${bottom+16}" text-anchor="middle" font-size="10.5" font-family="JetBrains Mono, monospace" fill="#ffa266">after s${state.sess}</text>`;
  $('#log').setAttribute('viewBox', `0 0 ${W} ${bottom+24}`);
  $('#log').innerHTML = s;
}
bindTips($('#log'));
function renderHistory(){
  $('#histTitle').textContent = `Meet ${H().user}: ${N()} chats over five months`;
  $('#histLede').textContent = H().description + ` Pick a session to read it. The chart is the answer key: what was true about ${H().user} after each session.`;
  renderTrack(); renderSession(); renderLog();
}

// ================= DUEL =================
function renderRunPanel(){
  const R0 = state.res || {}, st = state.status, live = R0.mode === 'live', btns = [];
  const runningJob = state.job && state.job.status === 'running';
  if (st.public) {
    $('#srcTitle').textContent = 'Hosted demo · saved results';
    $('#srcSub').innerHTML = `${R0.mode === 'scripted' ? 'The answers are scripted to show typical behavior. ' : ''}To run the contestants live with Claude, <a href="${esc(st.repo)}" target="_blank" rel="noopener">run Memory Duel on your computer</a>.`;
  } else if (live) {
    const d = R0.created ? new Date(R0.created).toLocaleString() : '';
    $('#srcTitle').textContent = `Live results · ${d}`;
    $('#srcSub').textContent = `Answers by ${R0.models?.answer || ''}; memory updates and grading by ${R0.models?.work || ''}.`;
  } else {
    $('#srcTitle').textContent = 'Saved demo results (scripted)';
    $('#srcSub').textContent = st.has_key ? 'These answers were scripted from rules to show typical behavior. Run it live to see what Claude actually does.' : 'These answers were scripted from rules to show typical behavior. Add an API key to .env to run it live.';
  }
  if (!st.public && st.has_key && !runningJob) {
    const some = shown().length < ORDER.length ? ` (${shown().length} shown)` : '';
    btns.push(`<button class="btn ${live ? 'ghost' : 'next'} small" id="runAll">${live ? `Run again with fresh calls${some}` : `Run it live${some}`}</button>`);
    const we = entry('window');
    if (live && we && we.window && we.window !== state.W) btns.push(`<button class="btn next small" id="runWin">Run sliding window with ${state.W} session${state.W>1?'s':''}</button>`);
    if (live) btns.push(`<button class="btn ghost small" id="showDemo">Show the scripted demo</button>`);
  }
  $('#runBtns').innerHTML = btns.join('');
  $('#runAll')?.addEventListener('click', () => askConfirm(shown().length < ORDER.length ? shown() : null, live));
  $('#runWin')?.addEventListener('click', () => askConfirm(['window'], false));
  $('#showDemo')?.addEventListener('click', async () => { await post(`/api/results/${H().slug}/clear`); await loadResults(); renderDuel(); });
  renderRunInfo();
}
async function askConfirm(only, fresh){
  try {
    const qs = new URLSearchParams({window: state.W, ...(only ? {only: only.join(',')} : {})});
    const est = await api(`/api/estimate/${H().slug}?${qs}`);
    state.confirm = {only, fresh, est};
  } catch (e) { state.confirm = {error: e.message}; }
  renderRunInfo();
}
function renderRunInfo(){
  const el = $('#runInfo'), c = state.confirm, j = state.job;
  if (j && j.status === 'running') {
    const ids = j.contestants;
    el.innerHTML = `<div class="note"><span class="spin"></span>Running · ${Math.round(j.elapsed||0)} s · ${usd(j.meter?.dollars ?? null)}</div>
      <div class="prog">${ids.map(cid => { const p = j.progress[cid]; const pct = p.total ? 100*p.done/p.total : 0;
        return `<div class="p" style="--k:${color(cid)}"><div class="l"><b>${cname(cid)}</b><span>${p.error ? 'failed' : esc(p.stage)}</span></div><div class="bar"><i style="width:${pct}%"></i></div>${p.error?`<div class="err">${esc(p.error)}</div>`:''}</div>`; }).join('')}</div>`;
    return;
  }
  if (j && j.status !== 'running' && j.done_note) { el.innerHTML = j.done_note; return; }
  if (c && c.error) { el.innerHTML = `<p class="err">${esc(c.error)}</p>`; return; }
  if (c) {
    const e = c.est;
    el.innerHTML = `<div class="row" style="margin-top:12px"><span class="note" style="margin:0">${c.only ? c.only.map(cname).join(', ') : 'All six contestants'}: about <b>${usd(e.dollars)}</b> (answers ${usd(e.parts.answers)}, memory upkeep ${usd(e.parts.upkeep)}, grading ${usd(e.parts.grading)}). Every call is cached, so rerunning the same thing is free${c.fresh ? ', except with fresh calls' : ''}. Budget cap: ${usd(e.budget)}.</span>
      <button class="btn next small" id="go">Start</button><button class="btn ghost small" id="cancel">Cancel</button></div>`;
    $('#go').onclick = () => startRun(c.only, c.fresh);
    $('#cancel').onclick = () => { state.confirm = null; renderRunInfo(); };
    return;
  }
  el.innerHTML = '';
}
async function startRun(only, fresh){
  state.confirm = null;
  try {
    const {job} = await post(`/api/run/${H().slug}`, {only, window: state.W, fresh});
    state.job = {id: job, status: 'running', contestants: only || ORDER, progress: {}, elapsed: 0};
    renderRunPanel(); poll();
  } catch (e) { state.confirm = {error: e.message}; renderRunInfo(); }
}
async function poll(){
  if (!state.job) return;
  try {
    const j = await api(`/api/jobs/${state.job.id}`);
    state.job = j;
    if (j.status === 'running') { renderRunInfo(); setTimeout(poll, 1500); return; }
    const failed = j.contestants.filter(c => j.progress[c].error);
    j.done_note = `<p class="note">${j.status === 'done' ? 'Done' : 'Finished with problems'} in ${Math.round(j.elapsed)} s · cost ${usd(j.meter?.dollars)}${j.meter?.cached ? ` · ${j.meter.cached} calls came from the cache` : ''}.</p>` +
      failed.map(c => `<p class="err">${cname(c)}: ${esc(j.progress[c].error)}</p>`).join('');
    await loadResults(); renderDuel();
  } catch (e) { state.job = null; state.confirm = {error: e.message}; renderRunInfo(); }
}

function renderCps(){ $('#cps').innerHTML = CPS().map(c => `<button aria-pressed="${c===state.cp}" data-cp="${c}">${c}</button>`).join(''); }
$('#cps').addEventListener('click', e => { const b = e.target.closest('button'); if (!b) return; state.cp = +b.dataset.cp; stopAnim();
  if (!qsAt(state.cp).some(q => q.id === state.q)) state.q = qsAt(state.cp)[0].id; renderDuel(); });
$('#win').addEventListener('input', e => { state.W = +e.target.value; $('#winv').textContent = state.W; renderDuel(); });

function renderChips(){
  $('#whoChips').innerHTML = ORDER.map(c => `<button style="--k:${color(c)}" aria-pressed="${state.shown.has(c)}" data-c="${c}"><i></i>${cname(c)}</button>`).join('');
}
$('#whoChips').addEventListener('click', e => { const b = e.target.closest('button'); if (!b) return; const c = b.dataset.c;
  if (state.shown.has(c)) { if (state.shown.size > 1) state.shown.delete(c); } else state.shown.add(c);
  try { localStorage.setItem('md-shown', JSON.stringify([...state.shown])); } catch (err) {}
  renderDuel(); });

function mapSvg(cid, upto){
  const e = entry(cid), facts = H().facts, n = N();
  const W = 330, L = 86, top = 20, rh = 17, cw = (W-L-4)/n;
  let s = `<defs><pattern id="hatch-${cid}" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="5" height="5" fill="#ffd95e" opacity=".35"/><line x1="0" y1="0" x2="0" y2="5" stroke="#ffd95e" stroke-width="2.4"/></pattern></defs>`;
  CPS().forEach(c => { s += `<text x="${L+(c-.5)*cw}" y="11" text-anchor="middle" font-size="9" font-family="JetBrains Mono, monospace" fill="${c===state.cp?'#ffa266':'#5e7e6a'}">${c}</text>`; });
  facts.forEach((f, r) => {
    const y = top + r*rh;
    s += `<text x="0" y="${y+11}" font-size="10.5" fill="#93b4a0">${esc(f.label)}</text>`;
    for (let t = 1; t <= n; t++) {
      const x = L + (t-1)*cw;
      const tl = e && e.timeline && e.timeline[t-1];
      if (t > upto || !tl) { s += `<rect x="${x+.8}" y="${y+1}" width="${cw-1.6}" height="${rh-4}" rx="2" fill="none" stroke="#12291e"/>`; continue; }
      const [stt, v] = tl.states[f.key] || ['na', null], sd = ST[stt] || ST.na;
      const tipTxt = `${esc(f.label)} after s${t}|${sd.l}${v ? ': ' + esc(v) : ''}`;
      let shape;
      if (stt === 'na') shape = `<rect x="${x+.8}" y="${y+1}" width="${cw-1.6}" height="${rh-4}" rx="2" fill="#0b1c13"/>`;
      else if (stt === 'missing') shape = `<rect x="${x+1.3}" y="${y+1.5}" width="${cw-2.6}" height="${rh-5}" rx="2" fill="none" stroke="#5e7e6a" stroke-dasharray="2 2"/>`;
      else if (stt === 'gone') shape = `<rect x="${x+.8}" y="${y+1}" width="${cw-1.6}" height="${rh-4}" rx="2" fill="#0b1c13"/><circle cx="${x+cw/2}" cy="${y+rh/2-1}" r="1.8" fill="#7ee39a"/>`;
      else shape = `<rect x="${x+.8}" y="${y+1}" width="${cw-1.6}" height="${rh-4}" rx="2" fill="${sd.hatch ? `url(#hatch-${cid})` : sd.c}" opacity="${stt==='current'?.85:1}"/>`;
      s += `<g data-tip="${tipTxt}">${shape}</g>`;
    }
  });
  const cx = L + (state.cp-.5)*cw, bottom = top + facts.length*rh;
  s += `<line x1="${cx}" y1="${top-3}" x2="${cx}" y2="${bottom}" stroke="#ffa266" stroke-width="1.2" opacity=".7"/>`;
  if (cid === 'window' && e) { const t = Math.min(upto, state.cp), w = e.window || state.W, a = Math.max(1, t-w+1);
    s += `<rect x="${L+(a-1)*cw}" y="${top-3}" width="${(t-a+1)*cw}" height="${bottom-top+3}" fill="none" stroke="#ff8f5a" stroke-width="1.5" rx="3"/>`; }
  return `<svg viewBox="0 0 ${W} ${bottom+2}" role="img" aria-label="${cname(cid)} memory map">${s}</svg>`;
}
function renderMaps(upto = state.cp){
  const t = Math.min(upto, state.cp);
  const tokAt = cid => { const e = entry(cid); return e && e.timeline && e.timeline[t-1] ? e.timeline[t-1].tokens : 0; };
  const mx = Math.max(1, ...ORDER.map(tokAt));
  $('#maps').innerHTML = shown().map(cid => {
    const e = entry(cid), tok = tokAt(cid);
    const how = cid === 'window' ? `Sends only the last ${(e && e.window) || state.W} session${((e && e.window) || state.W) > 1 ? 's' : ''}.` : (INFO[cid]||{}).how;
    if (!e) return `<div class="map" style="--k:${color(cid)}"><div class="hd"><span>${cname(cid)}</span></div><p class="how">Not run yet.</p></div>`;
    return `<div class="map" style="--k:${color(cid)}">
      <div class="hd"><span>${cname(cid)}</span><span class="tok">${tok.toLocaleString()} tokens</span></div>
      <div class="tokbar" title="Memory sent with each answer after session ${t}"><i style="width:${Math.max(1.5, 100*tok/mx)}%"></i></div>
      ${mapSvg(cid, upto)}
      <p class="how">${esc(how)}</p></div>`;
  }).join('');
}
bindTips($('#maps'));
function renderMapLegend(){
  const sw = st => st==='missing' ? `<i style="border:1px dashed #5e7e6a"></i>` : st==='gone' ? `<i style="background:#0b1c13;box-shadow:inset 0 0 0 3.5px #0b1c13, inset 0 0 0 6px #7ee39a"></i>` : st==='na' ? `<i style="background:#0b1c13;border:1px solid #1e3d2d"></i>` : st==='conflict' ? `<i style="background:repeating-linear-gradient(45deg,#ffd95e 0 2px,rgba(255,217,94,.35) 2px 4px)"></i>` : `<i style="background:${ST[st].c}"></i>`;
  $('#mapLegend').innerHTML = ['current','stale','partial','conflict','missing','leak','gone','na'].map(s => `<span>${sw(s)}${ST[s].l}</span>`).join('');
}

function renderScore(){
  $('#scoreCap').textContent = `Score after session ${state.cp} · ${qsAt(state.cp).length} questions · right = 1, partly = ½`;
  $('#score').innerHTML = shown().map(cid => {
    const qs = qsAt(state.cp), counts = {}; let n = 0;
    qs.forEach(q => { const a = answerOf(cid, state.cp, q.id); if (a && a.grade) { counts[a.grade] = (counts[a.grade]||0)+1; n++; } });
    const sc = scoreOf(cid, state.cp);
    const bar = OUT_ORDER.filter(o => counts[o]).map(o => `<i style="width:${100*counts[o]/n}%;background:${OUT[o].c}" title="${OUT[o].l}: ${counts[o]}"></i>`).join('');
    const parts = OUT_ORDER.filter(o => counts[o]).map(o => `${counts[o]} ${OUT[o].l.toLowerCase()}`).join(' · ');
    return `<div class="sc" style="--k:${color(cid)}"><div class="lab"><b>${cname(cid)}</b><span>${sc == null ? '–' : Math.round(100*sc) + '%'}</span></div><div class="bar">${bar}</div><div class="lab"><span>${parts || 'no results'}</span></div></div>`;
  }).join('');
}
function renderQdeck(){
  $('#qdeck').innerHTML = qsAt(state.cp).map(q => {
    const pips = shown().map(c => { const a = answerOf(c, state.cp, q.id); return `<i style="background:${a && a.grade ? OUT[a.grade].c : '#1e3d2d'}" title="${cname(c)}"></i>`; }).join('');
    return `<button class="qcard" aria-pressed="${q.id===state.q}" data-q="${q.id}"><span class="ty"><span>${TYPE_LABEL[q.type]||q.type}</span><span class="pips">${pips}</span></span><span class="qq">${esc(q.question)}</span></button>`;
  }).join('');
}
$('#qdeck').addEventListener('click', e => { const b = e.target.closest('.qcard'); if (b) { state.q = b.dataset.q; renderQdeck(); renderAnswers(); } });

function evidenceHtml(cid, q, a){
  const ev = a.evidence || {}, words = keywords(q), t = state.cp;
  if (ev.kind === 'sessions') {
    const ss = ev.sessions || [], a0 = ss[0], b0 = ss[ss.length-1];
    const f = q.key ? H().facts.find(x => x.key === q.key) : null;
    const mentioned = f ? Object.keys(f.mentions||{}).map(Number).filter(s => ss.includes(s)) : [];
    if (f) f.truth.forEach(([s,v]) => { if (v === null && ss.includes(s)) mentioned.push(s); });
    const toks = ss.reduce((acc, s) => acc + H().session_tokens[s-1], 0);
    return `<span class="hi">Sessions ${a0}–${b0}</span> · ${toks.toLocaleString()} tokens of chat\n` +
      (q.key ? (mentioned.length ? `${esc(factLabel(q.key))} comes up in session${mentioned.length>1?'s':''} ${[...new Set(mentioned)].sort((x,y)=>x-y).join(', ')}` : `Nothing about the ${esc(factLabel(q.key).toLowerCase())} in these sessions`) : '');
  }
  if (ev.kind === 'facts') {
    const act = ev.active || [], ret = ev.retired || [];
    const rel = f => words.some(w => f.text.toLowerCase().includes(w));
    const relA = act.filter(rel), relR = ret.filter(rel);
    let h = `${act.length} active facts\n` + relA.map(f => `<span class="hi">#${f.id} ${mark(f.text, words)}</span>`).join('\n');
    if (relR.length) h += '\n' + relR.map(f => `<s>#${f.id} ${esc(f.text)}</s> retired after s${f.retired}`).join('\n');
    if (!relA.length && !relR.length) h += 'No fact about this';
    const others = act.filter(f => !rel(f));
    if (others.length) h += `\n<span style="color:var(--faint)">+ ${others.length} other facts</span>`;
    return h;
  }
  if (ev.kind === 'hits') {
    return `Closest ${ev.hits.length} past messages\n` + ev.hits.map(x => `<span class="tag">s${x.session}</span> ${mark(x.text.length > 260 ? x.text.slice(0, 260) + '…' : x.text, words)}`).join('\n\n');
  }
  const text = (ev.text != null ? ev.text : '') || (entry(cid)?.checkpoints[String(t)]?.memory) || '';
  return text ? mark(text, words) : '(empty)';
}
function renderAnswers(){
  const q = qsAt(state.cp).find(x => x.id === state.q) || qsAt(state.cp)[0];
  if (!q) return;
  const outdated = q.outdated && q.outdated.length ? ` <span style="color:var(--faint)">· outdated: ${esc(q.outdated.join('; '))}</span>` : '';
  $('#refbox').innerHTML = `<b>${esc(H().user)} asks:</b> “${esc(q.question)}” &nbsp;·&nbsp; <b>Answer key:</b> ${esc(q.reference)}${outdated}`;
  $('#answers').innerHTML = shown().map(cid => {
    const a = answerOf(cid, state.cp, q.id), e = entry(cid);
    if (!e) return `<div class="ans" style="--k:${color(cid)}"><div class="who"><span>${cname(cid)}</span></div><p class="why">Not run yet.</p></div>`;
    if (!a) return `<div class="ans" style="--k:${color(cid)}"><div class="who"><span>${cname(cid)}</span></div><p class="why">No answer saved for this question.</p></div>`;
    if (a.error) return `<div class="ans" style="--k:${color(cid)}"><div class="who"><span>${cname(cid)}</span><span class="verdict" style="color:#ff6b6b">Error</span></div><p class="err">${esc(a.error)}</p></div>`;
    const o = OUT[a.grade] || {c:'#93b4a0', l:a.grade};
    return `<div class="ans" style="--k:${color(cid)}">
      <div class="who"><span>${cname(cid)}</span><span class="verdict" style="color:${o.c}">${o.l}</span></div>
      <div class="text">${esc(a.answer)}</div>
      <div class="mem">${evidenceHtml(cid, q, a)}</div>
      <p class="why">${esc(a.why || '')}</p>
      <div class="cost">${(a.tokens_in||0).toLocaleString()} tokens in · about ${usd(a.dollars)} for this answer</div></div>`;
  }).join('');
}

function stopAnim(){ if (state.anim) { clearInterval(state.anim); state.anim = null; $('#replay').textContent = '▶ Replay sessions'; } }
$('#replay').onclick = () => {
  if (state.anim) { stopAnim(); renderMaps(); return; }
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) { renderMaps(); return; }
  let t = 1; $('#replay').textContent = '■ Stop';
  renderMaps(t);
  state.anim = setInterval(() => { t++; renderMaps(t); if (t >= state.cp) stopAnim(); }, 260);
};
function renderDuel(){
  $('#win').value = state.W; $('#winv').textContent = state.W;
  renderRunPanel(); renderCps(); renderChips(); renderMaps(); renderMapLegend(); renderScore(); renderQdeck(); renderAnswers();
}

// ================= DEBRIEF =================
function lineChart(sel, {xs, series, yMax, yMin = 0, yTicks, yFmt, xLab, xFmt, area, log}){
  const W = 520, H0 = 280, L = 52, R0 = 16, T0 = 14, B = 40;
  const f = v => log ? Math.log10(Math.max(v, yMin)) : v, f0 = f(yMin), f1 = f(yMax);
  const x = v => L + (W-L-R0)*(v-xs[0])/(xs[xs.length-1]-xs[0]), y = v => T0 + (H0-T0-B)*(1 - (f(v)-f0)/(f1-f0));
  let s = '';
  yTicks.forEach(v => { s += `<line x1="${L}" x2="${W-R0}" y1="${y(v)}" y2="${y(v)}" stroke="#1e3d2d"/><text x="${L-8}" y="${y(v)+4}" text-anchor="end" font-size="10.5" font-family="JetBrains Mono, monospace" fill="#5e7e6a">${yFmt(v)}</text>`; });
  xs.forEach(v => { const lab = xFmt ? xFmt(v) : v; if (lab != null) s += `<text x="${x(v)}" y="${H0-B+18}" text-anchor="middle" font-size="10.5" font-family="JetBrains Mono, monospace" fill="#5e7e6a">${lab}</text>`; });
  s += `<text x="${(L+W-R0)/2}" y="${H0-4}" text-anchor="middle" font-size="11" fill="#93b4a0">${xLab}</text>`;
  series.forEach(se => {
    const pts = se.vals.map((v,i) => v == null ? null : [x(xs[i]), y(v)]).filter(Boolean);
    if (!pts.length) return;
    if (area) s += `<path d="M${pts.map(p => p.join(',')).join(' L')} L${pts[pts.length-1][0]},${y(yMin)} L${pts[0][0]},${y(yMin)} Z" fill="${se.hex}" opacity=".07"/>`;
    s += `<polyline points="${pts.map(p => p.join(',')).join(' ')}" fill="none" stroke="${se.hex}" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round"/>`;
    if (se.dots) pts.forEach(p => { s += `<circle cx="${p[0]}" cy="${p[1]}" r="3.3" fill="${se.hex}"/>`; });
    const lp = pts[pts.length-1]; s += `<circle cx="${lp[0]}" cy="${lp[1]}" r="4.5" fill="${se.hex}" stroke="#0e2118" stroke-width="2"/>`;
  });
  $(sel).innerHTML = s;
  const leg = $(sel).parentElement.querySelector('.legend') || $(sel).insertAdjacentElement('afterend', Object.assign(document.createElement('div'), {className: 'legend'}));
  leg.style.marginTop = '8px';
  leg.innerHTML = series.map(se => `<span><i style="background:${se.hex};border-radius:50%"></i>${se.label}</span>`).join('');
}
function avgScore(cid){ const v = CPS().map(cp => scoreOf(cid, cp)).filter(x => x != null); return v.length ? v.reduce((a,b) => a+b, 0)/v.length : null; }
function renderDebrief(){
  const ids = shown().filter(c => entry(c));
  lineChart('#accChart', {xs: CPS(), yMax: 100, yTicks: [0,25,50,75,100], yFmt: v => v+'%', xLab: 'quiz after session',
    series: ids.map(c => ({hex: color(c), label: cname(c), dots: true, vals: CPS().map(cp => { const s = scoreOf(c, cp); return s == null ? null : Math.round(100*s); })}))});
  const xs = [...Array(N())].map((_,i) => i+1);
  const tok = c => xs.map(t => entry(c).timeline[t-1]?.tokens ?? null);
  const mx = Math.max(1, ...ids.flatMap(c => tok(c).filter(v => v != null)));
  const top = Math.pow(10, Math.ceil(Math.log10(mx)));
  const ticks = []; for (let v = 10; v <= top; v *= 10) ticks.push(v);
  lineChart('#tokChart', {xs, log: true, yMin: 10, yMax: top, yTicks: ticks, yFmt: v => fmt(v), xLab: 'session (tokens on a log scale: each line up is 10 times more)', xFmt: v => (v===1 || v%5===0) ? v : null,
    series: ids.map(c => ({hex: color(c), label: cname(c), vals: tok(c)}))});
  const per = H().session_tokens.reduce((a,b) => a+b, 0) / N();
  $('#tokNote').textContent = `A real chat re-sends this with every turn. These sessions average ${Math.round(per).toLocaleString()} tokens; at one chat a day, a full transcript would pass ${fmt(per*365)} tokens within a year, beyond what most models can read at once.`;

  // matrix
  const types = Object.keys(TYPE_LABEL);
  const W = 900, L = 140, top2 = 36, rh = 30, colW = (W-L)/Math.max(1, ids.length);
  let s = '';
  ids.forEach((c, j) => { s += `<text x="${L+j*colW+4}" y="20" font-size="11.5" font-weight="700" fill="${color(c)}">${cname(c)}</text>`; });
  types.forEach((ty, i) => {
    const y = top2 + i*rh;
    s += `<text x="0" y="${y+15}" font-size="12.5" fill="#93b4a0">${TYPE_LABEL[ty]}</text><line x1="0" x2="${W}" y1="${y+rh-4}" y2="${y+rh-4}" stroke="#12291e"/>`;
    ids.forEach((c, j) => {
      let k = 0;
      CPS().forEach(cp => qsAt(cp).filter(q => q.type === ty).forEach(q => {
        const a = answerOf(c, cp, q.id); const x = L + j*colW + 4 + k*11; k++;
        const o = a && a.grade ? OUT[a.grade] : {c:'#1e3d2d', l:'no result'};
        s += `<g data-tip="${esc(q.question)} · after s${cp}|${esc(cname(c))}: ${o.l}"><rect x="${x}" y="${y+3}" width="9" height="16" rx="2" fill="${o.c}"/></g>`;
      }));
    });
  });
  $('#matrix').setAttribute('viewBox', `0 0 ${W} ${top2 + types.length*rh}`);
  $('#matrix').innerHTML = s;

  // cost table
  const last = CPS()[CPS().length-1];
  $('#costTable').innerHTML = ids.map(c => {
    const e = entry(c), tl = e.timeline;
    const upk = tl.reduce((a,x) => a + (x.upkeep_dollars||0), 0);
    let ans = 0, stale = 0; CPS().forEach(cp => (e.checkpoints[String(cp)]?.answers||[]).forEach(a => { ans += a.dollars||0; if (a.grade === 'stale') stale++; }));
    const fq = qsAt(last).find(q => q.type === 'forgetting'); const fa = fq ? answerOf(c, last, fq.id) : null;
    const sc = avgScore(c);
    return `<tr><td><span class="nm"><i style="background:${color(c)}"></i>${cname(c)}</span></td><td class="num">${sc == null ? '–' : Math.round(100*sc)+'%'}</td>
      <td class="num">${(tl[tl.length-1]?.tokens||0).toLocaleString()} tokens</td><td class="num">${upk ? usd(upk) : '–'}</td><td class="num">${usd(ans)}</td>
      <td class="num">${stale}</td><td>${fa ? `<span style="color:${OUT[fa.grade]?.c}">${OUT[fa.grade]?.l}</span>` : '–'}</td></tr>`;
  }).join('');

  const by = ids.map(c => ({c, sc: avgScore(c), tok: entry(c).timeline[N()-1]?.tokens || 0})).filter(x => x.sc != null).sort((a,b) => b.sc - a.sc);
  if (by.length) {
    const best = by[0], cheap = [...by].sort((a,b) => a.tok - b.tok)[0];
    const full = by.find(x => x.c === 'full');
    $('#debriefLede').textContent = `${state.res.mode === 'scripted' ? 'In these scripted results, ' : 'In this run, '}${cname(best.c).toLowerCase()} scored best on average (${Math.round(100*best.sc)}%), sending ${best.tok.toLocaleString()} tokens of memory with each answer by session ${N()}. ` +
      (full && cheap.c !== 'full' ? `${cname(cheap.c)} sent the least (${cheap.tok.toLocaleString()}), about ${Math.max(1, Math.round(full.tok / Math.max(1, cheap.tok)))} times less than the full transcript, and scored ${Math.round(100*cheap.sc)}%. ` : '') +
      `Hover the squares to see which questions each one missed.`;
  }
  bindTips($('#matrix'));
}

const GUIDE = [
 ['full','Every word','Anything, while it fits; time order; details','Cost and speed as history grows; facts in the middle; real deletion means editing history','Grows with every session, and is re-sent every turn'],
 ['window','The last N sessions','Recent context, simple and cheap','Anything older than the window; forgets by accident, not on request','Flat'],
 ['summary','A short running note, rewritten each session','Gist and big events in little space','Small details; errors compound with each rewrite','Flat, plus a small rewrite each session'],
 ['facts','A list of short facts, added and retired','Current facts, cheap; easy to show, edit and delete','History of changes; contradictions if the old fact isn’t retired; details judged too minor','Small, grows slowly; one cheap update per session'],
 ['rag','Every message, searchable','Huge histories at flat cost; specific old details','Questions worded differently from the original; telling which mention is current; deletion','Flat per answer; the index grows'],
 ['notes','Notes the assistant writes, edits and deletes itself','Adapts what it keeps; can keep a timeline and preferences','Depends on the model’s judgment; harder to predict','Small, plus one update call per session'],
];
function renderGuide(){ $('#guide').innerHTML = GUIDE.map(([c,keeps,good,bad,cost]) => `<tr><td><span class="nm"><i style="background:${color(c)}"></i>${cname(c)}</span></td><td>${keeps}</td><td>${good}</td><td>${bad}</td><td>${cost}</td></tr>`).join(''); }

// ================= NAV + BOOT =================
const STEPS = ['basics','history','duel','debrief'];
function go(step){
  state.step = step; stopAnim(); hideTip();
  document.querySelectorAll('.step').forEach(s => s.hidden = s.id !== step);
  document.querySelectorAll('nav.steps button').forEach(b => b.setAttribute('aria-current', b.dataset.step === step ? 'step' : 'false'));
  if (step === 'basics') renderSlide();
  if (step === 'history') renderHistory();
  if (step === 'duel') renderDuel();
  if (step === 'debrief') { renderDebrief(); renderGuide(); }
  try { if (location.hash.slice(1) !== step) history.replaceState(null, '', '#' + step); } catch (e) {}
  window.scrollTo({top: 0});
}
document.querySelectorAll('nav.steps button').forEach(b => b.onclick = () => go(b.dataset.step));
document.querySelectorAll('[data-go]').forEach(b => b.onclick = () => go(b.dataset.go));
addEventListener('hashchange', () => { const h = location.hash.slice(1); if (STEPS.includes(h) && h !== state.step) go(h); });

async function loadResults(){
  state.res = await api(`/api/results/${H().slug}`);
  const we = state.res.contestants && state.res.contestants.window;
  if (state.res.mode === 'live' && we && we.window) state.W = we.window;
  const chip = $('#modeChip');
  chip.className = 'modechip' + (state.res.mode === 'live' ? ' live' : '');
  chip.textContent = state.status.public ? 'Hosted demo · saved results' : state.res.mode === 'live' ? 'Live results' : (state.status.has_key ? (state.status.fake ? 'Test mode · stand-in AI' : 'Scripted demo · key found') : 'Scripted demo · no API key');
}

(async function boot(){
  drawLogo();
  if (document.fonts && document.fonts.load) document.fonts.load("700 100px 'Oswald'").then(drawLogo, () => {});
  try {
    state.status = await api('/api/status');
    ORDER = state.status.contestants.map(c => c.id);
    INFO = Object.fromEntries(state.status.contestants.map(c => [c.id, c]));
    $('#repoLink').href = state.status.repo;
    state.W = state.status.window || 3;
    const list = await api('/api/histories');
    const slug = (list[0] || {}).slug || 'nell';
    state.hist = await api(`/api/history/${slug}`);
    let saved = null; try { saved = JSON.parse(localStorage.getItem('md-shown') || 'null'); } catch (e) {}
    state.shown = new Set(Array.isArray(saved) && saved.length ? saved.filter(c => ORDER.includes(c)) : ORDER);
    state.cp = CPS()[CPS().length-1];
    await loadResults();
  } catch (e) {
    document.querySelector('.wrap').insertAdjacentHTML('afterbegin', `<p class="err">Couldn't load the app's data: ${esc(e.message)}. Is the server running?</p>`);
    return;
  }
  const h0 = location.hash.slice(1);
  go(STEPS.includes(h0) ? h0 : 'basics');
})();
