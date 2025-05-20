# This script pushes the backend code to GitHub

# Set the GitHub repository URL
$repoUrl = "https://github.com/dhanujdev/codedocgen-backend.git"

# Set the branch name
$branchName = "main"

Write-Host "Pushing to GitHub repository: $repoUrl"

# Set remote origin if not already set
git remote -v | Select-String -Pattern "origin" -Quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "Setting up remote origin..."
    git remote add origin $repoUrl
}

# Push to GitHub
Write-Host "Pushing to branch: $branchName..."
git push -u origin $branchName

Write-Host "Done! Check GitHub repository for changes." 