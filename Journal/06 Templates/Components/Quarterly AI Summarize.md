<%* /* Time Garden templater component*/ 
tR = ""
// Import the quarterly operations module
const quarterlyOps = window?.timeGarden?.quarterly;;

// Run the quarterly summary function
await quarterlyOps.generateSummary(tp, app);
-%>