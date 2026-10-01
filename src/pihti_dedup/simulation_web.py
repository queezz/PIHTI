"""Dedicated simulation STEP viewer routes, registered by the CAD application."""

from __future__ import annotations

import hashlib
import importlib.util
import io
from collections import OrderedDict
from pathlib import Path

from flask import Blueprint, abort, jsonify, render_template, request, send_file

from pihti_dedup import __version__
from pihti_dedup import simulation_step as prep


def register(app, root, mirror, guard):
    views = Blueprint("simulation", __name__)
    cache = OrderedDict()

    def source_path(source):
        if not source or "\\" in source:
            abort(404)
        path = (root / source).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            abort(404)
        if path.suffix.lower() in {".ipt", ".iam"}:
            stat = path.stat()
            target = mirror.current_step(source, stat.st_mtime_ns, stat.st_size)
            if target is None:
                raise ValueError("This file needs a current STEP mirror. Re-export it first.")
            target = target.resolve()
            if not target.is_relative_to(mirror.root.resolve()):
                abort(404)
            return target
        if path.suffix.lower() in {".step", ".stp"}:
            return path
        abort(404)

    def load(source, with_mesh=False):
        path = source_path(source)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        key = (source, digest)
        with prep.OCC_LOCK:
            if key not in cache:
                cache[key] = [prep.read_parts(path, source), None, None]
                while len(cache) > 2:
                    cache.popitem(last=False)
            cache.move_to_end(key)
            record = cache[key]
            if with_mesh and record[1] is None:
                record[1], record[2] = prep.mesh(record[0])
            return record, digest

    @views.get("/simulation")
    def page():
        sources = []
        if mirror.root.is_dir():
            for step in sorted(mirror.root.rglob("*.step")):
                relative = step.relative_to(mirror.root).as_posix()
                source = relative[:-5]
                if source.lower().endswith((".ipt", ".iam")) and (root / source).is_file():
                    sources.append(source)
        from pihti_dedup.inventory import scan_workspace

        sources.extend(
            record.path
            for record in scan_workspace(
                root, hash_files=False, extensions={".step", ".stp"}
            ).records
        )
        sources = sorted(set(sources))
        return render_template(
            "simulation.html",
            workspace=root.name,
            version=__version__,
            sources=sources,
            roles=prep.ROLES,
            available=bool(importlib.util.find_spec("OCP")),
            form_token=app.config["FORM_TOKEN"],
        )

    @views.get("/simulation/model")
    def model():
        try:
            source = request.args.get("source", "")
            record, digest = load(source, True)
            mapping = prep.read_map(root)
            rows = prep.public_parts(record[0], mapping)
            for row, span in zip(rows, record[2], strict=True):
                row.update(span)
            return jsonify(
                parts=rows, source_hash=digest, revision=prep.map_revision(mapping), units="mm"
            )
        except (ValueError, OSError, ImportError) as exc:
            return jsonify(error=str(exc)), 422

    @views.get("/simulation/mesh")
    def mesh():
        try:
            record, digest = load(request.args.get("source", ""), True)
            if request.args.get("hash") != digest:
                return jsonify(error="STEP changed. Reload the model."), 409
            return send_file(io.BytesIO(record[1]), mimetype="application/octet-stream")
        except (ValueError, OSError, ImportError) as exc:
            return jsonify(error=str(exc)), 422

    @views.post("/simulation/map")
    def save():
        refused = guard(request)
        if refused is not None:
            return refused
        payload = request.get_json(silent=True) or {}
        try:
            record, digest = load(payload.get("source", ""))
            if digest != payload.get("source_hash"):
                return jsonify(error="STEP changed. Reload the model."), 409
            part = next((p for p in record[0] if p.key == payload.get("key") and p.stable), None)
            if part is None:
                raise ValueError("This occurrence has no unique stable name.")
            mapping = prep.save_entry(root, part.key, payload.get("entry"), payload.get("revision"))
            return jsonify(revision=prep.map_revision(mapping))
        except (ValueError, OSError, ImportError, TypeError) as exc:
            return jsonify(error=str(exc)), 422

    @views.post("/simulation/export")
    def export():
        refused = guard(request)
        if refused is not None:
            return refused
        try:
            source = request.form.get("source", "")
            record, digest = load(source)
            mapping = prep.read_map(root)
            if digest != request.form.get("source_hash") or prep.map_revision(
                mapping
            ) != request.form.get("revision"):
                raise ValueError("The STEP or map changed. Reload before exporting.")
            with prep.OCC_LOCK:
                output = prep.export_bundle(
                    record[0],
                    mapping,
                    source,
                    digest,
                    strict=request.form.get("purpose") == "simulation",
                )
            return send_file(
                io.BytesIO(output),
                mimetype="application/zip",
                as_attachment=True,
                download_name=Path(source).stem + "-prepared.zip",
            )
        except (ValueError, OSError, ImportError) as exc:
            return jsonify(error=str(exc)), 422

    app.register_blueprint(views)
