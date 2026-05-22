# Git and Pull Request Workflow

Minimum git workflow for students and lab contributors with write access to the
main repository.

This is not a full git tutorial. It is the path that keeps shared CAD work
reviewable.

---

## Clone the main repository

Clone the main PIHTI repository, not a fork, unless you are an external
collaborator without write access.

```bash
git clone https://github.com/queezz/PIHTI.git
cd PIHTI
```

---

## Work on a branch

A branch is a named working copy inside the repository. It lets you make changes
without changing `master` directly.

Do not work directly on `master`. In this repository, `master` is the shared
branch for the current state of the lab archive. Some repositories call this
branch `main`; the idea is the same.

Branches let other people review geometry changes before they become part of
that shared state.

Create a branch before changing files:

```bash
git checkout -b my-feature-branch
```

Use a short name that describes the work, for example:

```text
palp-probe-adapter
pld-window-flange-update
esp32-logger-enclosure
```

---

## Commit your work

After making changes, stage and commit them:

```bash
git add .
git commit -m "Describe the change"
```

Use a message that says what changed and why.

Useful:

```text
Add PALP probe adapter for 2024 flange
```

Not useful:

```text
Updated files
```

Before committing, delete Inventor lock or temporary files if they appear, such
as `.lck` or `~$` files.

---

## Push your branch

Push the branch to GitHub:

```bash
git push -u origin my-feature-branch
```

After the first push, GitHub will usually show a button to open a pull request.

---

## Open a pull request

A pull request is a request to merge your branch into `master`. It gives other
lab members a place to check the change before it becomes part of the shared
repository.

In the pull request, briefly describe:

- What changed
- Why it changed
- Which assembly or subsystem is affected
- Whether the design was fabricated, test-fit, or is still a draft

For geometry changes, include screenshots from Inventor. A rendered view or
highlighted screenshot is much easier to review than a binary `.iam` diff.

For major assemblies, export a STEP file when the design is substantially
complete or has been fabricated. Put it next to the assembly so people can
inspect the geometry without Inventor.

---

## Usual workflow

```bash
git checkout -b my-feature-branch
git add .
git commit -m "Describe the change"
git push -u origin my-feature-branch
```

Then open a pull request on GitHub and ask a supervisor or collaborator to
review it.
