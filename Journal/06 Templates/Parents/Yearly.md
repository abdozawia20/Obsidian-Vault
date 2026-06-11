<%"---"%>
tags:
  - "#type/yearly-note" 
cssclasses:
  - image-borders
  - image-small
  - yearly
  - timegarden-yearly
<%* // --- BANNER CONFIG --- 
tR += await tp.file.include("[[Yearly Banner Config]]"); %>
date: <% moment(tp.file.title, 'YYYY').startOf('year').format("YYYY-MM-DD") %>
alias:
aiAnswer: ""
YearSummary: ""
yearlyWheelOfLifeCategoryChartType: line
journal: yearly
journal-date: <% moment(tp.file.title, 'YYYY').startOf('year').format("YYYY-MM-DD") %>
<%"---"%>
# ✧ <% tp.file.title %>

<%*
// --- NAVBAR ---
tR += await tp.file.include("[[Yearly MetaBindNavBar]]");
%>

<%*
tR += await tp.file.include("[[Yearly MetaBindAlias]]");
%>

<%* 
tR += await tp.file.include("[[Yearly MetaBindSummary]]"); 
%>

<%*
tR += await tp.file.include("[[Yearly MetaBindAiButton]]");
%>

## Ratings ✮⋆˙
---
<%*
// Yearly average rating
tR += await tp.file.include("[[Yearly Rating Average]]");
%>

```dataviewjs
dv.view("06 Templates/Scripts/templater/dataviewjs/yearly/yearlyRatingChart", {container: this.container})
```

## Top Days ✮⋆˙
---
```dataview
TABLE WITHOUT ID file.link as Date, alias as Day
FROM "<%* tR += window?.timeGarden?.rootPath.substring(1); _%>01 Daily"
WHERE date.year = date(this.file.day).year
AND dayRating >= 9
SORT dayRating DESC
```

## Gallery
---
<%*
// Get year from the file title
let yearDate = moment(tp.file.title, 'YYYY');
let year = yearDate.format('YYYY');

// Create section header
tR += '> [! pictures]- Yearly Gallery\n';

// Generate links to the pictures section of each quarterly note
for (let quarter = 1; quarter <= 4; quarter++) {
  let quarterTitle = `${year}-Q${quarter}`;
  tR += `> ![[${year}/${quarterTitle}#<p hidden>PicturesHeader</p>]]\n`;
}

// End the callout
tR += '\n';
_%>
## Quarters Overview
---
```dataview
TABLE without id file.link as Quarter, alias
FROM "<%* tR += window?.timeGarden?.rootPath.substring(1); %>04 Quarterly"
WHERE date.year = date(this.file.day).year
SORT file.day ASC
```

## Wheel of Life Overview
---
```dataviewjs
dv.view("06 Templates/Scripts/templater/dataviewjs/yearly/yearlyWheelOfLifeChart", {container: this.container})
```

<%*
// Display chart type picker for wheel of life category progression
tR += `**Chart Type:** \`INPUT[suggester(title('chart type'), option(line), option(bar), option(pie), option(radar)):yearlyWheelOfLifeCategoryChartType]\``;
%>

```dataviewjs
dv.view("06 Templates/Scripts/templater/dataviewjs/yearly/yearlyWheelOfLifeProgression", {container: this.container})
```
## Q&A
---
<%*
// wheel of Life chart
 tR += await tp.file.include("[[Yearly MetaBindAiQA]]")
%>

<%* app.workspace.activeLeaf.view.editor?.focus(); %>