<%*  /* Time Garden templater component*/ 
const editor = app.workspace.activeLeaf.view.editor;
const content = editor.getValue().split('\n');

// Build template string using concatenation to avoid immediate execution
const cursorTag = '<' + '% tp.file.cursor(1) %' + '>';
const thoughtLine = '- #highlight ' + cursorTag;

// Find marker with escaped HTML
const headerLine = content.findIndex(line => line.includes('<p hidden>placer</p>'));
if (headerLine === -1) return;

// Insert constructed string
content.splice(headerLine + 0, 0, thoughtLine);

// Update editor content
editor.setValue(content.join('\n'));
editor.focus();
%>