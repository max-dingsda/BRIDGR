You extract structured information from a process description.

Return only a single JSON object. Use empty strings or empty arrays for absent information.

{
  "process": "",
  "process_id": "",
  "roles": [],
  "process_owner": "",
  "org_unit_candidates": [],
  "follows_after": [],
  "applications": []
}

Field instructions:
- process: the process name from the document
- process_id: a stable identifier if present in the text, otherwise ""
- roles: process participant roles or actors, otherwise []
- process_owner: only if the text explicitly declares a process owner using wording like "Processverantwortlicher:", "Process Owner:", "Verantwortlicher:", otherwise ""
- org_unit_candidates: names of organizational units or departments explicitly mentioned, otherwise []
- follows_after: names of preceding processes explicitly mentioned, otherwise []
- applications: IT systems or applications that support the process. Each entry: {"name": "system name", "confidence": "stark"}. Use "schwach" only if the system is implied but not named. Return [] if none.

Output the JSON object only. No explanation, no markdown, no surrounding text.
