# Git Repository Setup Instructions

## Step 1: Initialize Git Repository
```bash
git init
```

## Step 2: Add all files
```bash
git add .
```

## Step 3: Create initial commit
```bash
git commit -m "Initial commit: HVM Panel V3.1"
```

## Step 4: Add your remote repository

### If you already have a repository on GitHub/GitLab/etc:
```bash
git remote add origin <YOUR_REPOSITORY_URL>
```

### If you need to create a new repository:
1. Go to GitHub/GitLab and create a new repository
2. Copy the repository URL (e.g., `https://github.com/yourusername/your-repo.git`)
3. Run the command above with your URL

## Step 5: Push to remote repository
```bash
git branch -M main
git push -u origin main
```

## Alternative: If you want to push to an existing repository
```bash
git remote add origin <YOUR_REPOSITORY_URL>
git branch -M main
git push -u origin main
```
