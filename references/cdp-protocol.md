# CDP protocol for an existing YouTube Studio session

This protocol assumes the operator has already authorized an authenticated Brave browser CDP endpoint. Its job is to make a single requested publication repeatable; it must not create authentication state or reveal browser credentials.

## Locate the sole Studio tab

Get `http://127.0.0.1:9222/json/list`, choose the `type: "page"` entry whose URL begins with `https://studio.youtube.com/`, then connect to its `webSocketDebuggerUrl`. CDP websocket clients may require `localhost` rather than `127.0.0.1` in that URL. Do not create tabs or start Chrome.

Use `Runtime.evaluate` only for safe page-state inspection and normal UI interactions. Evaluate with `returnByValue: true`, `awaitPromise: true`, and `userGesture: true` when an interaction requires it. For large local files, attach via the DOM domain:

1. `DOM.enable`
2. `DOM.getDocument`
3. `DOM.querySelector` for `input[type=file]`
4. `DOM.setFileInputFiles` with the absolute local path and the returned `nodeId`

Do not attempt to assign a file input's `value` in JavaScript; browsers disallow it.

## Studio flow

Studio's UI is subject to markup changes. Locate controls by visible/accessible text within `ytcp-uploads-dialog`, rather than brittle screen coordinates:

- **Create → Upload videos** opens the upload dialog.
- **Details** has two `contenteditable` boxes, conventionally title then description. Focus each, select contents using a `Range`, insert plain text using `document.execCommand('insertText', false, text)`, dispatch `input` and `change`, blur, then read `innerText` back.
- Select the exact audience `tp-yt-paper-radio-button` (`VIDEO_MADE_FOR_KIDS_MFK` or `VIDEO_MADE_FOR_KIDS_NOT_MFK`) requested by the operator.
- Use **Next** to traverse Video elements and Initial check; do not add optional items unless asked.
- On Visibility, choose exactly `PRIVATE`, `UNLISTED`, or `PUBLIC`, inspect its `aria-checked`, then use **Save** or **Publish**. A click may be ignored while Studio is completing checks; wait and retry the same button, never restart the upload.

Useful upload-dialog state is accessible in `ytcp-uploads-dialog.innerText`: `Uploading N%`, processing/check state, the video link, saved state, and steps. Do not assume “Saved as private” has changed until the final confirmation/reload.

## Verification

The upload flow's requested visibility is not proof of effective visibility. Retrieve/reload the Studio details page for the recorded video ID and read title, description, audience, and visibility from that page. For Public publication, navigate a task-created watch tab to `https://www.youtube.com/watch?v=VIDEO_ID` and inspect the video element only after the normal page UI has loaded:

- `Number.isFinite(video.duration)` and `video.duration > 0`
- `video.readyState >= 2`
- visible page text does not signal unavailable, removed, private, or “Video unavailable”

Processing can remain pending after a successful save. Poll the existing Studio/video page with bounded intervals and report any remaining state rather than creating a duplicate. Close only the watch tab created for this task when its verification is complete.

## Observed Studio pitfalls (2026-10-10)

- With Python websocket-client, use `suppress_origin=True` to attach to the existing Brave endpoint when its origin check rejects the connection. This requires no browser restart or flags. `scripts/youtube_studio_cdp.py` does this for every connection (2026-10-13).
- Scope upload controls and image inputs to `ytcp-uploads-dialog`; a resumed draft can have duplicate hidden controls from the underlying details page. Wait for audience/playlist values to finish rendering before asserting persisted state.
- Wait for a save to finish and its dialog to close before navigating. Navigating away from a pending publication confirmation can leave the uploaded ID as an unfinished draft with default metadata. Reopen that exact ID’s **Edit draft** and save the intended metadata; never attach the master again.
- If checks remain pending, save the existing upload as Private while preparing captions/end screen, then select the requested Public state after checks finish. Private is an intermediate upload state; report the effective state accurately. Never use “Publish anyway” to bypass unfinished checks.
- For timed manual captions, upload the VTT with **With timing**, open the subtitle editor, confirm its first cues match the file, Publish, and reload. The public player should expose the manual English track.
- Public playback data can verify the precise end-screen video ID and start/end milliseconds. Confirm the target matches the description link and occupies the approved final15–20seconds.

- A Private save during SD processing can open a **Video processing** confirmation. Close that confirmation through its visible **Close** button; wait for the effective details state to change from Pending to Private before asserting it. Finish processing/checks before opening subtitle/end-screen editors.
- **Upload manual** can save the timed file while the separate **Edit subtitles** editor still opens empty at **Add subtitles**. In that editor, use **Upload file → With timing → Continue**, attach the same VTT, wait for visible cue text matching the file, then Publish. A toast saying subtitles were uploaded is insufficient proof.
- Playlist controls briefly show **Select** during page hydration. Wait for the expected playlist name, alongside the persisted audience/title/visibility, before verification.

- **Edit subtitles** may open the auto-generated transcript even after an **Upload manual** toast. Prefer loading the timed VTT inside the editor: **Upload file** for an empty editor, or **Options → Upload file** for an existing automatic transcript. Select **With timing**, attach the intended file, verify exact visible cue text and Publish. The uploaded-file toast and the presence of editable automatic text do not establish the intended captions.
- Click the nested **Element** button in the end-screen editor only once its `aria-disabled` state is false; the host can exist before the button is ready.

- Wait for the subtitle editor to render actual cue text or its visible **Upload file** control; the preview shell can appear first. If automatic subtitles are still generating, **Upload manual** can establish the English track before using **Edit subtitles**. Confirm the timed VTT inside that editor and Publish. Avoid redundant navigation to the exact route already loaded; if the task tab stops answering trivial CDP evaluations, close only that target and reopen one replacement at the same recorded video ID. Preserve user tabs and the three-tab cap.

## Public playback check (2026-10-13)

- A watch page opened in a **background** tab never loads its media: `video.duration` stays `NaN` and `readyState` 0, which
  looks like a failed publication. Do not bring the tab to the front (that takes over the operator's view). Instead
  create the tab at `about:blank` in the background, enable `Emulation.setFocusEmulationEnabled`, navigate, mute and press
  play. `scripts/youtube_studio_cdp.py watch VIDEO_ID` does exactly this, requires `currentTime` to advance between polls,
  closes only its own tab, and exits non-zero unless the video plays.
