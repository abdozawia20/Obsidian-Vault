<%* /* Time Garden templater component*/ 
// Import the quarterly operations module
tR = ""
const quarterlyOps = window?.timeGarden?.quarterly;;

// Run the quarterly alias function
await quarterlyOps.generateAlias(tp, app);
-%>