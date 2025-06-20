export interface Game {
	_id: number;
	name: string;
	first_release_date: string;
	franchises?: string[];
	genres?: string[];
	summary: string;
	last_updated: string;
}

export interface UserState {
	query: string;
	use_vector_search: boolean;
	pagination_metadata: PaginationMetadata;
	vector_embedding?: number[] | null;
	processed_output?: MongoQueryOutput | null;
	signature?: string | null;
	result?: Game[] | null;
	violation?: string | null;
}

interface MongoQueryOutput {
	query: Record<string, any>[] | Record<string, any>;
	project: Record<string, number>;
	type: MongoQueryType;
}

interface PaginationMetadata {
	page: number;
	page_size: number;
	has_next_page: boolean;
}

enum MongoQueryType {
	SIMPLE = 'SIMPLE',
	AGGREGATE = 'AGGREGATE'
}
