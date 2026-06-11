<%* /* Time Garden templater component*/ 
// Configuration for yearly banners
const yearlyBannerConfigs = {
    // You can adjust these Y values as needed for the yearly banner
    "YearlyBanner": 50
};

// Get the current file path to extract year
const filePath = tp.file.path(true);
const yearMatch = filePath.match(/(\d{4})/);

if (yearMatch) {
    const year = yearMatch[1];
    
    // Use a single banner for all years
    const bannerBaseName = "YearlyBanner";
    
    // Try to find the correct file extension
    let bannerExt = 'jpg'; // Default
    const baseFolder = window?.timeGarden?.rootPath.substring(1) + '06 Templates/Images/Yearly Notes';
    const extensions = ['jpg', 'jpeg', 'png', 'gif', 'webp'];

    for (const ext of extensions) {
        const filePath = `${baseFolder}/${bannerBaseName}.${ext}`;
        const file = app.vault.getAbstractFileByPath(filePath);
        if (file) {
            bannerExt = ext;
            break;
        }
    }
    
    // Get the Y value from config (or use a default of 30)
    const bannerYValue = yearlyBannerConfigs[bannerBaseName] || 30;
    
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
    // If not a yearly note, add a comment instead
    tR += `# Not a yearly note - banner not applied`;
}
_%>