# Website security header

The policy in `site-preview/_headers` is the tested intended policy. Render's static-site documentation describes configuring response headers in the dashboard or a Blueprint; do not assume this file is applied by Render. Before relying on the policy, add it in the static site's Render settings as a header rule for `/*`, and verify the live HTTP response after deployment.

Name: `Content-Security-Policy`

Value: `default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; object-src 'none'`

The current pages contain inline scripts, event handlers, and styles. The script policy blocks external script URLs but permits inline scripts; remove that allowance only after those scripts and handlers are moved to files or protected with suitable hashes. External API collection will also require an explicit `connect-src` entry and a new browser test before it is enabled.

Render reference: https://render.com/docs/static-site-headers
