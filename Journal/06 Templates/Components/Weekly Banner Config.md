<%* /* Time Garden templater component*/ 
// Configuration for weekly banners
const weeklyBannerConfigs = {
    // You can adjust these Y values as needed for each weekly banner
    "WeeklyBanner1": 50,
    "WeeklyBanner2": 50,
    "WeeklyBanner3": 55,
    "WeeklyBanner4": 50
};

// Get the current file path to extract week number
const filePath = tp.file.path(true);
const weekMatch = filePath.match(/(\d{4})-W(\d{2})/);

if (weekMatch) {
    const year = weekMatch[1];
    const weekNum = parseInt(weekMatch[2], 10);
    
    // Determine which banner to use based on week number
    // Use modulo to cycle through the 4 banners (1-4)
    const bannerIndex = (weekNum % 4) + 1;
    const bannerBaseName = `WeeklyBanner${bannerIndex}`;
    
    // Try to find the correct file extension
    let bannerExt = 'png'; // Default
    const baseFolder = window?.timeGarden?.rootPath.substring(1) + '06 Templates/Images/Weekly Notes';
    const extensions = ['png', 'gif', 'jpg', 'jpeg', 'webp'];

    for (const ext of extensions) {
        const filePath = `${baseFolder}/${bannerBaseName}.${ext}`;
        const file = app.vault.getAbstractFileByPath(filePath);
        if (file) {
            bannerExt = ext;
            break;
        }
    }
    
    // Get the Y value from config (or use a default of 30)
    const bannerYValue = weeklyBannerConfigs[bannerBaseName] || 30;
    
    // Generate the YAML frontmatter
    tR += `banner:
  - - ${bannerBaseName}.${bannerExt}
banner-y: ${bannerYValue}
banner-x: 30
content-start: 200
banner-display: cover
banner-repeat: true
banner-height: 400
banner-fade: -75
banner-radius: 25`;
} else {
    // If not a weekly note, add a comment instead
    tR += `# Not a weekly note - banner not applied`;
}
_%>