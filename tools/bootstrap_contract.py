from pathlib import Path
p = Path('contracts/openapi.yaml')
s = p.read_text()
s = s.replace('# JL-SAD-001 / Proposed; no deployed service is asserted.\n', '')
s = s.replace('title: Job Lens / 融职境 API Proposal', 'title: Job Lens / 融职境 API')
s = s.replace('version: 0.1.0-proposed', 'version: 0.1.0')
s = s.replace('description: Read api-contract.md for resource authorization, state transitions, idempotency and cross-field invariants. M1/M2/M3 denote proposed work packages. All non-success responses use Problem Details.', 'description: Resource authorization, state transitions and HTTP conventions are defined in docs/development.md. Implementation coverage is tracked separately from this contract.')
if '    CaseProfile:' not in s:
    line = "    CaseProfile: {<<: *profile, required: [display_name, sensory_preferences, communication_preference, work_notes, user_id, version, preferences], properties: {<<: *profile_props, user_id: *uuid, version: *version, preferences: {$ref: '#/components/schemas/Preferences'}}}\n"
    s = s.replace('    Capabilities:', line + '    Capabilities:')
    start = s.index('  /cases/{case_id}/profile:')
    end = s.index('  /cases/{case_id}/materials:', start)
    section = s[start:end].replace('#/components/schemas/Profile', '#/components/schemas/CaseProfile')
    section = section.replace('headers: {ETag: *etag}, ', '')
    s = s[:start] + section + s[end:]
p.write_text(s)
