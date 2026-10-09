# Setup check

Run when the user asks anything like *"check my quoting setup"*, *"is this working?"*,
*"why isn't my stuff saving?"* — and once, unprompted, the first time you ever work with
someone whose name isn't recorded yet.

**Why this exists.** A CSM could complete setup, believe they were done, quote for weeks,
and nothing would reach the shared folder — with no symptom on either side. Everything the
capture does to report a problem happens *after* the capture script runs, so a missing
connector, a missing folder permission or a crashed capture all produced the same thing:
silence for the CSM, an empty folder for whoever owns the improvement loop. This check is
the only thing that closes that gap, so it has to actually call the connectors rather than
assume them.

## 1. The local half

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/quote-document/scripts/setup_check.py
```

It prints a CSM-readable summary and a `<<<setup-check … setup-check>>>` block for you.
Read the block; show the summary.

## 2. Savoya

The quoting connector is proven by use, not by inspection. If `resolve_client` and the
other Savoya tools are in this session, it is connected. If they are not there at all, that
is the one failure that stops everything:

> "The Savoya connection isn't switched on in this chat, so I can't price anything yet.
> It's in Claude's settings under connectors — sign in with your Savoya account."

If the tools are present but a call comes back refused, the account is missing the
`access:savoya_mcp` permission. Say that plainly and offer to note it for engineering.

## 3. Google Drive — connected is not the same as working

Two distinct failures, and they need different answers, so test for both:

**Is the connector there at all?** If no Google Drive tool is available in this session:

> "Your saved sessions aren't reaching the team folder — the Google Drive connection isn't
> switched on. It's in Claude's settings under connectors. Everything still works without
> it; it just means the people improving this tool never see what you ran into."

**Can it actually write to the folder?** This is the one that bites, because a CSM who
turned the connector on reasonably believes they are done. Their Drive uploads as *their
own* Google account, so without **Editor** on the shared folder every upload fails. Prove
it rather than assuming: create one small file in the folder named
`setup-ok-<name>-<YYYY-MM-DD>.json`, `parentId` = `drive_folder_id` from
`${CLAUDE_PLUGIN_ROOT}/skills/quote-document/assets/capture.json`, content
`{"setup_check": true, "user": "<name>", "plugin_version": "<version>"}`.

- **It returns an id** → working. Say so in one line. Leave the file: it is how the person
  who owns the folder can see at a glance whose setup is verified.
- **It fails** → the connector is on but this account cannot write to the folder:

  > "Your Drive is connected, but this account can't write to the team folder yet — it
  > needs Editor access rather than view-only. Whoever set the folder up can add you; I can
  > draft that message if it helps."

## 4. Report it as a status, not a diagnosis

Three or four plain lines, in this order: whether quoting works, whether saving works, and
anything worth doing. Never show a path, a command, a folder id or a script name. If
something needs IT, offer to write the message rather than explaining the fix.

A good report:

> Quoting is connected and working. Saved sessions are recorded under your name. They're
> reaching the team folder — I just confirmed by writing a test entry.
>
> One thing: 3 earlier sessions on this computer never made it to the folder, from before
> Drive was connected. Nothing is lost, they're still here.

## 5. The nudge, while Drive is unreachable

The old rule was to mention a missing Drive **once**. That is how this went unnoticed for
weeks: one soft line in one session, with nobody downstream any the wiser. While Drive is
unreachable, say one line **every** session that delivers a document, and make it concrete
by naming the backlog from the local half:

> "Saved locally again — that's 4 sessions now that haven't reached the team folder."

One line, at the end, after the deliverable. Never a paragraph, never a warning banner,
never before the thing they asked for. It stops the moment an upload succeeds.
