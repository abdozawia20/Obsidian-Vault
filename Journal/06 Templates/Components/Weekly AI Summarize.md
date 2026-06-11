<%* /* Time Garden templater component*/ 
// Import the weekly operations module
tR = ""
const weeklyOps = window?.timeGarden?.weekly;

// Run the weekly summary function
await weeklyOps.generateSummary(tp, app);
-%>