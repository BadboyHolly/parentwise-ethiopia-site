# Order recovery decision

Customers can recover after closing the tab by returning to checkout and entering the complete private recovery code: order ID plus the 256-bit bearer token. The QA page keeps the token only in the current tab session, clears the recovery input after use, and never places the token in a URL. The backend stores a hash of the token and checks it for status and download access. The order ID alone is not sufficient.

For production, keep this no-account recovery path as the default. Show the code once, explain that the customer must save it, and retain the clipboard-denial fallback that selects the full code and clears it when hidden. If a customer loses the code, Telegram support should verify the payment independently against the founder's bank or Telebirr record, rotate the recovery token, and revoke the old token. Never restore access from an order ID or a submitted payment reference alone.

This is a design recommendation only. The current checkout remains QA-only and does not contact payment providers or deliver real files.
