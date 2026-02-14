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
```
## 🧪 Example Usage
**Daily files**
```bash
python chatgpt_json_to_period_md.py conversations.json out_md --split daily --tz Asia/Tokyo
```
**Monthly files**
```bash
python chatgpt_json_to_period_md.py conversations.json out_md --split daily --tz Asia/Tokyo
```
**Weekly files starting Monday**
```bash
python chatgpt_json_to_period_md.py conversations.json out_md --split weekly --week-start mon --tz Asia/Tokyo
```
**Biweekly files starting Sunday**
```bash
python chatgpt_json_to_period_md.py conversations.json out_md --split biweekly --week-start sun --tz Asia/Tokyo
```
**Daily files grouped into month folders**
```bash
python chatgpt_json_to_period_md.py conversations.json out_md --split daily --group-by-month --tz Asia/Tokyo
```
**Weekly files grouped by month folders**
```bash
python chatgpt_json_to_period_md.py conversations.json out_md --split weekly --group-by-month --week-start mon --tz Asia/Tokyo
```
**Biweekly files grouped by month folders**
```bash
python chatgpt_json_to_period_md.py conversations.json out_md --split biweekly --week-start sun --group-by-month --tz Asia/Tokyo
```
## 📂 Example Output Structure
Without --group-by-month:
```yaml
out_md/
├── 2026-02-01.md
├── 2026-02-08.md
└── 2026-02-15.md
```

With --group-by-month:
```yaml
out_md/
└── 2026-02/
    ├── 2026-02-01.md
    ├── 2026-02-08.md
    └── 2026-02-15.md
```
## 📜 License
MIT License

