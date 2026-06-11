```tracker
searchType: frontmatter
searchTarget: dayRating
dateFormat: YYYY-MM-DD-dddd
datasetName: dayRating
startDate: <% moment(tp.file.title, 'YYYY-MM-MMMM').startOf('month').format("YYYY-MM-DD-dddd") %>
endDate: <% moment(tp.file.title, 'YYYY-MM-MMMM').endOf('month').format("YYYY-MM-DD-dddd") %>
summary:
    template: "Average Rating: {{average()}}" 
```