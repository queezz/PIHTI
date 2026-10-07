"""Dedicated simulation STEP viewer routes, registered by the CAD application."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import tempfile
from collections import OrderedDict
from pathlib import Path

from flask import Blueprint, abort, jsonify, render_template, request, send_file

from pihti_dedup import __version__, mesh_cache
from pihti_dedup import simulation_step as prep
from pihti_dedup.cache_root import cache_root
from pihti_dedup.display_worker import DisplayJobs, DisplayPending


class DisplayRefusal(ValueError):
    """A file-state-specific geometry limit already measured on this machine."""


def _store_display(target, payload):
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(payload)
    try:
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def register(app, root, mirror, guard, *, background=False):
    views = Blueprint("simulation", __name__)
    cache = OrderedDict()
    display_store = cache_root(root) / "appearance-meshes"
    jobs = DisplayJobs(root, mirror.root) if background else None
    app.extensions["pihti_display_jobs"] = jobs

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

    def load(source, with_mesh=False, payload=True, prepared=False):
        path = source_path(source)
        if with_mesh:
            # Display geometry survives navigation, the two-shape OCC LRU and
            # service restarts. Saved overrides are applied separately below.
            stat = path.stat()
            stamp = hashlib.sha256(
                f"appearance-v1:{mesh_cache.MAX_TRIANGLES}:{source}:{path}:{stat.st_mtime_ns}:{stat.st_size}".encode()
            ).hexdigest()
            metadata = display_store / stamp[:2] / (stamp + ".json")
            binary = metadata.with_suffix(".mesh")
            try:
                saved = json.loads(metadata.read_text(encoding="utf-8"))
                if "error" in saved:
                    raise DisplayRefusal(saved["error"])
                parts = [prep.Part(shape=None, **part) for part in saved["parts"]]
                if not binary.is_file():
                    raise ValueError("missing cached mesh")
                return [parts, binary.read_bytes() if payload else None, saved["ranges"]], saved[
                    "digest"
                ]
            except DisplayRefusal:
                raise
            except (OSError, ValueError, KeyError, TypeError):
                pass
            if jobs is not None:
                if prepared:
                    raise ValueError("STEP display cache could not be read")
                jobs.prepare(stamp, source)
                # A completed worker writes the same persistent display cache.
                if not metadata.is_file():
                    raise ValueError("STEP changed. Reload the model.")
                return load(source, with_mesh=True, payload=payload, prepared=True)
            # Single flight: another inspector may have finished while we waited.
            with prep.OCC_LOCK:
                if metadata.is_file():
                    try:
                        saved = json.loads(metadata.read_text(encoding="utf-8"))
                        if "error" in saved:
                            raise DisplayRefusal(saved["error"])
                        if not binary.is_file():
                            raise ValueError("missing cached mesh")
                        parts = [prep.Part(shape=None, **part) for part in saved["parts"]]
                        return [
                            parts,
                            binary.read_bytes() if payload else None,
                            saved["ranges"],
                        ], saved["digest"]
                    except DisplayRefusal:
                        raise
                    except (OSError, ValueError, KeyError, TypeError):
                        pass
                record, digest = load(source)
                try:
                    data, ranges = prep.mesh(record[0])
                except ValueError as exc:
                    if str(exc) == "assembly is too large for the viewer":
                        _store_display(metadata, json.dumps({"error": str(exc)}).encode())
                    raise
                after = path.stat()
                if (after.st_mtime_ns, after.st_size) != (stat.st_mtime_ns, stat.st_size):
                    raise ValueError("STEP changed. Reload the model.")
                saved = {
                    "digest": digest,
                    "ranges": ranges,
                    "parts": [
                        {
                            "key": p.key,
                            "original": p.original,
                            "occurrence": p.occurrence,
                            "colour": p.colour,
                            "stable": p.stable,
                        }
                        for p in record[0]
                    ],
                }
                for target, payload in (
                    (binary, data),
                    (metadata, json.dumps(saved).encode("utf-8")),
                ):
                    _store_display(target, payload)
                return [record[0], data, ranges], digest
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        key = (source, digest)
        with prep.OCC_LOCK:
            if key not in cache:
                cache[key] = [prep.read_parts(path, source), None, None]
                while len(cache) > 2:
                    cache.popitem(last=False)
            cache.move_to_end(key)
            record = cache[key]
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
            record, digest = load(source, True, payload=False)
            mapping = prep.read_map(root)
            rows = prep.public_parts(record[0], mapping)
            for row, span in zip(rows, record[2], strict=True):
                row.update(span)
                entry = mapping["parts"].get(row["key"], {}) if row["stable"] else {}
                if "colour" in entry:
                    row["appearances"] = [
                        {**face, "colour": entry["colour"]} for face in span["appearances"]
                    ]
            response = jsonify(
                parts=rows, source_hash=digest, revision=prep.map_revision(mapping), units="mm"
            )
            response.set_etag(hashlib.sha256(response.get_data()).hexdigest())
            response.headers["Cache-Control"] = "private, no-cache"
            return response.make_conditional(request)
        except DisplayPending:
            response = jsonify(pending=True)
            response.status_code = 202
            response.headers["Retry-After"] = "1"
            response.headers["Cache-Control"] = "no-store"
            return response
        except (ValueError, OSError, ImportError) as exc:
            return jsonify(error=str(exc)), 422

    @views.get("/simulation/mesh")
    def mesh():
        try:
            record, digest = load(request.args.get("source", ""), True)
            if request.args.get("hash") != digest:
                return jsonify(error="STEP changed. Reload the model."), 409
            response = send_file(io.BytesIO(record[1]), mimetype="application/octet-stream")
            response.set_etag(digest + "-appearance-v1")
            response.headers["Cache-Control"] = "private, max-age=31536000, immutable"
            return response.make_conditional(request)
        except DisplayPending:
            response = jsonify(pending=True)
            response.status_code = 202
            response.headers["Retry-After"] = "1"
            response.headers["Cache-Control"] = "no-store"
            return response
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
