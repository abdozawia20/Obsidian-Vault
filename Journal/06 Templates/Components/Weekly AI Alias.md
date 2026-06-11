<%* /* Time Garden templater component*/ 
// Import the weekly operations module
tR = ""
const weeklyOps = window?.timeGarden?.weekly;

// Run the weekly alias function
await weeklyOps.generateAlias(tp, app);
-%>