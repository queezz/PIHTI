(function () {
  "use strict";

  // A small WebGL viewport for the meshes `/mesh/<path>` serves: flat-shaded
  // triangles under one key light plus ambient, an orthographic camera fit to
  // the bounding box, and the isometric home view of the still previews
  // (front / right / above, Z up). Left-drag turns, the wheel zooms toward the
  // pointer, right-drag or Shift-drag pans, double-click returns home. No
  // library: positions and normals go to the GPU as they arrive.

  var MAGIC = "PIHTIMESH";
  var HEADER_BYTES = 44;
  var MEMO_LIMIT = 6;
  var HOME_AZIMUTH = Math.atan2(-1, 1);  // mesh_render.ISO_EYE = (1, -1, 0.72)
  var HOME_ELEVATION = Math.atan2(0.72, Math.SQRT2);
  var MARGIN = 0.06;  // the still previews' frame padding
  // The stills are transparent PNGs composited onto the preview box's own
  // CSS background (dedup.css --mesh-backdrop); this clear colour is read
  // from that same box below, per canvas, so a swap cannot change the tone.
  var BACKDROP_FALLBACK = [0x10 / 255, 0x18 / 255, 0x22 / 255];
  var BASE = [203 / 255, 208 / 255, 214 / 255];  // mesh_render.Style.base_color
  var AMBIENT = 0.42;
  var FILL = 0.18;
  // mesh_render.Style.key_light is (right, forward, up); in view space
  // (right, up, toward the viewer) it reads:
  var KEY = normalize([-0.35, 0.75, 0.55]);
  var ELEVATION_LIMIT = 89 * Math.PI / 180;
  var COAST_LIMIT = 24;  // pixels per frame a flick may start coasting at

  // Two programs share the same lighting: one lights a normal attribute the
  // mesh carries, the other derives a flat normal from how the view-space
  // position changes across the triangle (`OES_standard_derivatives`), so a
  // heavy mesh's payload can skip the normals a flat-shaded triangle does not
  // need. `create` compiles whichever the browser supports.
  var LIGHT_UNIFORMS = ["uniform vec3 uKey;", "uniform vec3 uBase;", "uniform float uAmbient;", "uniform float uFill;"];
  var LIGHT_BODY = [
    "  if (n.z < 0.0) n = -n;",  // two-sided, as the still renderer is
    "  float light = uAmbient + (1.0 - uAmbient) * max(dot(n, uKey), 0.0) + uFill * n.z;",
    "  gl_FragColor = vec4(min(clamp(light, 0.0, 1.15) * uBase, vec3(1.0)), 1.0);"
  ];

  var VERTEX_ATTR = [
    "attribute vec3 aPosition;",
    "attribute vec3 aNormal;",
    "uniform mat4 uView;",
    "uniform mat4 uProjection;",
    "uniform mat3 uNormal;",
    "varying vec3 vNormal;",
    "void main() {",
    "  vNormal = uNormal * aNormal;",
    "  gl_Position = uProjection * uView * vec4(aPosition, 1.0);",
    "}"
  ].join("\n");

  var FRAGMENT_ATTR = ["precision mediump float;", "varying vec3 vNormal;"]
    .concat(LIGHT_UNIFORMS, ["void main() {", "  vec3 n = normalize(vNormal);"], LIGHT_BODY, ["}"])
    .join("\n");

  var VERTEX_FLAT = [
    "attribute vec3 aPosition;",
    "uniform mat4 uView;",
    "uniform mat4 uProjection;",
    "varying vec3 vViewPos;",
    "void main() {",
    "  vec4 p = uView * vec4(aPosition, 1.0);",
    "  vViewPos = p.xyz;",
    "  gl_Position = uProjection * p;",
    "}"
  ].join("\n");

  var FRAGMENT_FLAT = ["#extension GL_OES_standard_derivatives : enable", "precision mediump float;", "varying vec3 vViewPos;"]
    .concat(LIGHT_UNIFORMS, ["void main() {", "  vec3 n = normalize(cross(dFdx(vViewPos), dFdy(vViewPos)));"], LIGHT_BODY, ["}"])
    .join("\n");

  function normalize(v) {
    var length = Math.hypot(v[0], v[1], v[2]) || 1;
    return [v[0] / length, v[1] / length, v[2] / length];
  }
  function cross(a, b) {
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  }
  function dot(a, b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }
  function add(a, b, scale) { return [a[0] + b[0] * scale, a[1] + b[1] * scale, a[2] + b[2] * scale]; }

  // The colour actually painted behind the still image in its box, read live
  // so CSS stays the one place it is set.
  function readBackdrop(el) {
    try {
      var css = window.getComputedStyle(el).backgroundColor;
      var match = /rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)/.exec(css || "");
      if (match) return [match[1] / 255, match[2] / 255, match[3] / 255];
    } catch (error) { /* a detached canvas or an old browser: fall back */ }
    return BACKDROP_FALLBACK;
  }

  // The binary omits per-triangle normals unless `?normals=1` asked for them
  // (needsNormals below decides that); either payload starts with the same
  // header, so the byte length alone says which one this is.
  function parse(buffer) {
    if (buffer.byteLength < HEADER_BYTES) throw new Error("short mesh");
    var bytes = new Uint8Array(buffer, 0, MAGIC.length);
    if (String.fromCharCode.apply(null, bytes) !== MAGIC) throw new Error("not a mesh");
    var head = new DataView(buffer, 0, HEADER_BYTES);
    var count = head.getUint32(16, true);
    var withNormals = buffer.byteLength === HEADER_BYTES + count * 72;
    if (!withNormals && buffer.byteLength !== HEADER_BYTES + count * 36) throw new Error("truncated mesh");
    var box = [];
    for (var index = 0; index < 6; index++) box.push(head.getFloat32(20 + index * 4, true));
    return {
      count: count,
      min: box.slice(0, 3),
      max: box.slice(3),
      positions: new Float32Array(buffer, HEADER_BYTES, count * 9),
      normals: withNormals ? new Float32Array(buffer, HEADER_BYTES + count * 36, count * 9) : null
    };
  }

  var probe = null;
  function supported() {
    if (probe === null) {
      try {
        var test = document.createElement("canvas");
        probe = !!(window.WebGLRenderingContext && test.getContext("webgl"));
      } catch (error) {
        probe = false;
      }
    }
    return probe;
  }

  // A browser without derivatives needs the normals attribute instead; this
  // is what asks the server for the heavier payload that carries it.
  var normalsProbe = null;
  function needsNormals() {
    if (normalsProbe === null) {
      try {
        var test = document.createElement("canvas").getContext("webgl");
        normalsProbe = !(test && test.getExtension("OES_standard_derivatives"));
      } catch (error) {
        normalsProbe = true;
      }
    }
    return normalsProbe;
  }

  // One fetch per URL: the last few meshes stay parsed, and a refusal is
  // remembered with its reason. An aborted or failed request is forgotten.
  // `onSize`, given the response's byte length as soon as headers arrive,
  // lets a caller name a heavy download while it is still in flight; it only
  // fires for the request that actually reaches the network, not a memo hit.
  var memo = new Map();
  function fetchMesh(url, signal, onSize) {
    if (needsNormals()) url += (url.indexOf("?") >= 0 ? "&" : "?") + "normals=1";
    if (memo.has(url)) {
      var known = memo.get(url);
      memo.delete(url);
      memo.set(url, known);
      return known;
    }
    var pending = fetch(url, { credentials: "same-origin", signal: signal }).then(function (response) {
      if (response.ok) {
        var length = onSize && response.headers.get("content-length");
        if (length) onSize(parseInt(length, 10));
        return response.arrayBuffer().then(parse);
      }
      return response.json().catch(function () { return {}; }).then(function (body) {
        var refusal = new Error(body.reason || "no mesh");
        refusal.reason = body.reason || "";
        throw refusal;
      });
    });
    memo.set(url, pending);
    while (memo.size > MEMO_LIMIT) memo.delete(memo.keys().next().value);
    pending.catch(function (error) {
      if (!error.reason && memo.get(url) === pending) memo.delete(url);
    });
    return pending;
  }

  function compile(gl, type, source) {
    var shader = gl.createShader(type);
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(shader));
    return shader;
  }

  function create(canvas, options) {
    options = options || {};
    var gl = canvas.getContext("webgl", { antialias: true, alpha: false });
    if (!gl) return null;
    // The box's background is fixed for the life of this canvas (it is never
    // reparented), so one read at creation is enough.
    var BACKDROP = readBackdrop(canvas.parentElement || canvas);
    var flat = !!gl.getExtension("OES_standard_derivatives");
    var program = gl.createProgram();
    gl.attachShader(program, compile(gl, gl.VERTEX_SHADER, flat ? VERTEX_FLAT : VERTEX_ATTR));
    gl.attachShader(program, compile(gl, gl.FRAGMENT_SHADER, flat ? FRAGMENT_FLAT : FRAGMENT_ATTR));
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) return null;
    var at = {
      position: gl.getAttribLocation(program, "aPosition"),
      normal: gl.getAttribLocation(program, "aNormal"),
      view: gl.getUniformLocation(program, "uView"),
      projection: gl.getUniformLocation(program, "uProjection"),
      normalMatrix: gl.getUniformLocation(program, "uNormal")
    };
    gl.useProgram(program);
    gl.uniform3fv(gl.getUniformLocation(program, "uKey"), KEY);
    gl.uniform3fv(gl.getUniformLocation(program, "uBase"), BASE);
    gl.uniform1f(gl.getUniformLocation(program, "uAmbient"), AMBIENT);
    gl.uniform1f(gl.getUniformLocation(program, "uFill"), FILL);
    gl.enable(gl.DEPTH_TEST);

    var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)");
    var buffers = null;
    var mesh = null;
    var lost = false;
    var frame = 0;
    var spin = 0;
    var width = 0;
    var height = 0;
    var view = { azimuth: HOME_AZIMUTH, elevation: HOME_ELEVATION, target: [0, 0, 0], halfHeight: 1 };

    function basis() {
      var ce = Math.cos(view.elevation);
      var toEye = [ce * Math.cos(view.azimuth), ce * Math.sin(view.azimuth), Math.sin(view.elevation)];
      var right = normalize(cross([-toEye[0], -toEye[1], -toEye[2]], [0, 0, 1]));
      var up = cross(right, [-toEye[0], -toEye[1], -toEye[2]]);
      return { right: right, up: up, toEye: toEye };
    }

    function centre() {
      return [0, 1, 2].map(function (axis) { return (mesh.min[axis] + mesh.max[axis]) / 2; });
    }

    // Tight-fits the mesh's actual projected outline, not its axis-aligned
    // box's eight corners: mesh_render.py's still frames the true outline of
    // whatever triangles project outermost, and an arbitrary shape's outline
    // sits inside its box's, usually well inside. Fitting to the box instead
    // would leave more margin than the still has and the swap would visibly
    // shrink the mesh. `immediate` renders this frame synchronously, so a
    // caller can reveal the canvas only once real pixels are in it.
    function home(immediate) {
      if (!mesh) return;
      view.azimuth = HOME_AZIMUTH;
      view.elevation = HOME_ELEVATION;
      var axes = basis();
      var pos = mesh.positions;
      var lowX = Infinity, highX = -Infinity, lowY = Infinity, highY = -Infinity;
      for (var i = 0; i < pos.length; i += 3) {
        var rx = pos[i] * axes.right[0] + pos[i + 1] * axes.right[1] + pos[i + 2] * axes.right[2];
        var ry = pos[i] * axes.up[0] + pos[i + 1] * axes.up[1] + pos[i + 2] * axes.up[2];
        if (rx < lowX) lowX = rx;
        if (rx > highX) highX = rx;
        if (ry < lowY) lowY = ry;
        if (ry > highY) highY = ry;
      }
      // The AABB centre anchors depth (which axis-aligned box this is does
      // not affect what is on screen); the tight outline's own centre places
      // it left-right and up-down, exactly as mesh_render.py's `mid` does.
      var boxCentre = centre();
      var target = add(
        add(boxCentre, axes.right, (lowX + highX) / 2 - dot(boxCentre, axes.right)),
        axes.up, (lowY + highY) / 2 - dot(boxCentre, axes.up)
      );
      view.target = target;
      var halfX = Math.max((highX - lowX) / 2, 1e-6);
      var halfY = Math.max((highY - lowY) / 2, 1e-6);
      var aspect = width && height ? width / height : 1;
      view.halfHeight = Math.max(halfY, halfX / aspect, 1e-6) / (1 - 2 * MARGIN);
      if (immediate) render(); else draw();
    }

    function draw() {
      if (!frame) frame = window.requestAnimationFrame(render);
    }

    function render() {
      if (frame) { window.cancelAnimationFrame(frame); }
      frame = 0;
      if (lost || !width || !height) return;
      gl.viewport(0, 0, canvas.width, canvas.height);
      gl.clearColor(BACKDROP[0], BACKDROP[1], BACKDROP[2], 1);
      gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
      if (!buffers) return;
      var axes = basis();
      var radius = Math.hypot(mesh.max[0] - mesh.min[0], mesh.max[1] - mesh.min[1], mesh.max[2] - mesh.min[2]) / 2 || 1;
      var drift = Math.hypot.apply(null, centre().map(function (value, axis) { return value - view.target[axis]; }));
      var distance = 3 * radius + drift;
      var eye = add(view.target, axes.toEye, distance);
      var r = axes.right;
      var u = axes.up;
      var d = axes.toEye;
      gl.uniformMatrix4fv(at.view, false, [
        r[0], u[0], d[0], 0, r[1], u[1], d[1], 0, r[2], u[2], d[2], 0,
        -dot(r, eye), -dot(u, eye), -dot(d, eye), 1
      ]);
      gl.uniformMatrix3fv(at.normalMatrix, false, [r[0], u[0], d[0], r[1], u[1], d[1], r[2], u[2], d[2]]);
      var near = radius;
      var far = distance + 2 * radius + drift;
      var halfWidth = view.halfHeight * width / height;
      gl.uniformMatrix4fv(at.projection, false, [
        1 / halfWidth, 0, 0, 0, 0, 1 / view.halfHeight, 0, 0,
        0, 0, -2 / (far - near), 0, 0, 0, -(far + near) / (far - near), 1
      ]);
      gl.bindBuffer(gl.ARRAY_BUFFER, buffers.position);
      gl.vertexAttribPointer(at.position, 3, gl.FLOAT, false, 0, 0);
      gl.enableVertexAttribArray(at.position);
      if (buffers.normal && at.normal >= 0) {  // the flat program has none
        gl.bindBuffer(gl.ARRAY_BUFFER, buffers.normal);
        gl.vertexAttribPointer(at.normal, 3, gl.FLOAT, false, 0, 0);
        gl.enableVertexAttribArray(at.normal);
      }
      gl.drawArrays(gl.TRIANGLES, 0, mesh.count * 3);
    }

    function release() {
      window.cancelAnimationFrame(spin);
      spin = 0;
      if (buffers && !lost) {
        gl.deleteBuffer(buffers.position);
        if (buffers.normal) gl.deleteBuffer(buffers.normal);
      }
      buffers = null;
      mesh = null;
    }

    function upload(data) {
      var buffer = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
      gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW);
      return buffer;
    }

    // Pointer: one gesture at a time, captured so a drag may leave the box.
    var drag = null;
    function turn(dx, dy) {
      view.azimuth -= dx * 0.01;
      view.elevation = Math.max(-ELEVATION_LIMIT, Math.min(ELEVATION_LIMIT, view.elevation + dy * 0.01));
    }
    function pan(dx, dy) {
      var axes = basis();
      var perPixel = 2 * view.halfHeight / height;
      view.target = add(add(view.target, axes.right, -dx * perPixel), axes.up, dy * perPixel);
    }
    canvas.addEventListener("pointerdown", function (event) {
      if (!mesh) return;
      window.cancelAnimationFrame(spin);
      spin = 0;
      var panning = event.button === 2 || event.button === 1 || event.shiftKey;
      drag = { pan: panning, x: event.clientX, y: event.clientY, vx: 0, vy: 0, t: performance.now() };
      try { canvas.setPointerCapture(event.pointerId); } catch (error) { /* a synthetic pointer */ }
      event.preventDefault();
    });
    canvas.addEventListener("pointermove", function (event) {
      if (!drag) return;
      var dx = event.clientX - drag.x;
      var dy = event.clientY - drag.y;
      var now = performance.now();
      drag.vx = dx / Math.max(now - drag.t, 1);
      drag.vy = dy / Math.max(now - drag.t, 1);
      drag.x = event.clientX;
      drag.y = event.clientY;
      drag.t = now;
      if (drag.pan) pan(dx, dy); else turn(dx, dy);
      draw();
    });
    function endDrag(event) {
      if (!drag) return;
      var last = drag;
      drag = null;
      if (canvas.hasPointerCapture(event.pointerId)) canvas.releasePointerCapture(event.pointerId);
      // A flick keeps turning and slows down, unless motion is reduced.
      if (last.pan || (reduceMotion && reduceMotion.matches)) return;
      if (performance.now() - last.t > 60 || Math.hypot(last.vx, last.vy) < 0.2) return;
      var vx = Math.max(-COAST_LIMIT, Math.min(COAST_LIMIT, last.vx * 16));
      var vy = Math.max(-COAST_LIMIT, Math.min(COAST_LIMIT, last.vy * 16));
      (function coast() {
        vx *= 0.92;
        vy *= 0.92;
        if (!mesh || Math.hypot(vx, vy) < 0.3) { spin = 0; return; }
        turn(vx, vy);
        render();
        spin = window.requestAnimationFrame(coast);
      })();
    }
    canvas.addEventListener("pointerup", endDrag);
    canvas.addEventListener("pointercancel", endDrag);
    canvas.addEventListener("contextmenu", function (event) { event.preventDefault(); });
    canvas.addEventListener("dblclick", function (event) { event.preventDefault(); home(); });
    canvas.addEventListener("wheel", function (event) {
      if (!mesh) return;
      event.preventDefault();
      var box = canvas.getBoundingClientRect();
      var sx = ((event.clientX - box.left) / box.width) * 2 - 1;
      var sy = 1 - ((event.clientY - box.top) / box.height) * 2;
      var step = event.deltaMode === 1 ? event.deltaY * 16 : event.deltaY;
      var before = view.halfHeight;
      view.halfHeight = before * Math.exp(Math.max(-1, Math.min(1, step * 0.0015)));
      // Keep the point under the pointer where it is.
      var axes = basis();
      var shrink = before - view.halfHeight;
      view.target = add(add(view.target, axes.right, sx * shrink * width / height), axes.up, sy * shrink);
      draw();
    }, { passive: false });

    canvas.addEventListener("webglcontextlost", function (event) {
      event.preventDefault();
      lost = true;
      buffers = null;
      if (options.onLost) options.onLost();
    });

    return {
      show: function (next) {
        release();
        if (lost) return false;
        mesh = next;
        buffers = { position: upload(next.positions), normal: next.normals ? upload(next.normals) : null };
        // Renders this first frame now, in place, rather than waiting for the
        // next animation frame: the caller reveals the canvas only after this
        // returns, so nothing empty or stale is ever shown mid-swap.
        home(true);
        return true;
      },
      resize: function (cssWidth, cssHeight) {
        width = Math.max(0, Math.floor(cssWidth));
        height = Math.max(0, Math.floor(cssHeight));
        var ratio = window.devicePixelRatio || 1;
        canvas.style.width = width + "px";
        canvas.style.height = height + "px";
        canvas.width = Math.max(1, Math.round(width * ratio));
        canvas.height = Math.max(1, Math.round(height * ratio));
        draw();
      },
      clear: release,
      home: home
    };
  }

  window.PihtiViewer3D = { supported: supported, create: create, fetchMesh: fetchMesh, parse: parse };
})();
