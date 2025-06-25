# Backend Setup and Configuration

This guide covers the complete setup and configuration process for the Gamesearch backend.

## Prerequisites

- Python 3.12+
- uv
- MongoDB Atlas account
- Anthropic API key (from [https://console.anthropic.com/](https://console.anthropic.com/))
- Voyage AI API key (from [https://voyageai.com/](https://voyageai.com/))

## Steps

1. **Clone the repository**

```bash
git clone https://github.com/yangrchen/gamesearch-llm.git
cd gamesearch/backend
```

2. **Configure environment variables**

```bash
# Edit .env with your configuration
cp .env.example .env
```

3. **Setup environment with uv and run backend script**

```bash
uv sync
uv run gamesearch-backend
```
