<%* /* Time Garden templater component*/ 
// Configuration for quarterly banners
const quarterlyBannerConfigs = {
    // You can adjust these Y values as needed for each quarterly banner
    "QuarterlyBanner1": 50,
    "QuarterlyBanner2": 50,
    "QuarterlyBanner3": 55,
    "QuarterlyBanner4": 50
};

// Get the current file path to extract quarter number
const filePath = tp.file.path(true);
const quarterMatch = filePath.match(/(\d{4})-Q(\d)/);

if (quarterMatch) {
    const year = quarterMatch[1];
    const quarterNum = parseInt(quarterMatch[2], 10);
    
    // Determine which banner to use based on quarter number
    // Just use the quarter number directly (1-4)
    const bannerBaseName = `QuarterlyBanner${quarterNum}`;
    
    // Try to find the correct file extension
    let bannerExt = 'gif'; // Default
    const baseFolder = window?.timeGarden?.rootPath.substring(1) + '06 Templates/Images/Quarterly Notes';
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
    const bannerYValue = quarterlyBannerConfigs[bannerBaseName] || 30;
    
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
    // If not a quarterly note, add a comment instead
    tR += `# Not a quarterly note - banner not applied`;
}
_%>