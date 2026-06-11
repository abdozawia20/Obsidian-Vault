<%* /* Time Garden templater component*/ 
const getWeekDates = (filename) => {
  try {
    const weekMatch = filename.match(/W(\d+)/);
    const yearMatch = filename.match(/(\d{4})/);
    
    if (weekMatch && yearMatch) {
      const weekNum = parseInt(weekMatch[1]);
      const year = parseInt(yearMatch[1]);
      
      // Find the first Monday of the year
      const firstDayOfYear = new Date(year, 0, 1);
      let firstMonday = new Date(firstDayOfYear);
      
      // Calculate days until Monday
      const dayOfWeek = firstDayOfYear.getDay(); // 0 = Sunday, 1 = Monday, etc.
      const daysUntilMonday = dayOfWeek === 1 ? 0 : (dayOfWeek === 0 ? 1 : 8 - dayOfWeek);
      
      // Set to first Monday
      firstMonday.setDate(firstDayOfYear.getDate() + daysUntilMonday);
      
      // Calculate the Monday of the specified week
      const weekStart = new Date(firstMonday);
      weekStart.setDate(firstMonday.getDate() + (weekNum - 1) * 7 - 6); // Subtract 6 days to hit exact isoweek
      
      // Calculate the Sunday of the specified week
      const weekEnd = new Date(weekStart);
      weekEnd.setDate(weekStart.getDate() + 6);
      
      return {
        start: weekStart.toISOString().split('T')[0],
        end: weekEnd.toISOString().split('T')[0]
      };
    }
  } catch (error) {
    console.error("Error calculating dates:", error);
  }
  
  return null;
}

// Get current filename and extract dates
const filename = tp.file.title;
const dates = getWeekDates(filename);

if (!dates) {
  return "Error: Unable to extract date range from filename.";
}

// Using the filter approach for finding progress items with lines between results
const query = `>[!highlights]- **Highlights**
>\`\`\`dataview
>TABLE WITHOUT ID regexreplace(L.text, "<p hidden>placer</p>", "") AS Highlights, file.day AS Date 
>FROM "${window?.timeGarden?.rootPath.substring(1)}01 Daily" 
>WHERE file.day >= date("${dates.start}") AND file.day <= date("${dates.end}")
>FLATTEN file.lists AS L
>WHERE contains(L.tags, "#highlight")
>SORT file.day DESC
>\`\`\``;

return query;
%>