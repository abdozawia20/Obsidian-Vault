`BUTTON[prev-quarter, current-year, next-quarter]`
```meta-bind-button
id: prev-quarter
style: primary
label: ← Previous Quarter
hidden: true
actions:
  - type: open
    link: "[[<%* tR += window?.timeGarden?.rootPath; _%>04 Quarterly/<% fileDate = moment(tp.file.title, 'YYYY-[Q]Q').subtract(1, 'quarter').format('YYYY/YYYY-[Q]Q') %>]]"
    newTab: false
```
```meta-bind-button
id: current-year
style: primary
label: This Year
hidden: true
actions:
    - type: open  
      link: "[[<%* tR += window?.timeGarden?.rootPath; _%>05 Yearly/<% fileDate = moment(tp.file.title, 'YYYY-[Q]Q').format('YYYY') %>]]"
      newTab: false
```
```meta-bind-button
id: next-quarter
style: primary
label: Next Quarter →
hidden: true
actions:
    - type: open
      link: "[[<%* tR += window?.timeGarden?.rootPath; _%>04 Quarterly/<% fileDate = moment(tp.file.title, 'YYYY-[Q]Q').add(1, 'quarter').format('YYYY/YYYY-[Q]Q') %>]]"
      newTab: false
```