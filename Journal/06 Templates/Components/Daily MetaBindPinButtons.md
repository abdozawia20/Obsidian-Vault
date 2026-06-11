`BUTTON[new-thought, highlight, idea]`
```meta-bind-button
id: new-thought
style: primary
class: phone-responsive
label: 🎯 Progress
hidden: true
actions:
  - type: command
    command: "templater-obsidian:<%* tR += window?.timeGarden?.rootPath.substring(1); _%>06 Templates/Components/New Progress.md"
  - type: sleep 
    ms: 2
  - type: command
    command: templater-obsidian:jump-to-next-cursor-location 
```
```meta-bind-button
id: highlight
style: primary
class: phone-responsive
label: ✨ Highlight
hidden: true
actions:
  - type: command
    command: "templater-obsidian:<%* tR += window?.timeGarden?.rootPath.substring(1); _%>06 Templates/Components/New Highlight.md"
  - type: sleep 
    ms: 2
  - type: command
    command: templater-obsidian:jump-to-next-cursor-location 
```
```meta-bind-button
id: idea
style: primary
class: phone-responsive
label: 💡 Idea
hidden: true
actions:
  - type: command
    command: "templater-obsidian:<%* tR += window?.timeGarden?.rootPath.substring(1); _%>06 Templates/Components/New Idea.md"
  - type: sleep 
    ms: 2
  - type: command
    command: templater-obsidian:jump-to-next-cursor-location 
```