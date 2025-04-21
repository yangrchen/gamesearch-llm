<script lang="ts">
	import type { Game } from '$lib/types';

	let searchQuery = $state('');
	let games = $state<Game[]>([]);
	let loading = $state(false);
	let error = $state<string | null>(null);
	
	let searchDisabled = $derived(loading || (searchQuery.trim() === ''))

	async function searchGames() {
		if (searchDisabled) return;
		loading = true;

		try {
			const response = await fetch('/api/search', {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json'
				},
				body: JSON.stringify({ query: searchQuery })
			});

			if (!response.ok) {
				throw new Error(`Search failed with status: ${response.status}`);
			}

			const data = await response.json();
			games = data.result;
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to search games';
			games = [];
		} finally {
			loading = false;
		}
	}

	function handleSubmit(event: Event) {
		event.preventDefault();
		searchGames();
	}
</script>

<svelte:head>
	<title>Gamesearch</title>
</svelte:head>

<div class="container mx-auto px-24 py-8">
	<form onsubmit={handleSubmit} class="mb-8">
		<div class="relative flex w-full items-center justify-center gap-4">
			<input
				type="text"
				bind:value={searchQuery}
				placeholder="Search for games by title, genre, release date using natural language..."
				class="w-full rounded-lg border border-gray-300 bg-gray-100 p-2 focus:border-transparent focus:ring-2 focus:ring-blue-500"
			/>
			<button
				type="submit"
				class={[
					'absolute right-1 flex cursor-pointer rounded-lg  p-2.5 font-bold text-white transition',
					searchDisabled && 'bg-gray-400', !searchDisabled && 'bg-purple-800 hover:bg-purple-900'
				]}
				disabled={loading}
			>
				<span class="icon-[material-symbols--search-rounded]"></span>
			</button>
		</div>
	</form>
</div>
