# VEDIX – AI-Assisted Code Review System

VEDIX is an AI-assisted code review and software quality assessment platform designed to analyze source code, identify potential issues, detect code smells, evaluate security patterns, and provide actionable recommendations.

It combines traditional static analysis techniques with AI-powered code review to help developers understand and improve their code quality.

## Features

- **Static Code Analysis:** Analyze Python source code using AST-based analysis.
- **Code Quality Analysis:** Identify code quality issues using Ruff.
- **Security Analysis:** Detect potential security vulnerabilities using Bandit.
- **Code Smell Detection:** Identify issues such as Long Method, Large Class, Deep Nesting, Too Many Parameters, and High Complexity.
- **AI-Powered Review:** Generate contextual code review comments and improvement suggestions.
- **Code Metrics:** Calculate lines of code, cyclomatic complexity, nesting depth, documentation coverage, and other metrics.
- **Review History:** Store and retrieve previous code analysis reports.
- **Report Management:** Preserve analysis results for future reference.

## Technology Stack

### Frontend
- React
- TypeScript
- Vite
- Tailwind CSS
- Monaco Editor

### Backend
- Python
- FastAPI
- Uvicorn

### Code Analysis
- Python AST
- Ruff
- Bandit
- Custom code smell detection
- Large Language Models (LLMs)

## Project Structure

```text
VEDIX/
│
├── backend/
│   ├── app/
│   ├── requirements.txt
│   └── ...
│
├── frontend/
│   ├── src/
│   ├── package.json
│   └── ...
│
├── data/
│
├── README.md
└── ...
```

*The structure above is illustrative. Adjust it to match the actual repository.*

## Prerequisites

Make sure the following tools are installed:

| Software | Recommended version |
|---|---|
| Python | 3.10 or later |
| Node.js | 20 or later |
| npm | Compatible with installed Node.js |
| Git | Latest stable version |

Check your installations:

```bash
python --version
node --version
npm --version
git --version
```

## Installation and Setup

### 1. Clone the Repository

```bash
git clone https://github.com/c0derashish/ai-code-reviewer.git
cd VEDIX
```

### 2. Backend Setup

Navigate to the backend directory:

```bash
cd backend
```

Create a virtual environment:

**Windows:**

```powershell
python -m venv venv
venv\Scripts\activate
```

**Linux/macOS:**

```bash
python3 -m venv venv
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create a `.env` file in the backend directory if your configuration requires one.

Example configuration:

```env
# AI Provider Configuration
AI_PROVIDER=
AI_API_KEY=
AI_MODEL=

# Database Configuration
DATABASE_URL=

# Application Configuration
DEBUG=false
```

Fill in the values according to your configured AI provider and database.

**Important:** Never commit API keys, passwords, or other secrets to GitHub. Keep `.env` excluded through `.gitignore`.

### 4. Start the Backend Server

From the backend directory, run:

```bash
uvicorn api.main:app --reload
```

If your FastAPI entry point is located elsewhere, update the module path accordingly.

The backend should be accessible at:

```text
http://127.0.0.1:8000
```

API documentation:

```text
http://127.0.0.1:8000/docs
```

Health check:

```text
http://127.0.0.1:8000/health
```

### 5. Frontend Setup

Open a new terminal and navigate to the frontend directory:

```bash
cd frontend
```

Install the dependencies:

```bash
npm install
```

Start the development server:

```bash
npm run dev
```

The frontend will usually be available at:

```text
http://localhost:5173
```

Use the URL printed by Vite if the port is different.

## Running the Complete Application

Start both servers in separate terminals.

**Terminal 1 – Backend**

```bash
cd backend
venv\Scripts\activate
uvicorn api.main:app --reload
```

**Terminal 2 – Frontend**

```bash
cd frontend
npm run dev
```

Open the frontend in your browser and start using VEDIX.

## API Endpoints

The following endpoints represent the current documented backend interface. Check the running API documentation for the latest implementation.

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Check backend health |
| POST | `/analyses` | Submit source code for analysis |
| GET | `/analyses/{id}` | Retrieve an analysis result |

## How to Use VEDIX

1. Start the frontend and backend servers.
2. Open the VEDIX application.
3. Upload or provide source code through the available interface.
4. Start the code analysis process.
5. Wait for the analysis pipeline to complete.
6. Review the generated metrics, code smells, security findings, and AI recommendations.
7. Access previously saved analysis reports through the history feature, where available.

## Analysis Pipeline

VEDIX follows a multi-stage analysis workflow:

```text
Source Code Input
       |
       v
Input Validation
       |
       v
Language Detection
       |
       v
AST-Based Analysis
       |
       v
Feature Extraction
       |
       v
Ruff + Bandit Analysis
       |
       v
Custom Code Smell Detection
       |
       v
AI-Powered Code Review
       |
       v
Finding Validation
       |
       v
Consolidated Analysis Report
```

AI-powered review depends on valid provider configuration. Without it, the static analysis components can operate independently where supported.

## Important Notes

- Python is the primary language supported by the static-analysis pipeline.
- Language recognition does not necessarily mean that all static-analysis features are supported for that language.
- AI-generated findings are suggestions and should be reviewed by developers.
- VEDIX analyzes source code statically; it does not establish runtime correctness by executing the submitted code.
- AI review may transmit source code to an external AI provider when that feature is enabled. Do not submit confidential code without appropriate authorization.
- Analysis results and report retention depend on the configured database and storage implementation.

## Troubleshooting

**Backend fails to start**

- Verify that the virtual environment is activated.
- Check that all Python dependencies are installed.
- Verify the FastAPI application entry point.
- Check the terminal for missing environment variables.

**Frontend fails to start**

- Verify Node.js and npm installations.
- Run `npm install` again.
- Check the frontend terminal for dependency or port errors.

**AI review is unavailable**

- Verify the AI provider configuration.
- Check the API key and model name.
- Ensure the selected provider is accessible.

**Static analysis fails**

- Verify that the uploaded source files are supported.
- Check that Ruff and Bandit are installed.
- Inspect the backend logs for file-processing errors.

## Security

- Never expose API keys in frontend code.
- Do not commit `.env` files.
- Treat uploaded source code and repository content as untrusted input.
- Avoid executing untrusted repository code during analysis.

## Future Scope

- Extended multi-language static analysis.
- GitHub repository integration.
- Advanced report generation and export.
- Improved review-history comparison.
- More comprehensive code quality evaluation.
- Human-assisted and AI-assisted review evaluation.

## Contributors

**VEDIX – AI-Assisted Code Review System**

Developed as an academic project by:

- Ashish Chandra
- Anuj Agrawal
- Alisha Khan
- Mayank Bareth

**Project Guide:** Dr. Vibha Pandey

**Institution:** Shri Shankaracharya Technical Campus, Bhilai

---

*For questions, suggestions, or bug reports, please open an issue in the project repository.*