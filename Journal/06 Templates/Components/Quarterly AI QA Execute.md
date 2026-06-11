<%* /* Time Garden templater component*/ 
// Import required modules
tR = ""
const quarterlyOps = window?.timeGarden?.quarterly;;

// Get current file
const currentFile = tp.file.find_tfile(tp.file.title);

// Read frontmatter to get the question
const frontmatter = tp.frontmatter;
const question = frontmatter.aiQuestion || "";

// Clear query
app.fileManager.processFrontMatter(currentFile, (frontmatter) => {
    delete frontmatter['aiQuestion'] 
});

if (!question.trim()) {
    new Notice("Please enter a question first.");
    return;
}

try {
    // Process QA
    const result = await quarterlyOps.generateQA(tp, app, question);
    
    // If successful, update the frontmatter
    if (result.success) {
        await app.fileManager.processFrontMatter(currentFile, fm => {
            fm.aiAnswer = result.answer;
            return fm;
        });
    } else {
        // Update with error message
        await app.fileManager.processFrontMatter(currentFile, fm => {
            fm.aiAnswer = `Error: ${result.error}. Please try again with a different question.`;
            return fm;
        });
    }
} catch (error) {
    console.error("Error processing Quarterly AI Q&A:", error);
    new Notice(`Error: ${error.message}`);
    
    // Update with error message
    await app.fileManager.processFrontMatter(currentFile, fm => {
        fm.aiAnswer = `Error: ${error.message}. Please try again with a different question.`;
        return fm;
    });
}
-%>