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

// Generate the month names for this quarter (with proper YYYY-MM-MMMM format)
for (let monthNum = startMonth; monthNum <= endMonth; monthNum++) {
  // Create the right formatted month with the quarter's year
  let monthPadded = String(monthNum).padStart(2, '0');
  let monthLongName = moment(`${year}-${monthPadded}-01`).format('MMMM');
  let monthFormatted = `${year}-${monthPadded}-${monthLongName}`;
  monthNames.push(monthFormatted);
}

// Generate separate callouts for each month's logs
for (let i = 0; i < monthNames.length; i++) {
  const monthName = monthNames[i];
  
  // Map numbers to words
  const numberWords = ["one", "two", "three"];
  const wordNumber = numberWords[i];
  
  // Use correct path with both main folder and year subfolder
  tR += `> [!logs${wordNumber}]- Logs of ${monthName}\n`;
  tR += `> ![[03 Monthly/${year}/${monthName}#Logs]]\n\n`;
}
_%>