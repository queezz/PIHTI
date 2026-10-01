(function () {

  "use strict";

  var page = document.querySelector('[data-simulation]');

  if (!page) return;

  var source = document.getElementById('sim-source'), form = document.getElementById('sim-edit');

  var status = document.getElementById('sim-status'), canvas = document.getElementById('sim-canvas');

  var parts = [], model = null, selected = null, viewer = null, opening = false;

  var sourceName = '', generation = 0;

  var sources = JSON.parse(document.getElementById('sim-sources').textContent);
  var folder = '', fileFind = document.getElementById('sim-file-find');
  var allFolders = document.getElementById('sim-all-folders');
  function parent(path) { return path.includes('/') ? path.slice(0,path.lastIndexOf('/')) : ''; }
  function browse(next) {
    folder = next;
    var crumbs = document.getElementById('sim-folders'); crumbs.replaceChildren();
    function door(label, path, area) {
      var button = document.createElement('button'); button.type='button'; button.className='copy-path'; button.textContent=label;
      button.addEventListener('click',function(){fileFind.value='';allFolders.checked=false;browse(path);}); area.appendChild(button);
    }
    door('Workspace','',crumbs);
    if(folder) folder.split('/').forEach(function(name,i){door(name,folder.split('/').slice(0,i+1).join('/'),crumbs);});
    var children = document.getElementById('sim-children'); children.replaceChildren();
    var prefix = folder ? folder+'/' : '';
    var names = new Set(); sources.forEach(function(path){if(path.startsWith(prefix)){var rest=path.slice(prefix.length);if(rest.includes('/'))names.add(rest.split('/')[0]);}});
    Array.from(names).sort().forEach(function(name){door(name,prefix+name,children);});
    document.getElementById('sim-browse').hidden=!names.size;
    filterFiles();
  }
  function filterFiles() {
    var selectedSource=source.value, query=fileFind.value.trim().toLowerCase();
    var matches=sources.filter(function(path){return (allFolders.checked || (query ? path.startsWith(folder ? folder+'/' : '') : parent(path)===folder)) && path.toLowerCase().includes(query);});
    source.replaceChildren(new Option(matches.length ? 'Choose a file' : 'No matching files',''));
    matches.forEach(function(path){source.add(new Option(allFolders.checked || query ? path : path.split('/').pop(),path));});
    if(matches.includes(selectedSource)) source.value=selectedSource;
    document.getElementById('sim-file-count').textContent=matches.length+(matches.length===1?' file':' files');
    document.getElementById('sim-open').disabled=!source.value || opening;
    var url=new URL(location.href); if(folder)url.searchParams.set('folder',folder);else url.searchParams.delete('folder');
    if(query)url.searchParams.set('find',fileFind.value);else url.searchParams.delete('find');
    if(allFolders.checked)url.searchParams.set('all','1');else url.searchParams.delete('all');
    history.replaceState(null,'',url.pathname+url.search);
  }
  fileFind.addEventListener('input',filterFiles);
  allFolders.addEventListener('change',filterFiles);
  source.addEventListener('change',function(){document.getElementById('sim-open').disabled=!source.value || opening;});

  function say(text) { status.textContent = text; }

  function colour(hex) { return [1, 3, 5].map(function (i) { return parseInt(hex.slice(i,i+2),16)/255; }); }

  function repaint() {

    if (viewer) viewer.setParts(parts.map(function (p) { return {start:p.start,count:p.count,colour:colour(p.colour),selected:p===selected,hidden:document.getElementById('sim-isolate').checked && p!==selected}; }));

  }

  function list() {

    var area = document.getElementById('sim-parts'), query = document.getElementById('sim-find').value.toLowerCase();

    area.replaceChildren();

    parts.forEach(function (part) {

      if (![part.name,part.original,part.material,part.role,part.occurrence.join('/')].join(' ').toLowerCase().includes(query)) return;

      var button = document.createElement('button'); button.type = 'button'; button.setAttribute('aria-pressed', String(part===selected));

      var swatch = document.createElement('span'); swatch.className='sim-swatch'; swatch.style.backgroundColor=part.colour;

      var text=document.createElement('span'); text.textContent=part.name;

      var detail=document.createElement('small'); detail.textContent=[part.role||'Unassigned',part.material,part.mapped?'Saved':'Unmapped'].filter(Boolean).join(' · ');

      text.appendChild(detail); button.append(swatch,text); button.addEventListener('click',function(){ select(part.id); }); area.appendChild(button);

    });

  }

  function select(id) {

    if(form.dataset.dirty==='true' && !window.confirm('Discard unsaved part edits?')) return;

    form.dataset.dirty='false';

    selected=parts.find(function(p){return p.id===id;}) || null;

    if (!selected) return;
    document.getElementById('sim-fields').disabled=!selected.stable;

    ['name','material','role','colour'].forEach(function(k){ form.elements[k].value=selected[k]; });

    document.getElementById('sim-original').textContent=selected.occurrence.join(' / ');

    document.getElementById('sim-save').disabled=!selected.stable;

    say(selected.stable ? 'Edit this part, then Save part.' : 'Occurrence has no unique name; name it in Inventor and re-export.');

    list(); repaint();

  }

  async function answer(response) {

    var value=await response.json(); if (!response.ok) throw new Error(value.error||'Request failed'); return value;

  }

  async function open() {

    if (opening || !source.value) return;

    if (form.dataset.dirty==='true' && !window.confirm('Discard unsaved part edits?')) return;

    var ticket=++generation; opening=true; selected=null; document.getElementById('sim-fields').disabled=true; parts=[]; sourceName=source.value;

    document.querySelectorAll('[data-sim-export]').forEach(function(b){b.disabled=true;});

    document.getElementById('sim-save').disabled=true;

    document.getElementById('sim-empty').hidden=false; document.getElementById('sim-empty').textContent='Loading STEP…';

    if(viewer) viewer.clear(); list(); say('Reading STEP…');

    var modelUrl=new URL(location.href); modelUrl.searchParams.set('source',sourceName); history.replaceState(null,'',modelUrl.pathname+modelUrl.search);

    try {

      model=await answer(await fetch('/simulation/model?source='+encodeURIComponent(sourceName)));

      var response=await fetch('/simulation/mesh?source='+encodeURIComponent(sourceName)+'&hash='+model.source_hash);

      if(!response.ok) await answer(response);

      var mesh=window.PihtiViewer3D.parse(await response.arrayBuffer());

      if(ticket!==generation) return;

      if(!viewer) viewer=window.PihtiViewer3D.create(canvas,{onPick:select});

      if(!viewer) throw new Error('WebGL is unavailable');

      parts=model.parts; mesh.parts=parts.map(function(p){return {start:p.start,count:p.count,colour:colour(p.colour)};});

      viewer.resize(canvas.parentElement.clientWidth,canvas.parentElement.clientHeight);

      viewer.show(mesh,{up:document.getElementById('sim-up').value});

      document.getElementById('sim-empty').hidden=true;

      form.dataset.dirty='false'; document.getElementById('sim-summary').textContent=sourceName.split('/').pop()+' · '+parts.length+' parts · mm'; document.getElementById('sim-summary').title=sourceName;

      document.querySelectorAll('[data-sim-export]').forEach(function(b){b.disabled=false;}); list();

      say('Click a part in the model or the parts list.');

    } catch(error) { say(error.message); document.getElementById('sim-empty').textContent=error.message; }

    finally { opening=false; document.getElementById('sim-open').disabled=!source.value; }

  }

  document.getElementById('sim-open').addEventListener('click',open);

  form.addEventListener('input',function(){form.dataset.dirty='true';});

  form.elements.role.addEventListener('change',function(){var option=this.selectedOptions[0];form.elements.colour.value=option.dataset.colour;});

  form.addEventListener('submit',async function(event){

    event.preventDefault(); if(!selected) return;

    var entry={}; ['name','material','role','colour'].forEach(function(k){entry[k]=form.elements[k].value.trim();});

    document.getElementById('sim-save').disabled=true;

    try {

      var value=await answer(await fetch('/simulation/map',{method:'POST',headers:{'Content-Type':'application/json','X-PIHTI-Token':page.dataset.token},body:JSON.stringify({source:sourceName,source_hash:model.source_hash,revision:model.revision,key:selected.key,entry:entry})}));

      model.revision=value.revision; Object.assign(selected,entry,{mapped:true}); form.dataset.dirty='false'; list(); repaint(); say('Part saved.');

    } catch(error){say(error.message);} finally {document.getElementById('sim-save').disabled=!selected.stable;}

  });

  document.querySelectorAll('[data-sim-export]').forEach(function(button){button.addEventListener('click',async function(){

    if(form.dataset.dirty==='true'){say('Save this part before exporting.');return;}

    var data=new FormData(); Object.entries({token:page.dataset.token,source:sourceName,source_hash:model.source_hash,revision:model.revision,purpose:button.dataset.simExport}).forEach(function(pair){data.append(pair[0],pair[1]);});

    button.disabled=true; say('Preparing STEP…');

    try {var response=await fetch('/simulation/export',{method:'POST',body:data});if(!response.ok)await answer(response);var url=URL.createObjectURL(await response.blob());var a=document.createElement('a');a.href=url;a.download=sourceName.split('/').pop().replace(/\.(iam|ipt|step|stp)$/i,'')+'-prepared.zip';a.click();setTimeout(function(){URL.revokeObjectURL(url);},30000);say('Export prepared.');}

    catch(error){say(error.message);}finally{button.disabled=false;}

  });});

  document.getElementById('sim-fit').addEventListener('click',function(){if(viewer)viewer.home();});

  document.getElementById('sim-up').addEventListener('change',function(){if(viewer)viewer.setUp(this.value);});

  document.getElementById('sim-isolate').addEventListener('change',repaint);

  document.getElementById('sim-find').addEventListener('input',list);

  page.addEventListener('keydown',function(event){if(event.key==='Escape'){if(form.dataset.dirty==='true' && !window.confirm('Discard unsaved part edits?'))return;form.dataset.dirty='false';selected=null;form.reset();document.getElementById('sim-original').textContent='Select in the model or parts list.';document.getElementById('sim-fields').disabled=true;document.getElementById('sim-save').disabled=true;document.getElementById('sim-isolate').checked=false;list();repaint();}});

  window.addEventListener('beforeunload',function(event){if(form.dataset.dirty==='true'){event.preventDefault();event.returnValue='';}});

  new ResizeObserver(function(){if(viewer)viewer.resize(canvas.parentElement.clientWidth,canvas.parentElement.clientHeight);}).observe(canvas.parentElement);

  var params=new URLSearchParams(location.search), initial=params.get('source');
  fileFind.value=params.get('find')||'';allFolders.checked=params.get('all')==='1';
  browse(params.get('folder') || (initial ? parent(initial) : ''));
  if(initial){if(!Array.from(source.options).some(function(o){return o.value===initial;}))source.add(new Option(initial,initial));source.value=initial;open();}

})();
