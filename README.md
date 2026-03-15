# Agent<sup>2</sup>

[![Built at GenAI Genesis 2026](https://img.shields.io/badge/GenAI_Genesis-2026-blue)](#)

### Your Real Estate Agent Agent
**Agent<sup>2</sup>** is an AI real estate assistant that helps you find your next home through a simple conversation. No apps, no accounts, no forms. Just send a text to start, take a short call with the AI agent, and receive matched listings directly by text message.

## Features ✨

- **Simple Start via SMS:** Text the Agent² number to begin the process.
- **Voice Conversation:** The system calls you and asks about your housing preferences.
- **AI Criteria Extraction:** Uses LLMs (via `railtracks` and OpenAI-compatible endpoints) to convert natural conversation into structured search criteria such as location, budget, bedrooms, and bathrooms.
- **SMS Results:** Matching listings are sent directly to the user's phone via SMS.
- **FastAPI Backend:** High-performance backend that manages conversation state, listing queries, and responses.
- **Data Aggregation:** Uses `Playwright`, `BeautifulSoup`, and `pandas` to gather and normalize listing data from multiple sources.
- **Landing Page:** A simple web interface explaining the product and allowing users to initiate the experience.

## How It Works 🛠️

1. **Text Agent²**  
   Send a message to the Agent² phone number.

2. **Confirm the Call**  
   The agent replies and asks you to respond **YES** when you're ready for a short call.

3. **Describe Your Preferences**  
   The system calls you and asks about the home you're looking for.

4. **AI Extraction**  
   The conversation is processed to extract structured housing preferences.

5. **Get Matches**  
   The system searches listings and sends the most relevant homes back to you by SMS.

## Tech Stack 🚀

**Backend**
- Python
- FastAPI
- Uvicorn

**Voice Agent**
- PersonaPlex
- AWS

**AI / NLP**
- Railtracks
- OpenAI-compatible LLM endpoint

**Communication**
- Twilio (SMS and calls)

**Data Collection**
- Playwright
- BeautifulSoup
- Pandas
- lxml

**Frontend**
- HTML
- CSS
- JavaScript

## Setup & Installation ⚙️

### 1. Clone the repository
```bash
git clone https://github.com/chantalzhang/genaigenesis2026.git
cd genaigenesis2026
