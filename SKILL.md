---
name: youtube-studio-cdp-upload
description: Upload a local video to YouTube Studio through an already authenticated browser, set metadata and audience/visibility, and verify the resulting public watch page. Use when a local master must be published to YouTube; not for rendering or editing video.
---

# YouTube Studio CDP Upload

Publish one already-approved local video at a time using the authenticated browser session the operator has made available. The skill does not create a browser session, generate a video, choose a title/description, or authorize publication.

## Preconditions and limits

- Obtain the exact local master path and the requested title, description, audience, and visibility. If any required metadata or visibility is not specified, ask before publishing; do not infer Public from a generic request to upload.
- Confirm the local source is a regular file and inspect its stream/duration metadata before attaching it. Do not upload an intermediate or an unvalidated render.
- Use only the already-running, authenticated Brave instance. Attach to the approved CDP endpoint (normally `127.0.0.1:9222`); never launch a browser, CDP service, profile, or a second browser instance.
- Reuse a single YouTube Studio tab. Keep no more than three YouTube tabs total; open a public watch tab only for verification and close task-created tabs once verified. Never close unrelated tabs.
- Treat signing in, account changes, uploads, metadata changes, and visibility changes as external side effects. Make only the requested changes.

## Upload sequence

1. Follow [the CDP protocol](references/cdp-protocol.md) to find the existing Studio tab and manipulate the page via its DOM/CDP session. Use `DOM.setFileInputFiles` for local file selection; a page script cannot populate a file input.
2. Start one upload and wait until Studio reaches the details step. Set its title and complete description, select the requested audience setting, and read the values back from the page before moving on.
3. Advance through Video elements and Initial check without adding cards, end screens, subtitles, or other unrequested changes. Choose only the requested visibility on the Visibility step, then save/publish.
4. Record the Studio video link/ID shown by the upload flow. If Studio says checks or processing are pending, do not claim it is Public merely because Public was selected.
5. Reload the exact Studio details page and prove the persisted title, description, audience, and effective visibility. For a Public request, also prove the public watch page plays with `scripts/youtube_studio_cdp.py watch VIDEO_ID` (exit 0 = a usable watch page, a finite video duration, `readyState >= 2`, playback advancing, and no unavailable/removed error; it uses its own background tab and closes it). Poll pending processing rather than re-uploading.
6. Write a concise publication record outside the skill repository: local file path and hash, requested/persisted metadata, video ID/URLs, requested/effective visibility, and timestamped verification results.

## Failure handling

- Never start a duplicate upload to solve a metadata, processing, or verification delay. Work with the one Studio video ID and retry the relevant save/reload/poll.
- Stop and report a blocker when the authenticated Studio tab is unavailable, file selection fails, account/channel differs from the requested one, the persisted metadata differs, Public does not become effective, or the watch page cannot play.
- Do not use private cookies, tokens, profile data, or CDP dumps as output or commit them to this skill/repository.

Read [the CDP protocol](references/cdp-protocol.md) before using the scripts. Use `scripts/youtube_studio_cdp.py` for deterministic CDP evaluation (`eval`), file attachment (`attach`) and public-playback proof (`watch`).
