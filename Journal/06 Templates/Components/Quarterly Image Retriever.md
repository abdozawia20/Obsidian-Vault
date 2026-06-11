<%*  /* Time Garden templater component*/ 
// Get quarter from the file title
let quarterDate = moment(tp.file.title, 'YYYY-[Q]Q');
let year = quarterDate.format('YYYY');
let quarter = quarterDate.format('Q');

// Calculate the month numbers for this quarter
let startMonth = (quarter - 1) * 3 + 1;
let endMonth = quarter * 3;

// Array to store month names
let monthNames = [];

// Generate the month names for this quarter
for (let monthNum = startMonth; monthNum <= endMonth; monthNum++) {
  let monthName = moment().month(monthNum - 1).format('MM-MMMM');
  monthNames.push(monthName);
}

// Create section header
tR += `> [! pictures]- Gallery of Q${quarter}\n`;

// Generate links to the pictures section of each monthly note
for (const monthName of monthNames) {
  let monthTitle = `${monthName}`;
  tR += `> ![[${year}/${year}-${monthTitle}#<p hidden>PicturesHeader</p>]]\n`;
}

// End the callout
tR += '\n';
_%>