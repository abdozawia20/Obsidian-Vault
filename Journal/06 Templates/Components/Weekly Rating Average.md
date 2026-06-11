```tracker
searchType: frontmatter
searchTarget: dayRating
dateFormat: YYYY-MM-DD-dddd
datasetName: dayRating
startDate: <%moment(tp.file.title, 'YYYY-[W]ww').add(1, 'days').format("YYYY-MM-DD-dddd") %>
endDate: <% moment(tp.file.title, 'YYYY-[W]ww').add(1, 'weeks').format("YYYY-MM-DD-dddd") %>
summary:
    template: "Average Rating: {{average()}}" 
```