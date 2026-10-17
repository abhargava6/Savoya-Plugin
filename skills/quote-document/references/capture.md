# Capture

Loaded at the capture step, after the final deliverable.

**Two moments, not one.**

**A session that cannot produce a document still reports (R80).** If the document flow stops — the data could not be saved, a check refused, the user chose email only and nothing verified — run `capture_session.py --blocked "<one sentence: what stopped it>" --slug <slug> --client "<Client>" --request handoff/request.md` before the last reply. It needs no `quote.json`. It carries the request, what was priced (from `handoff/responses/`) and the reason. Consent works exactly as above: `CAPTURE CONSENT UNASKED` means ask once, `declined` means nothing is written. A written record goes up like any other, titled `<slug>.blocked.json`, then `--mark-uploaded`. Say nothing to the user beyond the consent question.

**One-time consent (R76).** The first document a user verifies on a machine prints `CAPTURE CONSENT UNASKED`. Ask the question it carries once, before presenting the files, in your own words, with their name for filing: record the answer with `capture_session.py --consent yes|no --user "<Name>"` and re-run verify. It is never asked again. On *no*, verify prints `CAPTURE SKIPPED` and the session says nothing; nothing is written or uploaded.

1. **Every delivered document — a render snapshot.** `verify_document.py … --capture-slug <slug> --capture-client <Client>` runs the capture with `--auto` the moment verification passes (PASS or PARTIAL; a FAIL writes nothing) and leaves the `.pending-upload` marker. Upload **both** files it lists and run `--mark-uploaded` BEFORE presenting the files (R63). Run the capture by hand with `--auto` only if verify was run without `--capture-slug`. This is not optional and does not wait for the feedback exchange: a session where the user takes the PDF and leaves used to vanish without trace, and that is how three client-facing defects reached a CSM before anyone here heard about them. Silent, no comment to the user.

   The full capture goes up on **this** pass, not just the later one. It used to be held back to keep this pass to a single Drive call — and on 10 Oct 2026 a live London/Sicily/Milan quote delivered its PDF, uploaded the snapshot, never asked the feedback question, and the full capture reached the folder only because the user asked for it by name. Compressed it is around 8 KB; the saved call is not worth a lost capture.
2. **After the feedback exchange** — re-run for the same slug with `--worked` / `--change` / `--fixed` filled in. It supersedes the snapshot with the richer record and uploads both again under their own titles (`<slug>.feedback.json` and `<slug>.capture.json.gz.b64`, against the snapshot's `.feedback.snapshot.json` and `.capture.snapshot.json.gz.b64`). Drive's `create_file` always creates, so the separate titles are what stop the normal flow leaving two files with one name on every quote.

A revision does not earn a new slug; the script overwrites by design. Only pass `--new-version` if the user explicitly wants a second record kept.

The script prints an `upload` list. **Upload exactly what it lists, nothing else.** The full capture is compressed, so it is always in that list and always fits one call — a 192 KB capture goes up as 17 KB. **Never split a capture across multiple uploads**; a 12-part upload is worse than no upload.

There used to be a 25 KB ceiling above which the full capture stayed local. It is gone, and it is worth knowing why: on 10 Oct 2026 the two largest captures of the day — a 16-leg World Cup quote and a 6-leg London/Sicily/Milan one — both failed that test, stayed in a container, and were gone when it was reclaimed. The richest sessions were precisely the ones that never arrived.

Run it after the final deliverable of the document flow — after the PDF and email are delivered in the same reply — with `--deliverable "<all formats produced>"`. It includes everything intake decided (`handoff/intake.json` is read automatically). Don't capture per format, don't capture in intake when a document follows, and don't re-upload after a revision unless the user asks for a re-render — then one more, versioned.

**The Drive tool should already be loaded** — Stage 0 of `SKILL.md` loads it with the machine check, precisely so that it is not a fresh setup step here. If it isn't loaded, load it once now (`tool_search "Google Drive create_file"`), not per upload. Not having loaded it is not a reason to skip the upload: three live sessions in a row ended with the capture written locally and never sent, one of them saying so outright.

**First deliverable in a conversation — identity.** Read `~/.savoya-quoting/config.json`. If it has no `user`, ask once: *"Quick one so captures are attributed — what name should I record you as?"* and write `{"user": "<name>"}` to that file. Don't ask again in later conversations.

**Then, for each deliverable:**

1. Write the client's original message to `request.md` verbatim if you haven't already (it becomes the eval prompt later).
2. Run the capture:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/quote-document/scripts/capture_session.py --slug "<client>-<event>" --client "<Client>" \
     --deliverable pdf --request request.md --raw raw_quote.json --quote quote.json \
     --select <keys> [--auto] [--worked "…" --change "…" --fixed "…"] [--workaround "…"]
   ```
   Pass `--pdf <the delivered PDF>` whenever there is one, so `expected.pdf_pages` is
   measured. Without it the key is left out, which is correct — it used to be the literal
   `3` on every capture, while real deliverables were 4, 5 and 8 pages.

   **Upload the real file, exactly (R94).** The script prints each file's byte count and SHA-256 and the instruction `upload_exactly`. Read the file and pass its whole text as `textContent`. Never retype, shorten or summarize a record, a blocked one included: a condensed copy of a blocked log is a record that hides what a replay would show. The blocked record goes up packed (`<slug>.blocked.json.gz.b64`) for that reason: it cannot be summarized, only uploaded or not. `unpack_capture.py` checks the hash.

   **The script writes files. It has no Drive access and uploads nothing.** Its output
   opens with `status: NOTHING IS UPLOADED YET` for a reason: a session ran the capture,
   read the output as a completion summary and stopped there — *"I treated the local save
   as the end of the step"* — and the only channel back from a live quote went quiet
   again. **The capture step is not done until Drive has returned an `id` for every file
   in `upload`.**

   Then record it, with the ids Drive gave you:

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/quote-document/scripts/capture_session.py \
     --mark-uploaded "<slug>" --file-id <id> [--file-id <id>]
   ```

   Do **not** try to delete the marker with `rm` — the auto-mode classifier denies it, and
   on 10 Oct 2026 that left a capture that *had* been uploaded still counted as
   outstanding, so the line shown to the user ("that's 4 sessions now…") stated a number
   that was not true. `--mark-uploaded` refuses to run without a Drive id, so it cannot be
   used to tidy the backlog without an upload behind it. If
   `earlier_captures_never_uploaded` is above zero, upload those too — the paths are
   inside each `*.pending-upload` file.

   **`local_copy.durable: false` means the local copy is not a fallback.** `~` is this
   session's own storage: a cloud container on claude.ai, and an isolated VM on a linked
   desktop — only a connected folder is really the user's disk. When the session has a
   folder connected to the user's computer, pass `--dir` inside it and the capture
   survives the session. When it does not, Drive is the only durable destination, so the
   upload is not optional and the line in step 3 is not a formality.

3. **If Drive isn't available or the upload fails — ASK, don't just mention it.** This used to be a soft line that the user could do nothing with in the moment, and it is how three sessions in a row ended with the record stranded. The user is the only one who can switch the connector on, so give them the chance while the session is still alive, with `ask_user_input_v0`:

   > *"I couldn't save this session's record to the team folder — the Google Drive connection isn't switched on. That record is how the quoting tool gets fixed, so it's worth a minute."*
   >
   > - **I've turned it on — try again**
   > - **Skip it this time**

   On *try again*: load the tool if needed, retry the upload, and if it works carry on silently — no further comment. On *skip*, or if they don't answer, say one line and move on. **Never show them a file path, a script, a command or a connector id** — "the Google Drive connection, in your settings" is the whole explanation a CSM gets.

   Ask **once** per session, after the deliverable, never before it. A quote is the user's actual business; the record is ours, and it never delays their document.

   Make it concrete by naming the backlog — run `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/scripts/setup_check.py` for the count:

   > *"Saved locally again — that's 4 sessions now that haven't reached the team folder."*

   It stops the moment an upload succeeds. If they ask what to do about it, that's the setup check: `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/references/setup-check.md`.

   **A connector that is switched on can still fail to write.** Their Drive uploads as their own Google account, so without Editor on the shared folder every upload fails while everything looks connected. That is the setup check's job to prove, not yours to assume.

   Otherwise, upload the file with the Google Drive connector — `create_file` with `title` from the output, `textContent` = the file's contents, `contentMimeType: application/json`, `disableConversionToGoogleType: true`, `parentId` = `drive_folder_id`. Do this silently; it's part of producing the deliverable, not a separate action the user needs to approve. **Check the result has an `id`.** If it doesn't, retry once; if it still fails, that is the ask in step 3 — a connector switched on but without Editor on the shared folder fails exactly like one that is off, and the user is the only one who can fix either. Leave the local copy either way; `${CLAUDE_PLUGIN_ROOT}/skills/quote-document/scripts/export_captures.py` zips it for hand-off later.
4. Versioning: the two runs above already carry different titles — the render snapshot
   goes up as `<slug>.feedback.snapshot.json` and the post-feedback run as
   `<slug>.feedback.json` — so the normal flow no longer leaves two files with one name
   in the folder, which it used to do on *every* quote. The full capture goes up as
   `<slug>.capture.json.gz.b64`; it is a JSON envelope whose header reads plainly and
   whose `data` is the gzipped capture, and `unpack_capture.py` reverses it. The script
   overwrites the same slug locally; pass `--new-version` only when the user explicitly
   wants a second, separate record of the same quote. (There is no `--version N` flag —
   an earlier version of this file named one, and passing it stops the capture dead.)
5. Say nothing else about the capture. The user asked for a quote, not a report on telemetry.

**Record your own workarounds — in `--workaround`, never `--change`.** If you did anything outside the documented path — hand-edited legs, restructured units, patched a renderer, drew a map another way, guessed a value — put it in `--workaround`, on the render snapshot, at the moment you do it. Claude's own notes have been the most useful signal so far, and they must stay in their own field: `--change` is reserved for the user's words. Mixing them makes it impossible to tell a CSM's request from a defect Claude quietly patched, and that distinction is the whole point of the weekly pass.

**Feedback — ask, fix, then log.** The reply that delivers the *first* document ends with this line, verbatim: *"Anything you'd like changed?"* Then:

1. **They name something** → fix it now: adjust, re-render, re-verify, deliver the corrected file. Only then capture, with `--change "<what they asked for>"` **and `--fixed "<what you did>"`** so the weekly pass can tell a session-fixable gap from one that needs a plugin change. Say "fixed and logged" — nothing longer.
2. **They say no, or don't answer** → capture without those flags. Don't chase.

Never log a change request without acting on it first. The user gets the fix; the log gets the pattern. When they do tell you something — at any point — re-run the capture for the latest deliverable with `--worked` / `--change` filled in; the versioned capture carries it.

`RULES.md` in this skill folder is the hard-constraint list — read it before rendering. `feedback-archive.md` is the dated history; read it only during the weekly pass.

Before any repackage, `python3 ${CLAUDE_PLUGIN_ROOT}/skills/quote-document/scripts/regress.py --pdf` must be green.
