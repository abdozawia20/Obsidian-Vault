`BUTTON[generate-monthly-summary, generate-monthly-alias]`
```meta-bind-button
id: generate-monthly-summary
style: primary
label: ✨ Generate Summary
hidden: true
actions:
  - type: command
    command: templater-obsidian:<%* tR += window?.timeGarden?.rootPath.substring(1); _%>06 Templates/Components/Monthly AI Summarize.md
```
```meta-bind-button
id: generate-monthly-alias
style: primary
label: 🏷️ Generate Alias
hidden: true
actions:
  - type: command
    command: templater-obsidian:<%* tR += window?.timeGarden?.rootPath.substring(1); _%>06 Templates/Components/Monthly AI Alias.md
```