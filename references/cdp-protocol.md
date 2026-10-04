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
