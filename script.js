(function(){
var T=[
["Publish something worth citing.","Bring the rigor of a research desk to every page. Give writers a clear brief, reviewers the evidence, and your audience a source they can trust.",[["Evidence-led briefs","Questions, gaps, and source requirements"],["A reviewable workflow","Claims and references, kept in context"],["A measurable publishing loop","Learn from AI answers, not assumptions"]]],
["Win where answers are formed.","Look past rankings. See which questions AI answers from your pages, and which ones it answers from someone else's.",[["Citation coverage","Track presence across test questions"],["Query gap detection","BM25 and embeddings find thin passages"],["Retest after every change","Compare new runs to the same baseline"]]],
["Check the claims, not just the mentions.","Give researchers and product owners a way to verify that AI represents your facts correctly.",[["Claim fidelity checks","Compare answers against verified facts"],["Integrity audit","Same visible content for people and AI crawlers"],["Structured metadata","JSON-LD that matches the page"]]]];
var tabs=document.querySelectorAll('.tabs button');
function show(i){var d=T[i];
 tabs.forEach(function(b,k){b.setAttribute('aria-selected',k===i)});
 document.getElementById('tt').textContent=d[0];document.getElementById('td').textContent=d[1];
 document.getElementById('tl').innerHTML=d[2].map(function(r){return '<li><b>'+r[0]+'</b>'+r[1]+'</li>'}).join('');}
tabs.forEach(function(b){b.addEventListener('click',function(){show(+b.dataset.t)})});
show(0);
var Q=[["How long does a home battery last?","A home battery's useful life depends on chemistry, charge cycles and operating conditions.","Lifespan depends on chemistry, cycling and operating conditions. Compare the warranty's time, throughput and retained capacity. [1]",1],["Is cycle life the same as lifespan?","Cycle life alone doesn't determine a battery's service life.","Not exactly. Service life also depends on age, conditions and warranty terms. [1]",1],["What does a battery warranty cover?","Warranty terms: what is covered, and under which conditions.","Coverage varies by maker. Check the time limit, energy throughput and retained-capacity terms. [1]",1],["Does cold weather hurt it?","(no passage on temperature found on our page)","Temperature can affect performance, but sources differ on how much.",0]];
var chips=document.getElementById('chips'),pn=document.querySelectorAll('.pn'),ps=document.getElementById('ps'),an=document.getElementById('an'),vd=document.getElementById('vd'),tm=[],iv,still=window.matchMedia&&matchMedia('(prefers-reduced-motion:reduce)').matches;
Q.forEach(function(q,i){var b=document.createElement('button');b.textContent=q[0];b.addEventListener('click',function(){run(i)});chips.appendChild(b)});
window.citeRun=run;function run(i){var q=Q[i];tm.forEach(clearTimeout);clearInterval(iv);
 chips.querySelectorAll('button').forEach(function(b,k){b.classList.toggle('on',k===i)});
 pn.forEach(function(n){n.classList.remove('on')});ps.textContent='';an.textContent='';an.className='';vd.className='verd';vd.textContent='';
 function at(ms,f){tm.push(setTimeout(f,still?0:ms))}
 at(200,function(){pn[0].classList.add('on')});
 at(800,function(){pn[1].classList.add('on');ps.textContent=q[1]});
 at(1500,function(){pn[2].classList.add('on');var n=0;an.className='cur';iv=setInterval(function(){n+=2;an.textContent=q[2].slice(0,n);if(n>=q[2].length){clearInterval(iv);an.className='';pn[3].classList.add('on');vd.className='verd '+(q[3]?'ok':'no');vd.textContent=q[3]?'\u2713 Cited. Claim matches the verified source.':'\u26A0 Not cited. Gap detected: add a temperature section, then retest.'}},still?0:22)});}
var tk=document.getElementById('tk'),h='';for(var r=0;r<2;r++)Q.forEach(function(q){h+='<span>'+q[0].toLowerCase()+'</span>'});tk.innerHTML=h+h;
function count(el){var m=el.textContent.match(/(\d+)(.*)/);if(!m||still)return;var to=+m[1],t0=null;function f(t){t0=t0||t;var p=Math.min((t-t0)/1100,1);el.textContent=Math.round(to*(1-Math.pow(1-p,3)))+m[2];if(p<1)requestAnimationFrame(f)}requestAnimationFrame(f)}
if('IntersectionObserver' in window){
 var rv=document.querySelectorAll('.head,.step,.path,.studio,.dash,.gapcard,.tp,.std .wrap>*,.faq>*,.kpi'),io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){e.target.classList.add('in');io.unobserve(e.target);if(e.target.classList.contains('kpi'))count(e.target.querySelector('b'))}})},{threshold:.15});
 rv.forEach(function(el,i){el.classList.add('rv');if(el.matches('.step,.kpi'))el.style.transitionDelay=(i%4)*90+'ms';io.observe(el)});
 var ao=new IntersectionObserver(function(es){if(es[0].isIntersecting){ao.disconnect();run(0)}},{threshold:.3});ao.observe(document.getElementById('arena'));
}else{run(0)}
})();
(function(){
var hero=document.querySelector('.hero');
hero.addEventListener('pointermove',function(e){var r=hero.getBoundingClientRect();hero.style.setProperty('--mx',(e.clientX-r.left)+'px');hero.style.setProperty('--my',(e.clientY-r.top)+'px')});
var W=['trusts','cites','quotes','recommends'],k=0,rw=document.getElementById('rw');
if(!(window.matchMedia&&matchMedia('(prefers-reduced-motion:reduce)').matches))setInterval(function(){rw.classList.add('out');setTimeout(function(){k=(k+1)%W.length;rw.textContent=W[k];rw.classList.remove('out')},300)},2400);
var pb=document.getElementById('pb');addEventListener('scroll',function(){var h=document.documentElement;pb.style.width=(h.scrollTop/Math.max(1,h.scrollHeight-h.clientHeight)*100)+'%'},{passive:true});
var sw=document.getElementById('sw'),B=[['In today\'s fast-moving world of home energy, homeowners wonder about many things. Batteries are a complex topic with lots of factors to consider before you decide...','Sources disagree and no clear answer was found. (not cited)',18],['A home battery\'s useful life depends on chemistry, charge cycles and operating conditions. Compare warranty time, throughput and retained capacity.','Lifespan depends on chemistry, cycling and conditions. [1] (cited)',86]];
function setBA(on){var d=B[on?1:0];sw.setAttribute('aria-pressed',on);bp.textContent=d[0];bq.textContent=d[1];bm.style.width=d[2]+'%';bn.textContent=d[2]+'%';bl.textContent=on?'After: answer-first':'Before: buried answer'}
sw.addEventListener('click',function(){setBA(sw.getAttribute('aria-pressed')!=='true')});setBA(false);
})();

/* Popup router: every button/link that points to a section or form opens it in a popup instead of scrolling */
(function(){
var MAP={'#platform':'platform','#how':'how','#teams':'teams','#faq':'faq','#arena':'arena','#studio':'studio','#testing':'testing','#standard':'standard','#demo':'t-demo','#signin':'t-signin','#contact':'t-contact'};
var modal=document.getElementById('modal'),body=modal.querySelector('.mbody'),closeB=modal.querySelector('.mx'),node=null,ph=null,from=null;
function open(key,trigger){
  if(!modal.hidden)close(true);
  from=trigger||document.activeElement;
  if(key.indexOf('t-')===0){body.appendChild(document.getElementById(key).content.cloneNode(true))}
  else{node=document.getElementById(key);ph=document.createComment('ph');node.parentNode.insertBefore(ph,node);body.appendChild(node);
    node.querySelectorAll('.rv').forEach(function(e){e.classList.add('in')});
    if(key==='arena'&&window.citeRun)window.citeRun(0)}
  modal.hidden=false;document.body.classList.add('mo');modal.querySelector('.mbox').scrollTop=0;closeB.focus();
}
function close(keep){
  if(node){ph.parentNode.replaceChild(node,ph);node=ph=null}
  body.innerHTML='';modal.hidden=true;document.body.classList.remove('mo');
  if(!keep&&from&&from.focus)from.focus();
}
document.addEventListener('click',function(e){
  var a=e.target.closest('a[href]');
  if(a){var k=MAP[a.getAttribute('href')];if(k){e.preventDefault();open(k,a);return}}
  if(e.target===modal||e.target.closest('.mx'))close();
});
document.addEventListener('keydown',function(e){
  if(modal.hidden)return;
  if(e.key==='Escape'){close();return}
  if(e.key==='Tab'){var f=modal.querySelectorAll('a[href],button,input,textarea,summary,[tabindex]:not([tabindex="-1"])');
    if(!f.length)return;var first=f[0],last=f[f.length-1];
    if(!modal.contains(document.activeElement)){first.focus();e.preventDefault()}
    else if(e.shiftKey&&document.activeElement===first){last.focus();e.preventDefault()}
    else if(!e.shiftKey&&document.activeElement===last){first.focus();e.preventDefault()}}
});
document.addEventListener('submit',function(e){
  var f=e.target.closest('.fm form');if(!f)return;e.preventDefault();
  var m=document.createElement('div');m.innerHTML='<p class="ok">\u2713 '+f.dataset.msg+'</p><p class="fine" style="text-align:left">Prototype: nothing is sent or stored.</p>';
  f.replaceWith(m)
});
})();
