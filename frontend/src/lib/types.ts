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
	use_vector_search?: boolean;
	page?: number;
	page_size?: number;
	processed_output?: any;
	vector_embedding?: number[];
}

export interface SearchResponse {
	query: string;
	use_vector_search: boolean;
	result: Game[];
	page: number;
	page_size: number;
	has_next_page: boolean;
	total_count?: number;
	processed_output?: any;
	query_type?: string;
	projection?: Record<string, number>;
	vector_embedding?: number[];
	evaluation_output?: {
		is_allowed: boolean;
		violation_reason?: string;
	};
	error?: string;
}
