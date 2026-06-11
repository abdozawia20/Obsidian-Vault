<%*  /* Time Garden templater component*/ 
// Get month from the file title
let monthDate = moment(tp.file.title, 'YYYY-MM-MMMM');
let year = monthDate.format('YYYY');
let month = monthDate.format('MM');

// Function to determine if a week primarily belongs to this month
function weekBelongsToMonth(weekNum, year, month) {
  // Get the start date of the week
  let weekStart = moment(`${year}-W${weekNum}-1`, 'YYYY-[W]WW-E');
  
  // Count how many days of this week fall in our target month
  let daysInTargetMonth = 0;
  let currentDay = moment(weekStart);
  
  for (let i = 0; i < 7; i++) {
    if (currentDay.format('MM') === month) {
      daysInTargetMonth++;
    }
    currentDay.add(1, 'day');
  }
  
  // If majority of days (4 or more) are in this month, or
  // if exactly half the days (3-3 split with previous month) and the week starts on a Monday in this month
  return daysInTargetMonth >= 4 || 
         (daysInTargetMonth === 3 && weekStart.format('MM') === month);
}

// Get all weeks in the year
let startOfYear = moment(`${year}-01-01`);
let endOfYear = moment(`${year}-12-31`);
let allWeeks = new Set();

// Collect all week numbers for the entire year
let current = moment(startOfYear);
while (current <= endOfYear) {
  allWeeks.add(current.format('WW'));
  current.add(1, 'week');
}

// Filter to weeks that primarily belong to this month
let monthWeeks = Array.from(allWeeks).filter(weekNum => 
  weekBelongsToMonth(weekNum, year, month)
);

// Sort weeks numerically
monthWeeks.sort((a, b) => parseInt(a) - parseInt(b));

// Map numbers to words
const numberWords = ["one", "two", "three", "four", "five", "six"];

// Generate separate callouts for each week's logs
for (let i = 0; i < monthWeeks.length; i++) {
  // Ensure we don't exceed our numberWords array
  if (i >= numberWords.length) {
    break; // Skip if we have more weeks than words available
  }
  
  const weekNum = monthWeeks[i];
  // Ensure week number is padded with a leading zero if needed
  const paddedWeekNum = weekNum.padStart(2, '0');
  let weekTitle = `${year}-W${paddedWeekNum}`;
  
  // Use lowercase word-based callout identifiers: logsone, logstwo, etc.
  const wordNumber = numberWords[i];
  tR += `> [!logs${wordNumber}]- Logs of W${paddedWeekNum}\n`;
  tR += `> ![[${weekTitle}#Logs]]\n\n`;
}
_%>