export interface Game {
	_id: number;
	name: string;
	first_release_date: string;
	franchises?: string[];
	genres?: string[];
	summary: string;
	Last_updated: string;
}

export interface SearchQuery {
	query: string;
	use_vector_search: boolean;
}

export interface SearchResponse {
	result: Game[];
}
