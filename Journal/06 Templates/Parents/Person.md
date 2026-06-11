---
type: "person"
id: "person_{{date:YYYYMMDDHHmmss}}"
name: "{{title}}"
email: ""
role: ""
team: ""
tags:
  - person
---

# {{title}}

## Contact
- **Email**:
- **Role**:
- **Team**:

## Active Projects
```dataview
TABLE status, priority
FROM "Projects"
WHERE contains(team_members, this.file.link) OR owner = this.file.link
SORT status ASC
```

## Notes
