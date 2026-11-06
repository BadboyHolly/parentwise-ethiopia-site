# Design previews (not part of the public website)

`founder/` and `founder-preview/` are static design references for the Founder dashboard, with **sample data only**. They are
not served by the website (the Render site publishes only `site-preview/`). The real dashboard is built separately in the AletCloud
backend repository. To look at one locally, serve this folder, for example:

    python -m http.server 8770 --directory design-previews

then open `http://localhost:8770/founder-preview/index.html`. Moved out of `site-preview/` on 2026-11-06 so customers cannot reach them.
