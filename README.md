# Agent<sup>2</sup> 🏠

[![Built at GenAI Genesis 2026](https://img.shields.io/badge/GenAI_Genesis-2026-blue)](#)

**Agent<sup>2</sup>** is an agentic real estate agent that finds your next home entirely via text message. No apps, no accounts, no forms. Just text us, tell us what you need, and get matched listings sent directly to your phone, and our agent will message the sellers on the listings you like!

## Features ✨

- **Conversational Interface:** Communicate naturally via SMS, powered by Twilio webhooks.
- **AI Criteria Extraction:** Uses advanced LLMs (via `railtracks` and OpenAI-compatible endpoints) to extract structured search criteria (location, intent, max price, beds, baths) from your text messages.
- **FastAPI Backend:** High-performance, async backend to handle robust conversation state and API rendering.
- **Sleek Landing Page:** A modern, responsive frontend that showcases the product and lets users initiate texts with a single click.
- **Data Gathering:** Uses combinations of `Playwright`, `BeautifulSoup4`, and `pandas` to scrape, format, and push listings.

## How It Works 🛠️

1. **Text Us:** Send a quick text to our dedicated Twilio number.
2. **Tell Us What You Need:** Our AI will ask you a series of questions about your budget, preferred area, move-in date, and deal-breakers.
3. **Get Matches:** We parse your structured criteria, match you with the best available real estate listings, and text you the results directly—ready to view!

## Tech Stack 🚀

- **Backend:** Python 3, FastAPI, Uvicorn
- **AI / NLP:** Context extraction using `railtracks` and custom LLMs (GPT-OSS) 
- **Communications:** Twilio SMS API
- **Frontend:** HTML5, CSS3 (Custom styles), Vanilla JS
- **Scraping / Data:** Playwright, BeautifulSoup4, Pandas, lxml

## Setup & Installation ⚙️

### 1. Clone the repository
```bash
git clone <repository-url>
cd genaigenesis2026
```

### 2. Install dependencies
Create a virtual environment and install the required Python packages:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Environment Variables
Copy the `.env.example` file to `.env`:
```bash
cp .env.example .env
```
Fill out the variables in `.env` with your actual credentials for Twilio and your configured LLM (OpenAI-compatible) platform.

### 4. Run the Application
Start the development server using Uvicorn:
```bash
uvicorn app.main:app --reload
```
The application, including both the backend API and the static frontend, will be served at `http://localhost:8000`.

---
*Built with ❤️ during the GenAI Genesis 2026 Hackathon.*
