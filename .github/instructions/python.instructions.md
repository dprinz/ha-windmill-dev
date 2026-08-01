---
applyTo: "custom_components/**/*.py,tests/**/*.py,scripts/**/*.py"
---

- Use modern Python type annotations and explicit return types.
- Keep network I/O asynchronous in integration code.
- Do not catch broad exceptions unless immediately re-raised or translated with preserved context.
- Never log credentials, authorization headers, complete request bodies or raw job results by default.
- Tests should assert observable Home Assistant behavior through public interfaces.
- A bug fix requires a regression test that fails without the fix.
