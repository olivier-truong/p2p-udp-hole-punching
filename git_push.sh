#!/bin/bash

git add .
git commit -m "commit-$(date '+%Y-%m-%d %H:%M:%S')"
git push
