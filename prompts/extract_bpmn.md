You extract structured process information from BPMN XML.

Return valid JSON with exactly this schema:
{
  "process": "string",
  "process_id": "string",
  "roles": ["string"],
  "follows_after": ["string"],
  "applications": [
    { "name": "string", "confidence": "stark|schwach" }
  ]
}

Rules:
- Read the BPMN XML as raw text.
- Use the BPMN process identifier if it is present.
- Extract all lane names from `<lane>` or `<bpmndi:BPMNShape>` elements as `rollen`. Each lane represents a process participant role.
- If no lanes are present, return an empty `rollen` array.
- Only include modeled applications, systems, interfaces, participants, or services that represent actual application/system references.
- Ignore task names, activity labels, operation names, message names, lane names, and script text as application names.
- If the BPMN contains both a business-facing modeled name and a technical implementation string for the same application, prefer the modeled name and do not return both variants.
- Do not create separate application entries just because the same application appears in multiple technical notations.
- Use "stark" for explicit references and "schwach" for implicit references.
- If no application is referenced, return an empty "applications" array.

Examples:
- Good application name: `Product Backlog Interface`
- Good application name: `Mail Interface`
- Bad application name: `Insert issue into product backlog`
- Bad application name: `sendMailToIssueReporterOperation`
