>[! journal]- &nbsp;This Note From Different Years
>```dataview
TABLE alias
FROM "<%* tR += window?.timeGarden?.rootPath.substring(1) %>01 Daily"
WHERE dateformat(date, "MM-dd") = dateformat(this.file.day, "MM-dd") AND file.name != this.file.name
SORT date DESC
>```