<%* /* Time Garden templater component*/ 
// Import the monthly operations module
tR = ""
const monthlyOps = window?.timeGarden?.monthly;

// Run the monthly summary function
await monthlyOps.generateSummary(tp, app);
-%>