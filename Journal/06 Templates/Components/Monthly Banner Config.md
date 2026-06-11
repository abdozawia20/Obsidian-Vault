<%* /* Time Garden templater component*/ 
// Configuration for monthly banners
const monthlyBannerConfigs = {
    // You can adjust these Y values as needed for each monthly banner
    "MonthlyBanner1": 10,
    "MonthlyBanner2": 50,
    "MonthlyBanner3": 30,
    "MonthlyBanner4": 50
};

// Get the current file path to extract month number
const filePath = tp.file.path(true);
const monthMatch = filePath.match(/(\d{4})-(\d{2})-([A-Za-z]+)/);

if (monthMatch) {
    const year = monthMatch[1];
    const monthNum = parseInt(monthMatch[2], 10);
    
    // Determine which banner to use based on month number
    // Use modulo to cycle through the 4 banners (1-4)
    const bannerIndex = (monthNum % 4) + 1;
    const bannerBaseName = `MonthlyBanner${bannerIndex}`;
    
    // Try to find the correct file extension
    let bannerExt = 'gif'; // Default
    const baseFolder = window?.timeGarden?.rootPath.substring(1) + '06 Templates/Images/Monthly Notes';
    const extensions = ['gif', 'jpg', 'jpeg', 'png', 'webp'];

    for (const ext of extensions) {
        const filePath = `${baseFolder}/${bannerBaseName}.${ext}`;
        const file = app.vault.getAbstractFileByPath(filePath);
        if (file) {
            bannerExt = ext;
            break;
        }
    }
    
    // Get the Y value from config (or use a default of 30)
    const bannerYValue = monthlyBannerConfigs[bannerBaseName] || 30;
    
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
    // If not a monthly note, add a comment instead
    tR += `# Not a monthly note - banner not applied`;
}
_%>