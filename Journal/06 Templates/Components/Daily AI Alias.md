<%* /* Time Garden templater component*/ 
try {
  tR = ""
  const dailyOps = window?.timeGarden?.daily;
  
  await dailyOps.generateAlias(tp, tp.app);
  
} catch (error) {
  console.error("Error in Daily AI Alias:", error);
  new Notice(`❌ Error: ${error.message}`);
}
-%>