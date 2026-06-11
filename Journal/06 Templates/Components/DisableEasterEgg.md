<%* /* Time Garden templater component*/ 
// DisableSharePrompt.md
// This script updates the frontmatter of "a small favor..." note to disable it

// Get the file object for the share letter
const shareLetterPath = window?.timeGarden?.rootPath.substring(1) + "07 Notes/Extras/A secret garden within the garden.";
const shareLetterFile = app.vault.getAbstractFileByPath(shareLetterPath + ".md");

if (shareLetterFile) {
    try {
        // Read the current content
        const content = await app.vault.read(shareLetterFile);
        
        // Update the frontmatter to set showYourself to false
        const updatedContent = content.replace(
            /showYourself:\s*(true|false)/i,
            "showYourself: false"
        );
        
        // Write the updated content back
        await app.vault.modify(shareLetterFile, updatedContent);
        
        // Show notification
        new Notice("Personal Letter disabled for future daily notes");
    } catch (error) {
        console.error("Error updating share letter:", error);
        new Notice("Error updating share letter: " + error.message);
    }
} else {
    new Notice("Could not find the share letter file");
    console.error("Could not find the share letter file at path:", shareLetterPath);
}
%>