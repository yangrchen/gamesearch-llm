# Frontend Documentation

## Overview

The frontend is built with SvelteKit and provides a modern, responsive interface for searching for video games.

## Tech Stack

- **Language**: TypeScript
- **Framework**: SvelteKit
- **Styling**: TailwindCSS
- **Deployment**: AWS CloudFront + S3

## Project Structure

```
frontend/
├── src/
│   ├── routes/              # SvelteKit routes
│   ├── lib/
│   │   ├── components/      # Reusable components
│   │   └── types.ts         # Types
│   ├── app.html            # HTML template
│   └── app.d.ts            # Type definitions
├── static/                  # Static assets
└── svelte.config.js        # SvelteKit configuration
```

## Key Features

1. **Search Interface**: Modern search bar interface with responsive components
2. **Results Display**: Paginated game results
3. **Game Details**: Detailed game information views

## Setup and Configuration

See [setup-and-config.md](./setup-and-config.md) for detailed setup instructions and configuration options.

## Components

For component documentation, see [component.md](./components.md).
