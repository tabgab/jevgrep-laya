#!/bin/zsh
cd "${LAYA_EVAL_DATA:-$(dirname $0)/results}" && mkdir -p repos
python3 -c "import json;[print(t['id'],t['repo'],t['base_commit']) for t in json.load(open('tasks.json'))]" | while read id repo commit; do
  d=repos/$id
  [ -d $d/.git ] && continue
  git init -q $d && git -C $d remote add origin https://github.com/$repo.git &&
  git -C $d fetch -q --depth 1 origin $commit && git -C $d checkout -q FETCH_HEAD && echo "ok $id" || echo "FAIL $id"
done
echo ALLDONE
