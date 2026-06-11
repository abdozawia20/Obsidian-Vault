<%* /* Time Garden templater component*/ 
// Import the monthly operations module
tR = ""
const monthlyOps = window?.timeGarden?.monthly;

// Run the monthly alias function
await monthlyOps.generateAlias(tp, app);
-%>