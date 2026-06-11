`BUTTON[prev-year, next-year]`
```meta-bind-button
id: prev-year
style: primary
class: phone-responsive
label: ← Previous Year
hidden: true
actions:
  - type: open
    link: "[[<%* tR += window?.timeGarden?.rootPath; _%>05 Yearly/<% fileDate = moment(tp.file.title, 'YYYY').subtract(1, 'year').format('YYYY') %>]]"
    newTab: false
```
```meta-bind-button
id: next-year
class: phone-responsive
style: primary
label: Next Year →
hidden: true
actions:
    - type: open
      link: "[[<%* tR += window?.timeGarden?.rootPath; _%>05 Yearly/<% fileDate = moment(tp.file.title, 'YYYY').add(1, 'year').format('YYYY') %>]]"
      newTab: false
```