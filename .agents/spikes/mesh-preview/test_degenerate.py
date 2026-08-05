"""Degenerate / adversarial input handling for the mesh renderer."""
import struct, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import numpy as np
import meshpreview as mp

tmp = Path(tempfile.mkdtemp(prefix="degen-"))
results = []


def check(name, fn, expect):
    """expect: 'image' or 'EmptyMeshError' or 'error'"""
    try:
        out = fn()
        got = "image" if out is not None else "none"
    except mp.EmptyMeshError as e:
        got = "EmptyMeshError"
    except Exception as e:
        got = f"error:{type(e).__name__}: {e}"[:90]
    ok = got.startswith(expect)
    results.append((ok, name, got))
    print(f"{'PASS' if ok else 'FAIL'}  {name:44} -> {got}")


def bin_stl(path, tris):
    with open(path, "wb") as f:
        f.write(b"\0" * 80)
        f.write(struct.pack("<I", len(tris)))
        for t in tris:
            f.write(struct.pack("<3f", 0, 0, 1))
            for v in t:
                f.write(struct.pack("<3f", *v))
            f.write(b"\0\0")
    return path


R = lambda t: mp.render_triangles(t, size=128, ssaa=1)

# --- empty / trivial -------------------------------------------------
p = bin_stl(tmp / "empty.stl", [])
check("binary STL, zero triangles", lambda: R(mp.load_stl(p)), "EmptyMeshError")

p = tmp / "truncated.stl"
p.write_bytes(b"\0" * 80 + struct.pack("<I", 5000))  # claims 5000, has none
check("binary STL, truncated body", lambda: R(mp.load_stl(p)), "EmptyMeshError")

p = tmp / "notmesh.stl"
p.write_bytes(b"this is not an STL at all")
check("garbage file", lambda: R(mp.load_stl(p)), "EmptyMeshError")

p = tmp / "asciiempty.stl"
p.write_bytes(b"solid foo\nendsolid foo\n")
check("ASCII STL, no facets", lambda: R(mp.load_stl(p)), "EmptyMeshError")

# --- degenerate geometry ---------------------------------------------
p = bin_stl(tmp / "zeroarea.stl", [[(0, 0, 0), (1, 1, 1), (2, 2, 2)]] * 10)
check("all triangles collinear (zero area)", lambda: R(mp.load_stl(p)), "EmptyMeshError")

p = bin_stl(tmp / "point.stl", [[(1, 1, 1), (1, 1, 1), (1, 1, 1)]] * 4)
check("all vertices identical", lambda: R(mp.load_stl(p)), "EmptyMeshError")

nan = float("nan")
p = bin_stl(tmp / "nan.stl", [[(nan, 0, 0), (1, 0, 0), (0, 1, 0)]])
check("NaN coordinates only", lambda: R(mp.load_stl(p)), "EmptyMeshError")

inf = float("inf")
p = bin_stl(tmp / "mixed.stl", [
    [(inf, 0, 0), (1, 0, 0), (0, 1, 0)],       # dropped
    [(0, 0, 0), (1, 0, 0), (0, 1, 0)],         # kept
])
check("one Inf triangle + one good", lambda: R(mp.load_stl(p)), "image")

# --- extreme scale / aspect -------------------------------------------
p = bin_stl(tmp / "tiny.stl", [[(0, 0, 0), (1e-9, 0, 0), (0, 1e-9, 0)]])
check("sub-micron single triangle", lambda: R(mp.load_stl(p)), "image")

p = bin_stl(tmp / "huge.stl", [[(0, 0, 0), (1e9, 0, 0), (0, 1e9, 1e9)]])
check("1e9-scale single triangle", lambda: R(mp.load_stl(p)), "image")

p = bin_stl(tmp / "sliver.stl", [[(0, 0, 0), (1000, 0.001, 0), (0, 0.001, 0)]])
check("extreme sliver aspect ratio", lambda: R(mp.load_stl(p)), "image")

# flat plate exactly edge-on to the camera
p = bin_stl(tmp / "flat.stl", [
    [(0, 0, 0), (10, 0, 0), (10, 10, 0)],
    [(0, 0, 0), (10, 10, 0), (0, 10, 0)],
])
check("perfectly flat plate (planar)", lambda: R(mp.load_stl(p)), "image")

# --- missing files / wrong types --------------------------------------
check("nonexistent path", lambda: mp.render_file(tmp / "nope.stl"), "error:FileNotFoundError")
check("unsupported extension", lambda: mp.render_file(tmp / "x.iam"), "error:ValueError")

# --- direct array paths ------------------------------------------------
check("empty ndarray", lambda: R(np.zeros((0, 3, 3), np.float32)), "EmptyMeshError")
check("single valid triangle", lambda: R(np.array([[[0,0,0],[1,0,0],[0,1,0]]], np.float32)), "image")

print("\n" + "=" * 70)
bad = [r for r in results if not r[0]]
print(f"{len(results)-len(bad)}/{len(results)} passed")
for _, name, got in bad:
    print(f"  FAILED: {name} -> {got}")
