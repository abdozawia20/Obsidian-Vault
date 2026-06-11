<%*  /* Time Garden templater component*/ 
// Parse the week from the file title (format: YYYY-[W]WW)
let weekTitle = tp.file.title;
let weekNumber = weekTitle.split('-W')[1]; // Extracts the week number (e.g., "05")

// Calculate the start of week date
let startOfWeek = moment(weekTitle, 'YYYY-[W]WW').startOf('isoWeek');
let daysInWeek = 7;

// Create a callout with week-specific title
tR += `> [! pictures]- Pictures of W${weekNumber}\n`;

// Generate links to each day's picture section
tR += Array(daysInWeek).fill(null).map((x, i) => 
  `> ![[${moment(startOfWeek).add(i, 'd').format('YYYY-MM-DD-dddd')}#📁 Pictures]]`
).join("\n") + '\n';
_%>