```tracker
searchType: frontmatter
searchTarget: dayRating
dateFormat: YYYY-MM-DD-dddd
datasetName: yearRating
startDate: <% moment(tp.file.title, 'YYYY').startOf('year').format("YYYY-MM-DD-dddd") %>
endDate: <% moment(tp.file.title, 'YYYY').endOf('year').format("YYYY-MM-DD-dddd") %>
summary:
    template: "Average Rating: {{average()}}" 
```