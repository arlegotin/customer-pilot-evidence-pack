---
license: mit
pretty_name: keenbench results
configs:
  - config_name: news
    data_files: runs/*/fresh.jsonl
    default: true
  - config_name: finance
    data_files: runs/*/gold.jsonl
  - config_name: scholar
    data_files: runs/*/scholar.jsonl
---
