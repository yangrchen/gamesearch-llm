# API Endpoints

## Base URL

- Production: `https://api.gamesearch.app`
- Development: `http://localhost:8000`

## Endpoints

### Search Games

Search for games using natural language queries.

**Endpoint**: `POST /search`

**Request Body**:

````json
{
  "query": "string",
  "use_vector_search": false,
  "pagination_metadata": {
    "page": 1,
    "page_size": 20
  }
}

**Response**:

```json
{
  "query": "string",
  "use_vector_search": false,
  "pagination_metadata": {
    "page": 1,
    "page_size": 20,
    "has_next_page": true
  },
  "result": [
    {
      "_id": 1,
      "name": "string",
      "first_release_date": "2023-01-01",
      "genres": ["string"],
      "summary": "string"
    }
  ],
  "signature": "string"
}
````

**Status Codes**:

- `200`: Success
- `400`: Bad request (empty query)
- `422`: Query cannot be processed
- `500`: Internal error

### Health Check

**Endpoint**: `GET /health`

**Response**:

```json
{
    "status": "string"
}
```

**Status Codes**:

- `200`: Success
- `500`: Internal error
