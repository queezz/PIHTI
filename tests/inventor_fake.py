"""A stand-in for Inventor's automation surface, for `inventor_session` tests.

It mirrors exactly the calls the repair recipe makes: `SoftwareVersion`,
`Documents.Count/Item/Open`, `doc.File.ReferencedFileDescriptors` with
`FullFileName`, `ReferenceMissing`, `ReplaceReference`, `doc.Save2`, and
`doc.Close`, plus the STEP export's `doc.SaveAs(path, True)`, which writes a
small stand-in file (`fail_export` makes it raise, `hang` on "saveas" makes it
stall), and the leftover close's `Application.Views` (`windows` lists the
full paths shown in a window), `View.Document`, and
`doc.ReferencingDocuments` (the loaded documents whose references name it). The "disk" is a dict of referring document -> referenced full
paths; `Save2` writes it back and, when the document exists as a real file,
rewrites that file's bytes the way Inventor would: the new name added, the old
one left behind as a fossil string.
"""

from __future__ import annotations

import ntpath
import os
import threading
from pathlib import Path
from types import SimpleNamespace

from pihti_dedup.inventor_session import Session


def key(path) -> str:
    return ntpath.normpath(str(path)).casefold()


def reference_bytes(*stored_paths: str) -> bytes:
    payload = bytearray(b"\xde\xad" * 4)
    for stored in stored_paths:
        payload += b"\x00\x00" + stored.encode("utf-16-le") + b"\x00\x00"
    return bytes(payload)


class FakeDescriptor:
    def __init__(self, document: FakeDocument, index: int) -> None:
        self._document = document
        self._index = index

    @property
    def FullFileName(self) -> str:  # noqa: N802 - Inventor's own name
        return self._document.references[self._index]

    @property
    def ReferenceMissing(self) -> bool:  # noqa: N802
        return not os.path.exists(self.FullFileName)

    def ReplaceReference(self, new_path: str) -> None:  # noqa: N802
        app = self._document.app
        app.log.append(("replace", self._document.name, ntpath.basename(new_path)))
        app.maybe_hang("replace", self._document.FullFileName)
        self._document.references[self._index] = str(new_path)


class FakeCollection:
    def __init__(self, items) -> None:
        self._items = list(items)

    @property
    def Count(self) -> int:  # noqa: N802
        return len(self._items)

    def Item(self, position: int):  # noqa: N802 - one-based, as in Inventor
        return self._items[position - 1]


class FakeDocument:
    def __init__(self, app: FakeInventor, full_name: str, *, owner: bool = False) -> None:
        self.app = app
        self.FullFileName = str(full_name)
        self.name = ntpath.basename(self.FullFileName)
        self.owner = owner
        self.references = list(app.disk.get(key(full_name), ()))

    @property
    def File(self):  # noqa: N802
        return SimpleNamespace(
            ReferencedFileDescriptors=FakeCollection(
                FakeDescriptor(self, index) for index in range(len(self.references))
            )
        )

    @property
    def ReferencingDocuments(self):  # noqa: N802
        return FakeCollection(
            document
            for document in self.app.loaded
            if document is not self
            and any(key(item) == key(self.FullFileName) for item in document.references)
        )

    def Save2(self, save_dependents: bool) -> None:  # noqa: N802
        app = self.app
        app.log.append(("save", self.name, save_dependents))
        if self.owner:
            app.violations.append(("save", self.name))
        app.maybe_hang("save", self.FullFileName)
        if key(self.FullFileName) in app.fail_save:
            raise RuntimeError("the file is read-only")
        if key(self.FullFileName) in app.lose_save:
            return
        before = list(app.disk.get(key(self.FullFileName), ()))
        app.disk[key(self.FullFileName)] = list(self.references)
        target = Path(self.FullFileName)
        if target.is_file():
            # Inventor keeps stale strings around: the old name survives as a fossil.
            target.write_bytes(reference_bytes(*self.references, *before))

    def SaveAs(self, full_name: str, save_copy_as: bool) -> None:  # noqa: N802
        app = self.app
        app.log.append(("saveas", self.name, ntpath.basename(full_name), save_copy_as))
        if self.owner:
            app.violations.append(("saveas", self.name))
        app.maybe_hang("saveas", self.FullFileName)
        if key(self.FullFileName) in app.fail_export:
            raise RuntimeError("the translator failed")
        Path(full_name).write_bytes(b"ISO-10303-21; /* " + self.name.encode() + b" */")

    def Close(self, skip_save: bool) -> None:  # noqa: N802
        app = self.app
        app.log.append(("close", self.name, skip_save))
        if self.owner:
            app.violations.append(("close", self.name))
        if key(self.FullFileName) in app.fail_close:
            raise RuntimeError("the document is busy")
        app.loaded = [document for document in app.loaded if document is not self]


class FakeDocuments:
    def __init__(self, app: FakeInventor) -> None:
        self._app = app

    @property
    def Count(self) -> int:  # noqa: N802
        return len(self._app.loaded)

    def Item(self, position: int) -> FakeDocument:  # noqa: N802
        return self._app.loaded[position - 1]

    def Open(self, full_name: str, visible: bool) -> FakeDocument:  # noqa: N802
        app = self._app
        app.log.append(("open", ntpath.basename(full_name), visible))
        app.maybe_hang("open", full_name)
        for document in app.loaded:
            if key(document.FullFileName) == key(full_name):
                if document.owner:
                    app.violations.append(("open", document.name))
                return document
        if key(full_name) not in app.disk:
            raise RuntimeError(f"cannot open {full_name}")
        document = FakeDocument(app, full_name)
        app.loaded.append(document)
        return document


class FakeInventor:
    """`disk` maps a referring document's full path to its referenced full paths."""

    def __init__(self, disk: dict, *, owner_open=(), version: str = "2027.1") -> None:
        self.disk = {key(path): [str(item) for item in refs] for path, refs in disk.items()}
        self.SoftwareVersion = SimpleNamespace(DisplayVersion=version)
        self.Documents = FakeDocuments(self)
        self.log: list[tuple] = []
        self.violations: list[tuple] = []
        self.fail_save: set[str] = set()
        self.lose_save: set[str] = set()
        self.fail_export: set[str] = set()
        self.fail_close: set[str] = set()
        #: Full paths shown in a window; `Views` answers from this.
        self.windows: list[str] = []
        self.hang: tuple[str, str] | None = None
        self.release = threading.Event()
        self.loaded: list[FakeDocument] = [
            FakeDocument(self, path, owner=True) for path in owner_open
        ]

    @property
    def Views(self):  # noqa: N802
        return FakeCollection(
            SimpleNamespace(Document=SimpleNamespace(FullFileName=str(path)))
            for path in self.windows
        )

    def maybe_hang(self, action: str, full_name: str) -> None:
        if self.hang and self.hang[0] == action and self.hang[1] == key(full_name):
            self.log.append(("hang", ntpath.basename(full_name)))
            self.release.wait(10)

    def ours(self) -> list[str]:
        """Documents this code opened and left loaded."""

        return [document.name for document in self.loaded if not document.owner]


def fake_session(app: FakeInventor) -> Session:
    return Session(lambda: app, version=str(app.SoftwareVersion.DisplayVersion))
