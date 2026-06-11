`BUTTON[prev-month, current-quarter, next-month]`
```meta-bind-button
id: prev-month
style: primary
class: phone-responsive
label: ← Previous Month
hidden: true
actions:
  - type: open
    link: "[[<%* tR += window?.timeGarden?.rootPath; _%>03 Monthly/<% fileDate = moment(tp.file.title, 'YYYY-MM-MMMM').subtract(1, 'month').format('YYYY/YYYY-MM-MMMM') %>]]"
    newTab: false
```
```meta-bind-button
id: current-quarter
style: primary
class: phone-responsive
label: This Quarter
hidden: true
actions:
    - type: open  
      link: "[[<%* tR += window?.timeGarden?.rootPath; _%>04 Quarterly/<% fileDate = moment(tp.file.title, 'YYYY-MM-MMMM').format('YYYY/YYYY-[Q]Q') %>]]"
      newTab: false
```
```meta-bind-button
id: next-month
style: primary
class: phone-responsive
label: Next Month →
hidden: true
actions:
    - type: open
      link: "[[<%* tR += window?.timeGarden?.rootPath; _%>03 Monthly/<% fileDate = moment(tp.file.title, 'YYYY-MM-MMMM').add(1, 'month').format('YYYY/YYYY-MM-MMMM') %>]]"
      newTab: false
```