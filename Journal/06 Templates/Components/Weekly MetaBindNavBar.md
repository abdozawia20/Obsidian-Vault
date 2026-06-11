`BUTTON[prev-week, current-month, next-week]`
```meta-bind-button
id: prev-week
style: primary
class: phone-responsive
label: ← Previous Week
hidden: true
actions:
  - type: open
    link: "[[<%* tR += window?.timeGarden?.rootPath; _%>02 Weekly/<% moment(tp.file.title, 'YYYY-[W]WW').subtract(2, 'w').format('YYYY') %>/<% moment(tp.file.title, 'YYYY-[W]WW').subtract(2, 'w').format('YYYY') %>-<% moment(tp.file.title, 'YYYY-[W]WW').subtract(1, 'w').format('[W]WW') %>]]"
    newTab: false
```
```meta-bind-button
id: current-month
style: primary
class: phone-responsive
label: This Month
hidden: true
actions:
    - type: open  
      link: "[[<%* tR += window?.timeGarden?.rootPath; _%>03 Monthly/<% fileDate = moment(tp.file.title, 'YYYY-[W]WW').add(1, "d").format('YYYY/YYYY-MM-MMMM') %>]]"
      newTab: false
```
```meta-bind-button
id: next-week
style: primary
class: phone-responsive
label: Next Week →
hidden: true
actions:
    - type: open
      link: "[[<%* tR += window?.timeGarden?.rootPath; _%>02 Weekly/<% moment(tp.file.title, 'YYYY-[W]WW').add(2, 'w').format('YYYY') %>/<% moment(tp.file.title, 'YYYY-[W]WW').add(2, 'w').format('YYYY') %>-<% moment(tp.file.title, 'YYYY-[W]WW').add(1, 'w').format('[W]WW') %>]]"
      newTab: false
```