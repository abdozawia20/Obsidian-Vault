<%"---"%>
tags:
  - "#type/weekly-note" 
cssclasses:
- image-borders
- image-small
- weekly
- timegarden-weekly
<%* tR += "- " + "week-" + moment(tp.file.title, 'YYYY-[W]WW').format('W').toLowerCase();%>
<%* // --- BANNER CONFIG --- 
tR += await tp.file.include("[[Weekly Banner Config]]"); %>
date: <% moment(tp.file.title, 'YYYY-[W]ww').startOf('week').format("YYYY-MM-DD") %>
journal: weekly
journal-date: <% moment(tp.file.title, 'YYYY-[W]WW').format("YYYY-MM-DD") %>
journal-start-date: <% moment(tp.file.title, 'YYYY-[W]WW').isoWeekday(1).format("YYYY-MM-DD") %>
journal-end-date: <% moment(tp.file.title, 'YYYY-[W]WW').isoWeekday(7).format("YYYY-MM-DD") %>
alias:
aiAnswer: ""
WeekSummary: ""
wheelOfLife:
  spiritual: 
  spiritualSummary: ""
  career: 
  careerSummary: ""
  relationships: 
  relationshipsSummary: ""
  health: 
  healthSummary: ""
  growth: 
  growthSummary: ""
  recreation: 
  recreationSummary: ""
  social: 
  socialSummary: ""
  finance: 
  financeSummary: ""
<%"---"%>
# ✧ <% tp.file.title %>
[[<% fileDate = moment(tp.file.title, 'YYYY-[W]WW').format('YYYY-[W]WW') %>|]] 
<%*
// --- NAVBAR ---
tR += await tp.file.include("[[Weekly MetaBindNavBar]]");
%>

<%*
tR += await tp.file.include("[[Weekly MetaBindAlias]]");
%>

<%* 
tR += await tp.file.include("[[Weekly MetaBindSummary]]"); 
%>

<%*
  tR += await tp.file.include("[[Weekly MetaBindAiButton]]");
%>

## Ratings ✮⋆˙
---
<%*
// the weekly average
tR += await tp.file.include("[[Weekly Rating Average]]");
%>
<%*
// the weekly Rating Barchart Module
tR += await tp.file.include("[[Weekly Rating BarChart]]");
%>
### <p hidden>PicturesHeader</p>
<%*
tR += await tp.file.include("[[Weekly Image Retriever]]");
_%>
## Logs
---
<%*
// weekly thought dashboard
tR += await tp.file.include("[[Weekly Progress]]");
%>

<%*
// weekly thought dashboard
tR += await tp.file.include("[[Weekly Ideas]]");
%>

<%*
// weekly thought dashboard
tR += await tp.file.include("[[Weekly Highlights]]");
%>

## General Overview
---
<%*
// weekly Daylist
 tR += await tp.file.include("[[Weekly Dataview Daylist]]")
%>

## Wheel of Life
---
<%*
// wheel of Life chart
 tR += await tp.file.include("[[Weekly WheelOfLife]]")
%>
<%*
// wheel of Life button
 tR += await tp.file.include("[[Weekly MetaBindWheelOfLifeAIButton]]")
%>

<%*
// wheel of Life displays
tR += await tp.file.include("[[weekly MetaBindWheelOfLifeDisplay]]")
%>

---
## Q&A
---
<%*
// wheel of Life chart
 tR += await tp.file.include("[[Weekly MetaBindAiQA]]")
%>

<%* app.workspace.activeLeaf.view.editor?.focus(); %>