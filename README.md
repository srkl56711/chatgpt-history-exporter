# chatgpt-history-exporter

A Python tool that converts ChatGPT `conversations.json`
into period-based Markdown files (daily, weekly, biweekly, monthly).

Optimized for **Obsidian** to prevent freezing caused by large Markdown files.

---

## ✨ Features

- Split conversation history by:
  - `daily`
  - `weekly`
  - `biweekly`
  - `monthly`
- Optional monthly folder grouping (`--group-by-month`)
- Configurable week start (`mon` or `sun`)
- Timezone support
- Designed to avoid large Markdown files that may cause Obsidian to freeze

### Why this tool?

When splitting only by `monthly`, generated Markdown files can become very large.  
Large files may cause **Obsidian to freeze while creating indexes**.

This tool allows splitting by `weekly` or `biweekly` to keep file sizes manageable and Obsidian-friendly.

---

## 🐍 Requirements

- Python 3.9+

Install required packages:

```bash
python -m pip install tzdata ijson

