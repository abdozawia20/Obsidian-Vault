<%* /* Time Garden templater component*/ 
// Import the yearly operations module
const yearlyOps = window?.timeGarden?.yearly;

// Run the yearly summary function
await yearlyOps.generateSummary(tp, app);
%>