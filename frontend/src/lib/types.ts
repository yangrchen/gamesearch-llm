export interface Game {
    _id: number;
    name: string;
    first_release_date: string;
    franchises?: string[];
    genres?: string[];
    summary: string;
    last_updated: string;
}

export interface SearchQuery {
    query: string;
}

export interface SearchResponse {
    result: Game[];
}