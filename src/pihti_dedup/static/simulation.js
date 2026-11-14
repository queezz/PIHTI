window.addEventListener('DOMContentLoaded', function () {

  "use strict";

  var page = document.querySelector('[data-simulation]');

  if (!page) return;

  var source = document.getElementById('sim-source'), form = document.getElementById('sim-edit');

  var status = document.getElementById('sim-status'), canvas = document.getElementById('sim-canvas');

  var parts = [], model = null, selected = null, viewer = null, opening = false;

  var selection = new Set(), groupBusy = false, partBusy = false;
  var groupForm = document.getElementById('sim-group-form');
  var groupList = document.getElementById('sim-groups');
  var groupName = groupForm.elements.group_name;
  var groupSave = document.getElementById('sim-group-save');
  var groupDelete = document.getElementById('sim-group-delete');
  var clearSelection = document.getElementById('sim-clear');

  var sourceName = '', generation = 0;
  var meshUp = 'y', section = null, ready = false;
  function meshUrl() { return '/mesh/' + encodeURIComponent(sourceName); }
  function syncTools() {
    tools.set({view:'3d',up:meshUp,ready:ready,section:section});
  }
  var tools = window.PihtiMeshTools.bind(page.querySelector('[data-mesh-tools]'), {
    up: function(axis) {
      meshUp = axis;
      if (sourceName) window.PihtiMeshTools.rememberUp(meshUrl(), axis);
      if (viewer) viewer.setUp(axis);
      syncTools();
    },
    cut: function(axis) {
      if (!viewer || !ready) return;
      section = window.PihtiMeshTools.section(viewer, section, axis);
      viewer.setSection(section);
      syncTools();
    },
    at: function(fraction) {
      if (!viewer || !section || !ready) return;
      section.at = fraction;
      viewer.setSection(section);
    }
  });
  syncTools();

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
  function appearance(p) { return (p.mapped ? [p] : p.appearances || [p]).map(function(face){return {start:face.start,count:face.count,colour:colour(face.colour)};}); }

  function repaint() {

    if (viewer) viewer.setParts(parts.map(function (p) { return {start:p.start,count:p.count,colour:colour(p.colour),appearances:appearance(p),selected:selection.has(p),hidden:selection.size > 0 && document.getElementById('sim-isolate').checked && !selection.has(p)}; }));

  }

  var branches = new Map(), expanded = new Set();
  function buildTree() {
    branches = new Map(); expanded.clear();
    var commonRoot = parts.length > 0 && parts.every(function(part) {
      return part.occurrence.length > 1 && part.occurrence[0] === parts[0].occurrence[0];
    });
    parts.forEach(function(part) {
      var level = branches, path = [];
      part.occurrence.slice(commonRoot ? 1 : 0, -1).forEach(function(name) {
        path.push(name);
        if (!level.has(name)) level.set(name, {name:name,key:JSON.stringify(path),parts:[],children:new Map()});
        var branch = level.get(name);
        branch.parts.push(part);
        level = branch.children;
      });
      level.set(part.id, part);
    });
  }

  function list() {
    var area = document.getElementById('sim-parts'), query = document.getElementById('sim-find').value.trim().toLowerCase();
    var focused = document.activeElement?.dataset.pickKey;
    var focusTarget;
    area.replaceChildren();

    function leaf(part, container) {
      if (![part.name,part.original,part.occurrence.join('/')].join(' ').toLowerCase().includes(query)) return;
      var button = document.createElement('button'); button.type = 'button';
      button.dataset.pickKey = 'part:' + part.id;
      button.setAttribute('aria-pressed', String(selection.has(part)));
      var swatch = document.createElement('span'); swatch.className='sim-swatch'; swatch.style.backgroundColor=part.colour;
      var text=document.createElement('span'); text.textContent=part.name;
      var detail=document.createElement('small'); detail.textContent=part.occurrence.at(-1) || part.original;
      text.appendChild(detail); button.append(swatch,text);
      button.addEventListener('click',function(event){ select(part.id, event); });
      container.appendChild(button);
      if (button.dataset.pickKey === focused) focusTarget = button;
    }

    function render(level, container) {
      var nodes = Array.from(level.values());
      nodes.filter(function(node){return node.children;}).forEach(function(branch) {
        var details = document.createElement('details');
        details.className = 'sim-assembly';
        var children = document.createElement('div');
        children.className = 'sim-assembly-children';
        render(branch.children, children);
        if (!children.childElementCount) return;
        var summary = document.createElement('summary');
        var title = document.createElement('span');
        title.textContent = branch.name + ' · ' + branch.parts.length;
        var pick = document.createElement('button');
        pick.type = 'button'; pick.textContent = 'Select';
        pick.dataset.pickKey = 'assembly:' + branch.key;
        pick.setAttribute('aria-label', 'Select assembly ' + branch.name + ', ' + branch.parts.length + ' parts');
        var count = branch.parts.filter(function(part){return selection.has(part);}).length;
        pick.setAttribute('aria-pressed', String(count === branch.parts.length));
        if (count > 0 && count < branch.parts.length) pick.setAttribute('aria-pressed', 'mixed');
        pick.addEventListener('click', function(event) {
          event.preventDefault(); applySelection(branch.parts, event);
        });
        details.open = Boolean(query) || expanded.has(branch.key);
        details.addEventListener('toggle', function() {
          if (query || !details.isConnected) return;
          if (details.open) expanded.add(branch.key); else expanded.delete(branch.key);
        });
        summary.append(title, pick); details.append(summary, children); container.append(details);
        if (pick.dataset.pickKey === focused) focusTarget = pick;
      });
      nodes.filter(function(node){return !node.children;}).forEach(function(part){leaf(part, container);});
    }
    render(branches, area);
    if (focusTarget) focusTarget.focus({preventScroll:true});
  }

  function updateGroups() {
    var active = groupList.value;
    groupList.replaceChildren(new Option('Choose a group', ''));
    Object.entries(ready ? model.drawing_groups : {}).forEach(function ([name, keys]) {
      groupList.add(new Option(name + ' · ' + keys.length, name));
    });
    groupList.value = active;
    groupList.disabled = !ready || groupBusy;
    updateSelectionControls();
  }

  function updateSelectionControls() {
    var blocked = Array.from(selection).some(function (part) { return !part.stable; });
    document.getElementById('sim-selection').textContent = selection.size
      ? selection.size + (selection.size === 1 ? ' part selected' : ' parts selected') +
        (blocked ? ' · includes parts without unique names' : '')
      : 'No parts selected';
    groupSave.disabled = !ready || groupBusy || !selection.size || blocked;
    groupDelete.disabled = !ready || groupBusy || !groupList.value;
    clearSelection.disabled = !selection.size || groupBusy;
  }

  function canSelect() {
    return !opening && !groupBusy && !partBusy &&
      (form.dataset.dirty !== 'true' || window.confirm('Discard unsaved part edits?'));
  }

  function showSelection() {
    form.dataset.dirty = 'false';
    selected = selection.size === 1 ? selection.values().next().value : null;
    document.getElementById('sim-fields').disabled = !selected || !selected.stable;
    document.getElementById('sim-save').disabled = !selected || !selected.stable;
    if (selected) {
      ['name','material','role','colour'].forEach(function(k){ form.elements[k].value=selected[k]; });
    } else form.reset();
    document.getElementById('sim-original').textContent = selected
      ? selected.occurrence.join(' / ')
      : selection.size ? 'Multiple parts selected. Name them together in Drawing groups.'
      : 'Select in the model or parts list.';
    updateSelectionControls();
    list(); repaint();
  }

  function applySelection(members, event) {
    if (!canSelect() || !members.length) return;
    var extend = document.getElementById('sim-multi').checked ||
      (event && (event.ctrlKey || event.metaKey));
    var remove = extend && members.every(function(part){return selection.has(part);});
    if (!extend) selection.clear();
    members.forEach(function(part){ if (remove) selection.delete(part); else selection.add(part); });
    groupList.value = '';
    showSelection();
  }

  function select(id, event) {
    if (parts[id]) applySelection([parts[id]], event);
  }

  clearSelection.addEventListener('click', function () {
    if (!canSelect()) return;
    selection.clear(); groupList.value = '';
    document.getElementById('sim-isolate').checked = false;
    showSelection();
  });
  groupList.addEventListener('change', function () {
    if (!groupList.value || !canSelect()) { groupList.value = ''; updateSelectionControls(); return; }
    var keys = new Set(model.drawing_groups[groupList.value]);
    selection = new Set(parts.filter(function (part) { return part.stable && keys.has(part.key); }));
    groupName.value = groupList.value;
    showSelection();
    if (selection.size !== keys.size) say((keys.size - selection.size) + ' saved parts are missing in this STEP.');
  });

  async function saveGroup(remove) {
    if (!ready || groupBusy || partBusy) return;
    var name = remove ? groupList.value : groupName.value.trim();
    if (!name) { groupName.focus(); return; }
    if (remove && !window.confirm('Remove drawing group “' + name + '”?')) return;
    if (!remove && Object.hasOwn(model.drawing_groups, name) &&
        !window.confirm('Replace the parts in “' + name + '” with this selection?')) return;
    groupBusy = true; updateGroups();
    try {
      var value = await answer(await fetch('/simulation/drawing-group', {
        method:'POST', headers:{'Content-Type':'application/json','X-PIHTI-Token':page.dataset.token},
        body:JSON.stringify({source:sourceName,source_hash:model.source_hash,revision:model.drawing_revision,
          name:name,members:remove ? null : Array.from(selection, function(part){return part.key;})})
      }));
      model.drawing_groups = value.groups; model.drawing_revision = value.revision;
      updateGroups(); groupList.value = remove ? '' : name;
      if (remove) groupName.value = '';
      say(remove ? 'Drawing group removed.' : 'Drawing group saved: ' + name);
    } catch (error) { say(error.message); }
    finally { groupBusy = false; updateGroups(); }
  }

  groupForm.addEventListener('submit', function (event) {
    event.preventDefault(); if (!groupSave.disabled) saveGroup(false);
  });
  groupDelete.addEventListener('click', function () { saveGroup(true); });

  async function answer(response) {

    var value=await response.json(); if (!response.ok) throw new Error(value.error||'Request failed'); return value;

  }

  async function open() {

    if (opening || groupBusy || partBusy || !source.value) return;

    if (form.dataset.dirty==='true' && !window.confirm('Discard unsaved part edits?')) return;

    var ticket=++generation; opening=true; selected=null; document.getElementById('sim-fields').disabled=true; parts=[]; buildTree(); sourceName=source.value;
    ready=false; selection.clear(); groupName.value=''; updateGroups(); section=null; meshUp=window.PihtiMeshTools.upFor(meshUrl()); syncTools();

    document.querySelectorAll('[data-sim-export]').forEach(function(b){b.disabled=true;});

    document.getElementById('sim-save').disabled=true;

    document.getElementById('sim-empty').hidden=false; document.getElementById('sim-empty').textContent='Loading STEP…';

    if(viewer) viewer.clear(); list(); say('Reading STEP…');

    var modelUrl=new URL(location.href); modelUrl.searchParams.set('source',sourceName); history.replaceState(null,'',modelUrl.pathname+modelUrl.search);

    try {

      model=await answer(await window.PihtiViewer3D.fetchDisplayModel(sourceName));

      var response=await fetch('/simulation/mesh?source='+encodeURIComponent(sourceName)+'&hash='+model.source_hash);

      if(!response.ok) await answer(response);

      var mesh=window.PihtiViewer3D.parse(await response.arrayBuffer());

      if(ticket!==generation) return;

      if(!viewer) viewer=window.PihtiViewer3D.create(canvas,{onPick:select});

      if(!viewer) throw new Error('WebGL is unavailable');

      parts=model.parts; buildTree(); mesh.parts=parts.map(function(p){return {start:p.start,count:p.count,colour:colour(p.colour),appearances:appearance(p)};});

      viewer.resize(canvas.parentElement.clientWidth,canvas.parentElement.clientHeight);

      viewer.show(mesh,{up:meshUp}); ready=true; syncTools(); updateGroups();

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

    event.preventDefault(); if(!selected || partBusy) return;
    partBusy=true;

    var entry={}; ['name','material','role','colour'].forEach(function(k){entry[k]=form.elements[k].value.trim();});

    document.getElementById('sim-save').disabled=true;

    try {

      var value=await answer(await fetch('/simulation/map',{method:'POST',headers:{'Content-Type':'application/json','X-PIHTI-Token':page.dataset.token},body:JSON.stringify({source:sourceName,source_hash:model.source_hash,revision:model.revision,key:selected.key,entry:entry})}));

      model.revision=value.revision; Object.assign(selected,entry,{mapped:true}); form.dataset.dirty='false'; list(); repaint(); say('Part saved.');

    } catch(error){say(error.message);} finally {partBusy=false; document.getElementById('sim-save').disabled=!selected.stable;}

  });

  document.querySelectorAll('[data-sim-export]').forEach(function(button){button.addEventListener('click',async function(){

    if(form.dataset.dirty==='true'){say('Save this part before exporting.');return;}

    var data=new FormData(); Object.entries({token:page.dataset.token,source:sourceName,source_hash:model.source_hash,revision:model.revision,purpose:button.dataset.simExport}).forEach(function(pair){data.append(pair[0],pair[1]);});

    button.disabled=true; say('Preparing STEP…');

    try {var response=await fetch('/simulation/export',{method:'POST',body:data});if(!response.ok)await answer(response);var url=URL.createObjectURL(await response.blob());var a=document.createElement('a');a.href=url;a.download=sourceName.split('/').pop().replace(/\.(iam|ipt|step|stp)$/i,'')+'-prepared.zip';a.click();setTimeout(function(){URL.revokeObjectURL(url);},30000);say('Export prepared.');}

    catch(error){say(error.message);}finally{button.disabled=false;}

  });});

  document.getElementById('sim-fit').addEventListener('click',function(){if(viewer)viewer.home();});

  document.getElementById('sim-isolate').addEventListener('change',repaint);

  document.getElementById('sim-find').addEventListener('input',list);

  page.addEventListener('keydown',function(event){
    if(event.key==='Escape' && !event.defaultPrevented && !['INPUT','SELECT','TEXTAREA'].includes(event.target.tagName)) clearSelection.click();
  });

  window.addEventListener('beforeunload',function(event){if(form.dataset.dirty==='true'){event.preventDefault();event.returnValue='';}});

  new ResizeObserver(function(){if(viewer)viewer.resize(canvas.parentElement.clientWidth,canvas.parentElement.clientHeight);}).observe(canvas.parentElement);

  var params=new URLSearchParams(location.search), initial=params.get('source');
  fileFind.value=params.get('find')||'';allFolders.checked=params.get('all')==='1';
  browse(params.get('folder') || (initial ? parent(initial) : ''));
  if(initial){if(!Array.from(source.options).some(function(o){return o.value===initial;}))source.add(new Option(initial,initial));source.value=initial;open();}

});
