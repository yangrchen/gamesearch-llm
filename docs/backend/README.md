# Backend Documentation

## Overview

The backend is built with FastAPI and uses LangGraph for agent orchestration. It connects to MongoDB Atlas for data storage and implements both traditional NoSQL query and vector search capabilities.

## Tech Stack

- **Language**: Python 3.12+
- **Framework**: FastAPI
- **AI/ML**: LangGraph, Anthropic Claude, VoyageAI
- **Database**: MongoDB Atlas with Motor

## Project Structure

```
backend/
├── src/
│   └── backend/
│       └── main.py     # FastAPI application entry point
└── pyproject.toml      # Project dependencies
```

## Key Features

1. **Natural Language Query Processing**: Converts user queries to MongoDB queries
2. **Vector Search**: Embedding search using VoyageAI embeddings
3. **Safety Evaluation**: Query validation and content filtering
4. **Pagination**: Support for paginating through large result sets

## Setup and Configuration

See [setup-and-config.md](./setup-and-config.md) for detailed setup instructions.

## API Endpoints

For detailed API documentation, see [API Endpoints](../api/README.md).
