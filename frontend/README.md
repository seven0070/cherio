# Bella desktop frontend

This is an adaptation of Sanath's Grok Mirror project, exported from Lovable on September 27, 2026: https://lovable.dev/projects/d8da2dec-60bf-46c1-b0a0-5744c5ecb314. Its visual structure, styles, sidebar behavior and local design language come from that source. The hosted Supabase/no-auth data layer, server AI search, canned replies, sign-in buttons and Grok mark were not carried into the desktop build. The original export included a Supabase `.env`; it is deliberately excluded. Chat data lives in Bella's local SQLite store instead.

`npm ci && npm run build` creates static assets in `dist/`. Run `bella-desktop` from a Python source install with pywebview. `npm run dev` is only a visual preview and cannot run local assistant actions.
