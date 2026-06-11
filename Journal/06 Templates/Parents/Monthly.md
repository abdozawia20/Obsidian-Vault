<%"---"%>
tags:
  - "#type/monthly-note" 
cssclasses:
  - image-borders
  - image-small
  - timegarden-monthly
  <%* tR += "- " + moment(tp.file.title, 'YYYY-MM-MMMM').format('MMMM').toLowerCase(); tR += "\n  - monthly" %>
<%* // --- BANNER CONFIG --- 
tR += await tp.file.include("[[Monthly Banner Config]]"); %>
date: <% moment(tp.file.title, 'YYYY-MM-MMMM').startOf('month').format("YYYY-MM-DD") %>
alias:
aiAnswer: ""
MonthSummary: ""
monthlyWheelOfLifeCategoryChartType: line
journal: monthly
journal-date: <% moment(tp.file.title, 'YYYY-MM-MMMM').startOf('month').format("YYYY-MM-DD") %>
journal-start-date: <% moment(tp.file.title, 'YYYY-MM-MMMM').startOf('month').format("YYYY-MM-DD") %>
journal-end-date: <% moment(tp.file.title, 'YYYY-MM-MMMM').endOf('month').format("YYYY-MM-DD") %>
<%"---"%>
# ✧ *<% moment(tp.file.title, 'YYYY-MM-MMMM').format('MM-MMMM') %>*

<%*
tR += await tp.file.include("[[Monthly MetaBindNavBar]]");
%>

<%*
tR += await tp.file.include("[[Monthly MetaBindAlias]]");
%>

<%* 
tR += await tp.file.include("[[Monthly MetaBindSummary]]"); 
%>

<%*
tR += await tp.file.include("[[Monthly MetaBindAiButton]]");
%>

## Ratings ✮⋆˙
---
<%*
// Monthly average rating
tR += await tp.file.include("[[Monthly Rating Average]]");
%>

<%*
// Monthly Rating Chart Module
tR += await tp.file.include("[[Monthly Rating Chart]]");
%>
### <p hidden>PicturesHeader</p>
<%*
// Monthly Image Retriever - will collect images from the month
tR += await tp.file.include("[[Monthly Image Retriever]]");
_%>

## Logs
---
<%*
// Get all weekly callouts
tR += await tp.file.include("[[Monthly Logs Retriever]]");
%>

## Week Overview
---
<%*
// List of weekly notes with their aliases
tR += await tp.file.include("[[Monthly Weeklist]]");
%>
## Wheel of Life Overview
---
<%*
// Display all 4 wheels of life and the average
tR += await tp.file.include("[[Monthly WheelOfLife]]");
%>

<%*
// Display all 4 wheels of life and the average
tR += await tp.file.include("[[Monthly MetaBind WheelOfLifeChartTypePicker]]");
%>

<%*
// Display all 4 wheels of life and the average
tR += await tp.file.include("[[Monthly WheelOfLifeCategoryChart]]");
%>

## Q&A
---
<%*
// wheel of Life chart
 tR += await tp.file.include("[[Monthly MetaBindAiQA]]")
%>

<%* app.workspace.activeLeaf.view.editor?.focus(); %>