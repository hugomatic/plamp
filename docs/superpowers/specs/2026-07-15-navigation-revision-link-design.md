# Navigation revision link

Replace the top navigation's `GitHub` link with one understated revision link:

`[rev ebaf545]`

The label uses the running checkout's short Git commit and links to that exact commit on GitHub. Resolve the revision once at application startup and pass it to the shared navigation renderer; page rendering must not invoke Git. Every page using the shared navigation shows the same revision.

If the revision cannot be resolved, render `[rev unknown]` without a link. Escape revision text before rendering it.

Tests cover the shared navigation label, exact commit URL, removal of the separate `GitHub` link, and the unavailable-revision fallback.
