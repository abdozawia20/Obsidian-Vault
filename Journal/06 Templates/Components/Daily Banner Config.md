<%* /* Time Garden templater component*/ 

// just hardcoded y values for the banners to look best. Adjust as you need.
const bannerConfigs = {
    Monday: 49,
    Tuesday: 50,
    Wednesday: 50,
    Thursday: 30,
    Friday: 30,
    Saturday: 0,
    Sunday: 2
};

// Get day of daily note
const today = moment(tp.file.title, 'YYYY-MM-DD').format("dddd");

// Try to find the correct file extension
let bannerExt = 'gif'; // Default
let baseFolder =  window?.timeGarden?.rootPath.substring(1) + '06 Templates/Images/Daily Notes';
console.log("BASEFOLDER", baseFolder);
const extensions = ['gif', 'jpg', 'jpeg', 'png', 'webp'];

for (let ext of extensions) {
    let filePath = `${baseFolder}/${today}Banner.${ext}`;
    let file = tp.app.vault.getAbstractFileByPath(filePath);
    if (file) {
        bannerExt = ext;
        break;
    }
}

// Add banner yaml properties, including the fitting y-value
tR += `banner:
  - - ${today}Banner.${bannerExt}
banner-y: ${bannerConfigs[today]}
banner-x: 30
content-start: 200
banner-display: cover
banner-repeat: true
banner-height: 400
banner-fade: -75
banner-radius: 25`;
_%>