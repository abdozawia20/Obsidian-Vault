<%*  /* Time Garden templater component*/ 
// Get month from the file title
let monthDate = moment(tp.file.title, 'YYYY-MM-MMMM');
let year = monthDate.format('YYYY');
let month = monthDate.format('MM');

// Create section header
tR += `> [! pictures]- Gallery of M${month}\n`;

// Debug information (uncomment to see)
// tR += `> DEBUG: Processing month ${month} of year ${year}\n`;

// Get all days in this month and collect their week numbers
let startOfMonth = moment(monthDate).startOf('month');
let endOfMonth = moment(monthDate).endOf('month');
let currentDate = moment(startOfMonth);
let weekNumbers = new Set();

// Collect all unique week numbers in this month
while (currentDate <= endOfMonth) {
  let weekNum = currentDate.format('WW');
  weekNumbers.add(weekNum);
  
  // Optional debug (uncomment to see)
  // tR += `> DEBUG: ${currentDate.format('YYYY-MM-DD')} (${currentDate.format('dddd')}) is in week ${weekNum}\n`;
  
  currentDate.add(1, 'day');
}

// Sort the week numbers
let sortedWeeks = Array.from(weekNumbers).sort((a, b) => parseInt(a) - parseInt(b));

// Generate links to the pictures section of each weekly note
for (const weekNum of sortedWeeks) {
  const paddedWeekNum = weekNum.padStart(2, '0');
  let weekTitle = `${year}-W${paddedWeekNum}`;
  
  // Optional debug (uncomment to see)
  // tR += `> DEBUG: Including week ${paddedWeekNum}\n`;
  
  tR += `> ![[${weekTitle}#<p hidden>PicturesHeader</p>]]\n`;
}

// End the callout
tR += '\n';
_%>