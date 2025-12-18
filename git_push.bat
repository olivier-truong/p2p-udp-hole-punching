git add .
powershell -Command "git commit -m commit-$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
git push
