# Gamesearch

AI-powered search engine that allows users to find games using natural language queries. Features both traditional database search and vector similarity search for discovering games based on themes, gameplay mechanics, and concepts.

## 🎮 Live Demo

[Visit Gamesearch](https://gamesearch.app)

## ✨ Features

- **Natural Language Search**: Search for games using everyday language
- **Dual Search Modes**:
    - **Traditional Search**: Converts user queries to MongoDB queries for structured searches
    - **AI Similarity Search**: Uses embeddings to find games with similar themes, gameplay, or concepts
- **Modern UI**: Built with SvelteKit and TailwindCSS
- **Content Safety**: Built-in guardrails to ensure appropriate search queries

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │    Backend      │    │   Database      │
│   (SvelteKit)   │───▶│   (FastAPI)     │───▶│   (MongoDB)     │
│                 │    │   + LangGraph   │    │   + Atlas       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                               │
                       ┌───────▼───────┐
                       │  ETL Pipeline │
                       │  (Go Lambdas) │
                       └───────────────┘
```

## 🚀 Local Development Quickstart

### Prerequisites

- Python 3.12+
- uv
- Node.js 18+
- pnpm
- MongoDB Atlas account
- AWS Account (for deployment)
- Anthropic API key
- Voyage AI API key

### Steps

1. **Clone the repository**:

```bash
git clone <repository-url>
cd gamesearch
```

2. **Setup environment variables**

Create `.env` files in both `backend/` and `frontend/` directories:

**Backend (.env)**:

```env
MONGODB_URI=mongodb+srv://your-connection-string
ANTHROPIC_API_KEY=your-anthropic-key
VOYAGE_API_KEY=your-voyage-key
GAMESEARCH_SECRET_KEY=your-secret-key
ALLOWED_ORIGINS=http://localhost:5173,https://your-domain.com
```

**Frontend (.env)**:

```env
PUBLIC_API_URL=http://localhost:8000/search
```

2. **Start the backend**:

```bash
cd backend
uv sync
uv run gamesearch-backend
```

3. **Start the frontend**:

```bash
cd frontend
pnpm install
pnpm dev
```

4. **Access the application**:

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs

## 🔧 Tech Stack

### Backend

- **FastAPI**: Modern Python web framework
- **LangGraph**: AI workflow orchestration
- **Motor**: Async MongoDB driver
- **Langchain**: AI/LLM integration
- **Anthropic Claude**: Query processing and guardrails
- **Voyage AI**: Text embeddings

### Frontend

- **SvelteKit**: Full-stack web framework
- **TailwindCSS**: Utility-first CSS framework
- **TypeScript**: Type-safe JavaScript

### Infrastructure

- **AWS Fargate**: Containerized backend hosting
- **AWS Lambda**: ETL processing
- **MongoDB Atlas**: Database with vector search
- **Terraform**: Infrastructure as code
