# Document questions

Run `decide.py --next`, ask exactly one question, record it, and repeat. If the user already supplied an answer, record it before requesting the next question.

1. `discount_pct` — whole-percentage additional temporary discount, or none. Build the request with `handoff.py prepare-discount`, call the returned MCP tool, replace the authoritative handoff result, and normalize again. Never calculate the discount locally.
2. `cover` — select an audience cover for PDF/print output.
3. `personalization` — event name, intro, contact details, client-safe notes, and closing.
4. `map` — optional route map for PDF/print output.
5. `format` — email, PDF, email+PDF, print HTML, HTML email, DOCX, or XLSX.

Fuel additions/waivers and priced greeter fees are not questions. Existing Core values remain visible. Unsupported monetary changes become a clear unsupported message; operational services may be described as arranged separately and not included in pricing.
