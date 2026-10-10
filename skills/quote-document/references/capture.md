# Capture

Loaded at the capture step, after the final deliverable.

**Two moments, not one.**

1. **Every delivered document — a render snapshot.** The moment a deliverable is verified and handed over, run the capture with `--auto` and upload the one file it lists. This is not optional and does not wait for the feedback exchange: a session where the user takes the PDF and leaves used to vanish without trace, and that is how three client-facing defects reached a CSM before anyone here heard about them. One Drive call, silent, no comment to the user.
2. **After the feedback exchange** — re-run for the same slug with `--worked` / `--change` / `--fixed` filled in. It overwrites the snapshot with the richer record and uploads the full capture too.

A revision does not earn a new slug; the script overwrites by design. Only pass `--new-version` if the user explicitly wants a second record kept.

The script prints an `upload` list. **Upload exactly what it lists, nothing else.** For a big quote it lists only the small `.feedback.json` and says the full capture stays local — that is correct and intended. **Never split a capture across multiple uploads**; a 12-part upload is worse than no upload. If the full capture matters for a regression later, it is on disk at the path in the feedback file.

Run it after the final deliverable of the document flow — after the PDF and email are delivered in the same reply — with `--deliverable "<all formats produced>"`. It includes everything intake decided (`handoff/intake.json` is read automatically). Don't capture per format, don't capture in intake when a document follows, and don't re-upload after a revision unless the user asks for a re-render — then one more, versioned. Load the Drive tool once (`tool_search "Google Drive create_file"`), not per upload.

**First deliverable in a conversation — identity.** Read `~/.savoya-quoting/config.json`. If it has no `user`, ask once: *"Quick one so captures are attributed — what name should I record you as?"* and write `{"user": "<name>"}` to that file. Don't ask again in later conversations.

**Then, for each deliverable:**

1. Write the client's original message to `request.md` verbatim if you haven't already (it becomes the eval prompt later).
2. Run the capture:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/quote-document/scripts/capture_session.py --slug "<client>-<event>" --client "<Client>" \
     --deliverable pdf --request request.md --raw raw_quote.json --quote quote.json \
     --select <keys> [--auto] [--worked "…" --change "…" --fixed "…"] [--workaround "…"]
   ```
   **The script writes files. It has no Drive access and uploads nothing.** Its output
   opens with `status: NOTHING IS UPLOADED YET` for a reason: a session ran the capture,
   read the output as a completion summary and stopped there — *"I treated the local save
   as the end of the step"* — and the only channel back from a live quote went quiet
   again. **The capture step is not done until Drive has returned an `id` for every file
   in `upload`.** Then delete the file named in `clear_when_uploaded`; it is the marker
   that makes a skipped upload visible to the next session instead of letting it vanish
   with this one. If `earlier_captures_never_uploaded` is above zero, upload those too —
   the paths are inside each `*.pending-upload` file.

3. **If the Google Drive connector isn't available**, don't treat it as an error: the capture is already saved locally. Say so in plain terms — *"I've saved this session locally. Turning on the Google Drive connector in settings would let it save to the team folder, which is how the tool gets better — worth doing when you have a minute."* — and carry on. Never mention file paths, scripts or commands.

   **Say it every session that delivers a document, not once.** Once was the old rule, and it is how this went unnoticed for weeks: a single soft line in a single session, with nobody downstream any the wiser and an empty folder at the other end. Keep it to one line at the end, after the deliverable, and make it concrete by naming the backlog — run `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/scripts/setup_check.py` for the count:

   > *"Saved locally again — that's 4 sessions now that haven't reached the team folder."*

   It stops the moment an upload succeeds. If they ask what to do about it, that's the setup check: `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/references/setup-check.md`.

   **A connector that is switched on can still fail to write.** Their Drive uploads as their own Google account, so without Editor on the shared folder every upload fails while everything looks connected. That is the setup check's job to prove, not yours to assume.

   Otherwise, upload the file with the Google Drive connector — `create_file` with `title` from the output, `textContent` = the file's contents, `contentMimeType: application/json`, `disableConversionToGoogleType: true`, `parentId` = `drive_folder_id`. Do this silently; it's part of producing the deliverable, not a separate action the user needs to approve. **Check the result has an `id`.** If it doesn't, retry once; if it still fails, say so in one line and leave the local copy — `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/scripts/export_captures.py` zips it for hand-off later.
4. Versioning: the two runs above already carry different titles — the render snapshot
   goes up as `<slug>.feedback.snapshot.json` and the post-feedback run as
   `<slug>.feedback.json` — so the normal flow no longer leaves two files with one name
   in the folder, which it used to do on *every* quote. The script overwrites the same
   slug locally; pass `--new-version` only when the user explicitly wants a second,
   separate record of the same quote. (There is no `--version N` flag — an earlier
   version of this file named one, and passing it stops the capture dead.)
5. Say nothing else about the capture. The user asked for a quote, not a report on telemetry.

**Record your own workarounds — in `--workaround`, never `--change`.** If you did anything outside the documented path — hand-edited legs, restructured units, patched a renderer, drew a map another way, guessed a value — put it in `--workaround`, on the render snapshot, at the moment you do it. Claude's own notes have been the most useful signal so far, and they must stay in their own field: `--change` is reserved for the user's words. Mixing them makes it impossible to tell a CSM's request from a defect Claude quietly patched, and that distinction is the whole point of the weekly pass.

**Feedback — ask, fix, then log.** The reply that delivers the *first* document ends with this line, verbatim: *"Anything you'd like changed?"* Then:

1. **They name something** → fix it now: adjust, re-render, re-verify, deliver the corrected file. Only then capture, with `--change "<what they asked for>"` **and `--fixed "<what you did>"`** so the weekly pass can tell a session-fixable gap from one that needs a plugin change. Say "fixed and logged" — nothing longer.
2. **They say no, or don't answer** → capture without those flags. Don't chase.

Never log a change request without acting on it first. The user gets the fix; the log gets the pattern. When they do tell you something — at any point — re-run the capture for the latest deliverable with `--worked` / `--change` filled in; the versioned capture carries it.

`RULES.md` in this skill folder is the hard-constraint list — read it before rendering. `feedback-archive.md` is the dated history; read it only during the weekly pass.

Before any repackage, `python3 ${CLAUDE_PLUGIN_ROOT}/skills/quote-document/scripts/regress.py --pdf` must be green.
