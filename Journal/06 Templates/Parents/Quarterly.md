<%"---"%>
tags:
  - "#type/quarterly-note" 
cssclasses:
  - image-borders
  - image-small
  - timegarden-quarterly
  <%* tR += "- " + "quarter-" + moment(tp.file.title, 'YYYY-[Q]Q').format('Q').toLowerCase(); tR += "\n  - quarterly" %>
<%* // --- BANNER CONFIG --- 
tR += await tp.file.include("[[Quarterly Banner Config]]"); %>
date: <% moment(tp.file.title, 'YYYY-[Q]Q').startOf('quarter').format("YYYY-MM-DD") %>
alias:
aiAnswer: ""
QuarterSummary: ""
quarterlyWheelOfLifeCategoryChartType: line
quarterRating: 0
journal: quarterly
journal-date: <% moment(tp.file.title, 'YYYY-[Q]Q').startOf('quarter').format("YYYY-MM-DD") %>
journal-start-date: <% moment(tp.file.title, 'YYYY-[Q]Q').startOf('quarter').format("YYYY-MM-DD") %>
journal-end-date: <% moment(tp.file.title, 'YYYY-[Q]Q').endOf('quarter').format("YYYY-MM-DD") %>
<%"---"%>
# ✧ *<% moment(tp.file.title, 'YYYY-[Q]Q').format('YYYY [Q]Q') %>*

<%*
tR += await tp.file.include("[[Quarterly MetaBindNavBar]]");
%>

<%*
tR += await tp.file.include("[[Quarterly MetaBindAlias]]");
%>

<%* 
tR += await tp.file.include("[[Quarterly MetaBindSummary]]"); 
%>

<%*
tR += await tp.file.include("[[Quarterly MetaBindAiButton]]");
%>

## Ratings ✮⋆˙
---
<%*
// Quarterly average rating
tR += await tp.file.include("[[Quarterly Rating Average]]");
%>

<%*
// Quarterly Rating Chart Module
tR += await tp.file.include("[[Quarterly Rating Chart]]");
%>
### <p hidden>PicturesHeader</p>
<%*
// Quarterly Image Retriever - will collect images from the quarter
tR += await tp.file.include("[[Quarterly Image Retriever]]");
_%>

## Logs
---
<%*
// Get all monthly callouts
tR += await tp.file.include("[[Quarterly Logs Retriever]]");
%>

## Month Overview
---
<%*
// List of monthly notes with their aliases
tR += await tp.file.include("[[Quarterly Monthlist]]");
%>

## Wheel of Life Overview
---
<%*
// Display all 3 wheels of life and the average
tR += await tp.file.include("[[Quarterly WheelOfLife]]");
%>

<%*
// Display chart type picker for wheel of life category progression
tR += await tp.file.include("[[Quarterly MetaBind WheelOfLifeChartTypePicker]]");
%>

<%*
// Display wheel of life category progression chart
tR += await tp.file.include("[[Quarterly WheelOfLifeCategoryChart]]");
%>

## Q&A
---
<%*
// wheel of Life chart
 tR += await tp.file.include("[[Quarterly MetaBindAiQA]]")
%>

<%* app.workspace.activeLeaf.view.editor?.focus(); %>