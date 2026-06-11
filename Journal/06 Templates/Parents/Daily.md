<%"---"%>
<%*
tR += await tp.file.include("[[Daily Banner Config]]"); 
%>

<%* tR+= "cssclasses:"%>
  - <%"image-borders"%>
  - image-small
  - <%"timegarden-daily"%>
  <%* 
    tR += "- " + moment(tp.file.title, 'YYYY-MM-DD').format('dddd').toLowerCase()
    tR += "\n  - daily"
    %> 

date: <% moment(tp.file.title, 'YYYY-MM-DD-dddd').format("YYYY-MM-DD") %>

alias: 
dayRating: 1
tags: "#type/daily-note"

journal: daily
journal-date: <% moment(tp.file.title, 'YYYY-MM-DD-dddd').format('YYYY-MM-DD') %>
journal-start-date: <% moment(tp.file.title, 'YYYY-MM-DD-dddd').format('YYYY-MM-DD') %>
journal-end-date: <% moment(tp.file.title, 'YYYY-MM-DD-dddd').format('YYYY-MM-DD') %>

aiAnswer: ""
<%"---"%>
# ✧ <% moment(tp.file.title, 'YYYY-MM-DD-dddd').format("dddd, MMMM DD, YYYY") %>
[[<% // create hidden link to weekly note for graph view

moment(tp.file.title, 'YYYY-MM-DD-dddd').format('YYYY-[W]WW') %>|]]
<%*
// create navbar
tR += await tp.file.include("[[Daily MetaBindNavBar]]");
%>

<%*
// create input field for alias
tR += await tp.file.include("[[Daily MetaBindAlias]]");
%>
---
- <% tp.file.cursor(0) %>


<%*
tR += await tp.file.include("[[Daily MetaBindAiButtons]]");
%>
---
### 📁 Pictures


### <p hidden>PicturesEnd</p>
---
<%*
tR += await tp.file.include("[[Daily MetaBindRating]]");
%>

### ⚡︎ Quick Notes
---
<p hidden>placer</p>

<%*
tR += await tp.file.include("[[Daily MetaBindPinButtons]]");
%>
---
<%*
tR += await tp.file.include("[[Daily YearNoteThrowback]]");
%>

### Q&A
---
<%*
tR += await tp.file.include("[[Daily MetaBindAiQA]]");
%>

<%*
// delete this manually to remove the share letter as an alternative to pressing the button!
const dv = app.plugins.plugins.dataview.api;

const shareLetterPage = dv.page(window?.timeGarden?.rootPath.substring(1) + "07 Notes/Extras/A secret garden within the garden.");

if (shareLetterPage && shareLetterPage.showYourself === true) {
    tR += "\n\n[[A secret garden within the garden.]]";
} else {}
%>