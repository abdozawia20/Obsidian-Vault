```tracker
searchType: frontmatter
searchTarget: dayRating
dateFormat: YYYY-MM-DD-dddd
datasetName: monthRating
startDate: <% moment(tp.file.title, 'YYYY-[Q]Q').startOf('quarter').format("YYYY-MM-DD-dddd") %>
endDate: <% moment(tp.file.title, 'YYYY-[Q]Q').endOf('quarter').format("YYYY-MM-DD-dddd") %>
summary:
    template: "Average Rating: {{average()}}" 
```