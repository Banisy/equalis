# Equalis Prep Generator —

**Generate unlimited CFA-style mock exams from your own study materials using AI.**

Built for students, by students. Because knowledge should be accessible to everyone. 🎓

---

## What It Does

1. **Upload** your CFA study PDFs (Kaplan Schweser, Wiley, CFAI curriculum, etc.)
2. **Process** — the tool extracts and chunks text by topic area
3. **Generate** — Cohere AI creates CFA Level I style MCQs from your materials
4. **Exam** — take timed mock exams with proper topic weighting, flagging, and navigation
5. **Review** — detailed score breakdown by topic with explanations for every question

## Features

- 🎯 **CFA L1 topic weighting** — exams match actual topic weights (Ethics 15-20%, FSA 11-14%, etc.)
- ⏱️ **Timed exam mode** — 4.5 hours for 180 questions, just like the real thing
- 📊 **Score breakdown** — see your performance by topic to identify weak areas
- 🔖 **Flag & review** — flag questions during the exam, review incorrect/flagged after
- ⌨️ **Keyboard shortcuts** — A/B/C to answer, F to flag, arrows to navigate
- 💾 **Persistent question bank** — questions stored locally in SQLite, never regenerated twice
- 🔒 **100% local** — your data stays on your machine (only API calls go to Cohere)

## Quick Start

### 1. Install Python 3.9+

Make sure you have Python installed. Check with:
```bash
python --version
```

### 2. Clone / Download

```bash
git clone <this-repo>
cd cfa-mock-generator
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Get a Cohere API Key (Free)

1. Go to [dashboard.cohere.com](https://dashboard.cohere.com/api-keys)
2. Sign up for a free account
3. Create an API key (the free tier has generous limits)

### 5. Run

```bash
python backend/app.py
```

Then open **http://localhost:5000** in your browser.

### 6. Configure

1. Go to **Settings** tab
2. Paste your Cohere API key
3. Go to **Materials** tab and upload your PDFs
4. Click **Process** on each uploaded file
5. Go to **Generate** tab and click **Generate All Questions**
6. Once questions are generated, go to **Exams** and create a mock exam!

## How It Works

### PDF Processing
- Text is extracted from PDFs using `pdfplumber`
- Content is chunked into ~2000-character segments
- Each chunk is auto-tagged with a CFA topic area via keyword detection

### Question Generation
- Each chunk is sent to Cohere's Command R+ model with a carefully crafted prompt
- The AI generates 5 MCQs per chunk in CFA exam format (3 answer choices)
- Questions include difficulty rating, subtopic, and detailed explanations
- All questions are stored in a local SQLite database

### Exam Assembly
- Questions are sampled from the bank with CFA L1 topic weights
- Previously shown questions are deprioritized (least-shown-first selection)
- Full timer, navigation grid, and flagging system

## CFA Level I Topic Weights

| Topic | Weight |
|-------|--------|
| Ethical and Professional Standards | 15-20% |
| Quantitative Methods | 6-9% |
| Economics | 6-9% |
| Financial Statement Analysis | 11-14% |
| Corporate Issuers | 6-9% |
| Equity Investments | 9-12% |
| Fixed Income | 9-12% |
| Derivatives | 5-8% |
| Alternative Investments | 5-8% |
| Portfolio Management | 8-12% |

## Project Structure

```
cfa-mock-generator/
├── backend/
│   └── app.py              # Flask server, PDF processing, question generation
├── frontend/
│   └── index.html           # Complete exam UI (single-page app)
├── data/                    # Auto-created at runtime
│   ├── questions.db         # SQLite question bank
│   ├── config.json          # API key storage
│   └── uploads/             # Uploaded PDFs
├── requirements.txt
└── README.md
```

## Tips for Best Results

- **Upload topic-specific PDFs** for better topic detection (e.g., separate Ethics, FSA, Fixed Income books)
- **Set questions per chunk to 5-7** for a good quality/quantity balance
- **Generate in batches** — if you have 3000 pages, it'll take a while. Be patient, let the API do its thing
- **Use the API delay setting** to avoid rate limits (2 seconds works well for Cohere free tier)
- **Review your incorrect answers** — the explanations are very helpful for learning

## Tech Stack

- **Backend**: Python, Flask, SQLite, pdfplumber
- **Frontend**: Vanilla HTML/CSS/JS (zero dependencies, instant load)
- **AI**: Cohere Command R+ (free tier)

## License

MIT — use it, share it, improve it. Knowledge is for everyone.

## Contributing

PRs welcome! Some ideas for improvement:
- Vignette-style item sets (multi-question scenarios)
- Spaced repetition for weak topics
- Performance analytics over time
- Support for CFA Level II and III
- Alternative LLM backends (Ollama for fully offline, OpenAI, etc.)
