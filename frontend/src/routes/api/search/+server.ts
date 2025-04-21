import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import type { SearchQuery, SearchResponse } from '$lib/types';

export const POST: RequestHandler = async ({ request, fetch }) => {
    const body: SearchQuery = await request.json();

    try {
        const response = await fetch('http://localhost:8001/search', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(body)
        });

        if (!response.ok) {
            throw new Error(`API responded with status: ${response.status}`);
        }

        const result: SearchResponse = await response.json();
        return json(result)
    } catch (error) {
        console.error('Error fetching search results:', error);
        return json({ result: [] }, { status: 500 })
    }
}