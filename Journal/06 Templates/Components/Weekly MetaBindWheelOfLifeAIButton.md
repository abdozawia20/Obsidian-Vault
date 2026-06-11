```meta-bind-button
id: generate-wheel-of-life
style: primary
class: centered-button phone-responsive
label: 🌟 Generate Wheel of Life Analysis
actions:
  - type: command
    command: templater-obsidian:<%* tR += window?.timeGarden?.rootPath.substring(1); _%>06 Templates/Components/Weekly AI WheelOfLife.md
```