# Sunday Deadline Checklist

## 14:15 CET -- REPO PREPARATION (15 min before public)
- [ ] All agents commit and push final work
- [ ] Merge all agent branches into main: `git merge agent-cv agent-ml agent-nlp agent-ops`
- [ ] Push main: `git push origin main`
- [ ] Verify LICENSE file exists (MIT): `cat LICENSE`
- [ ] Make repo public: `gh repo edit --visibility public`
- [ ] Verify public: `gh repo view --json isPrivate`

## 14:45 CET -- REPO GOES PUBLIC (PRIZE ELIGIBILITY)
- [ ] Confirm repo is public
- [ ] Confirm LICENSE is MIT
- [ ] Check all branches are pushed: `git branch -r`

## 15:00 CET -- COMPETITION ENDS
- [ ] Final scores recorded
- [ ] No more submissions accepted

## Pre-Flight (do Saturday evening)
- [ ] Push all branches (backup)
- [ ] Verify no secrets in repo: grep for API keys, tokens, passwords
- [ ] Check .gitignore covers: .env, .astar_token, .auth/
- [ ] Delete any GCP VMs still running (save credits)
