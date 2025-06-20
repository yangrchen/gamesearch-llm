<script lang="ts">
	import GameCard from '$lib/components/GameCard.svelte';
	import Pagination from '$lib/components/Pagination.svelte';
	import PageSizeSelector from '$lib/components/PageSizeSelector.svelte';
	import type { Game, UserState } from '$lib/types';
	import { PUBLIC_API_URL } from '$env/static/public';

	let searchQuery = $state('');
	let games = $state<Game[]>([]);
	let loading = $state(false);
	let error = $state<string | null>(null);
	let useVectorSearch = $state(false);
	let searchResponse = $state<UserState | null>(null);
	let currentPage = $state(1);
	let pageSize = $state(12);

	let searchDisabled = $derived(loading || searchQuery.trim() === '');

	const exampleQueries = [
		'RPG games released in 2020',
		'Open world adventure games',
		'Card game based on the Witcher universe'
	];

	function setExampleQuery(text: string) {
		searchQuery = text;
	}

	async function searchGames() {
		if (searchDisabled) return;
		currentPage = 1;
		games = [];
		loading = true;
		error = null;

		try {
			const requestBody: UserState = {
				query: searchQuery,
				use_vector_search: useVectorSearch,
				pagination_metadata: {
					page: currentPage,
					page_size: pageSize,
					has_next_page: false
				}
			};
			const response = await fetch(PUBLIC_API_URL, {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json'
				},
				body: JSON.stringify(requestBody)
			});

			if (!response.ok) {
				throw new Error(`Search failed with status: ${response.status}`);
			}

			const data: UserState = await response.json();

			// Check if query was allowed
			if (data.violation) {
				throw new Error(data.violation);
			}

			searchResponse = data;
			games = data.result as Game[];
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to search games';
			games = [];
			searchResponse = null;
		} finally {
			loading = false;
		}
	}

	async function changePage(page: number) {
		if (!searchResponse || loading) return;

		currentPage = page;
		loading = true;
		error = null;

		try {
			const requestBody: UserState = {
				...searchResponse,
				pagination_metadata: {
					page: page,
					page_size: pageSize,
					has_next_page: searchResponse.pagination_metadata.has_next_page
				}
			};

			const response = await fetch(PUBLIC_API_URL, {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json'
				},
				body: JSON.stringify(requestBody)
			});

			if (!response.ok) {
				throw new Error(`Pagination failed with status: ${response.status}`);
			}

			const data: UserState = await response.json();

			if (data.violation) {
				throw new Error(data.violation);
			}

			searchResponse = data;
			games = data.result as Game[];
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to load page';
			currentPage = searchResponse.pagination_metadata.page; // Reset to previous page
		} finally {
			loading = false;
		}
	}

	function handlePageSizeChange(newPageSize: number) {
		if (loading) return;

		pageSize = newPageSize;
		// If we have search results, restart the search with the new page size
		if (searchResponse) {
			changePage(currentPage);
		}
	}

	function handleSubmit(event: Event) {
		event.preventDefault();
		searchGames();
	}

	function handleKeyDown(event: KeyboardEvent) {
		if (event.key === 'Enter' && !event.shiftKey) {
			event.preventDefault();
			searchGames();
		}
	}
</script>

<svelte:head>
	<title>Gamesearch</title>
</svelte:head>

<div class="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
	<!-- Header -->
	<header class="border-b border-white/10 bg-black/20 backdrop-blur-sm">
		<div class="container mx-auto px-6 py-4">
			<div class="flex items-center justify-between">
				<h1
					class="bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-2xl font-bold text-transparent"
				>
					🎮 Gamesearch
				</h1>
			</div>
		</div>
	</header>

	<!-- Main Content -->
	<main class="container mx-auto px-6 py-8">
		<!-- Search Section -->
		<div class="mx-auto max-w-4xl">
			<div class="mb-8 text-center">
				<h2 class="mb-4 text-4xl font-bold text-white">
					Find Your Next
					<span class="bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">
						Gaming Adventure
					</span>
				</h2>
				<p class="text-lg text-slate-300">
					Search through thousands of games using natural language or find similar games with
					AI-powered recommendations
				</p>
			</div>

			<!-- Search Form -->
			<form onsubmit={handleSubmit} class="mb-8">
				<div class="group relative">
					<div
						class="absolute -inset-0.5 rounded-xl bg-gradient-to-r from-purple-600 to-pink-600 opacity-20 blur transition duration-300 group-hover:opacity-30"
					></div>
					<div class="relative rounded-xl bg-slate-800/50 p-1 backdrop-blur-sm">
						<div class="flex items-center gap-4 p-3">
							<div class="flex-1">
								<textarea
									bind:value={searchQuery}
									onkeydown={handleKeyDown}
									placeholder="Search for games by title, genre, release date, or describe the type of game you want to play..."
									class="w-full resize-none bg-transparent text-white placeholder-slate-400 focus:outline-none"
									rows="1"
									style="field-sizing: content; max-height: 120px;"
								></textarea>
							</div>

							<button
								type="submit"
								disabled={searchDisabled}
								class="group relative overflow-hidden rounded-lg bg-gradient-to-r from-purple-600 to-pink-600 px-6 py-3 font-semibold text-white transition-all duration-200 hover:scale-105 hover:shadow-lg hover:shadow-purple-500/25 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:scale-100"
							>
								{#if loading}
									<div class="flex items-center gap-2">
										<div
											class="h-4 w-4 animate-spin rounded-full border-2 border-white/20 border-t-white"
										></div>
										Searching...
									</div>
								{:else}
									<div class="flex items-center gap-2">
										<span class="icon-[material-symbols--search-rounded] text-lg"></span>
										Search
									</div>
								{/if}
							</button>
						</div>
					</div>
				</div>
			</form>

			<!-- Search Type Toggle -->
			<div class="mb-6">
				<div class="mb-3 flex items-center justify-center gap-2">
					<div
						class="flex rounded-lg border border-slate-700/50 bg-slate-800/50 p-1 backdrop-blur-sm"
					>
						<button
							type="button"
							onclick={() => (useVectorSearch = false)}
							aria-pressed={!useVectorSearch}
							aria-label="Use structured search"
							class={`flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-all duration-200 ${
								!useVectorSearch
									? 'bg-gradient-to-r from-purple-600 to-purple-500 text-white shadow-lg shadow-purple-500/25'
									: 'text-slate-400 hover:bg-slate-700/30 hover:text-slate-300'
							}`}
						>
							<span class="icon-[material-symbols--database-outline] text-lg"></span>
							Structured Search
						</button>
						<button
							type="button"
							onclick={() => (useVectorSearch = true)}
							aria-pressed={useVectorSearch}
							aria-label="Use AI similarity search"
							class={`flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-all duration-200 ${
								useVectorSearch
									? 'bg-gradient-to-r from-pink-600 to-pink-500 text-white shadow-lg shadow-pink-500/25'
									: 'text-slate-400 hover:bg-slate-700/30 hover:text-slate-300'
							}`}
						>
							<span class="icon-[material-symbols--auto-awesome] text-lg"></span>
							AI Similarity Search
						</button>
					</div>
				</div>

				<!-- Search Type Description -->
				<div class="text-center text-sm text-slate-400">
					{#if useVectorSearch}
						<div class="flex items-center justify-center gap-2">
							<span class="icon-[material-symbols--psychology] text-pink-400"></span>
							<span>AI will find games with similar themes, gameplay, or concepts</span>
						</div>
					{:else}
						<div class="flex items-center justify-center gap-2">
							<span class="icon-[material-symbols--filter-list] text-purple-400"></span>
							<span>AI will create precise database queries based on your criteria</span>
						</div>
					{/if}
				</div>
			</div>

			<!-- Example Queries -->
			{#if games.length === 0 && !loading}
				<div class="mb-8">
					<h3 class="mb-4 text-center text-lg font-medium text-slate-300">
						Try these example searches:
					</h3>
					<div class="flex flex-wrap justify-center gap-3">
						{#each exampleQueries as query}
							<button
								onclick={() => setExampleQuery(query)}
								class="rounded-full border border-slate-600 px-4 py-2 text-sm text-slate-300 transition-all duration-200 hover:border-purple-500 hover:bg-purple-500/10 hover:text-purple-300"
							>
								{query}
							</button>
						{/each}
					</div>
				</div>
			{/if}

			<!-- Error Display -->
			{#if error && !loading}
				<div class="mb-6 rounded-lg border border-red-500/20 bg-red-500/10 p-4">
					<div class="flex items-center gap-3 text-red-400">
						<span class="icon-[material-symbols--error-outline] text-xl"></span>
						<div>
							<p class="font-medium">Search Error</p>
							<p class="text-sm text-red-300">{error}</p>
						</div>
					</div>
				</div>
			{/if}
		</div>

		<!-- Results Section -->
		{#if games.length > 0}
			<div class="mx-auto max-w-6xl">
				<div class="mb-6">
					<div class="mb-3 flex items-center justify-between">
						<div>
							<h3 class="text-xl font-semibold text-white">Search Results</h3>
							<div class="mt-1 text-sm text-slate-400">
								{#if searchResponse}
									Page {searchResponse.pagination_metadata.page} • {games.length} game{games.length !==
									1
										? 's'
										: ''} shown
									{#if searchResponse.pagination_metadata.has_next_page}
										• More available
									{/if}
								{:else}
									{games.length} game{games.length !== 1 ? 's' : ''} found
								{/if}
							</div>
						</div>

						<div class="flex items-center gap-4">
							{#if searchResponse && searchResponse.pagination_metadata.page > 1}
								<div class="flex items-center gap-2 text-xs text-green-400">
									<span class="icon-[material-symbols--speed] text-sm"></span>
									<span>Optimized pagination active</span>
								</div>
							{/if}
							<PageSizeSelector
								{pageSize}
								onPageSizeChange={handlePageSizeChange}
								disabled={loading}
							/>
						</div>
					</div>

					<!-- Search Context Info -->
					{#if searchResponse}
						<div class="rounded-lg border border-slate-700/30 bg-slate-800/20 p-3">
							<div class="flex items-center justify-between text-sm">
								<div class="flex items-center gap-4">
									<div class="flex items-center gap-2">
										<span class="icon-[material-symbols--search] text-slate-400"></span>
										<span class="text-slate-300">"{searchQuery}"</span>
									</div>
									<div class="flex items-center gap-2">
										{#if searchResponse.use_vector_search}
											<span class="icon-[material-symbols--psychology] text-pink-400"></span>
											<span class="text-pink-300">AI Similarity Search</span>
										{:else}
											<span class="icon-[material-symbols--filter-list] text-purple-400"></span>
											<span class="text-purple-300">Structured Search</span>
										{/if}
									</div>
								</div>
								{#if searchResponse.pagination_metadata.page > 1}
									<div class="flex items-center gap-2 text-green-400">
										<span class="icon-[material-symbols--bolt] text-sm"></span>
										<span class="text-xs">Fast pagination (no AI re-processing)</span>
									</div>
								{/if}
							</div>
						</div>
					{/if}
				</div>

				<div class="relative">
					<div class="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
						{#each games as game (game._id)}
							<GameCard {game} />
						{/each}
					</div>

					<!-- Pagination -->
					{#if searchResponse}
						<Pagination
							currentPage={searchResponse.pagination_metadata.page}
							hasNextPage={searchResponse.pagination_metadata.has_next_page}
							pageSize={searchResponse.pagination_metadata.page_size}
							onPageChange={changePage}
							{loading}
						/>
					{/if}
				</div>
			</div>
		{/if}

		<!-- Loading State -->
		{#if loading}
			<div class="mx-auto max-w-6xl">
				<!-- Loading Message -->
				<div class="mb-6 text-center">
					<div
						class="inline-flex items-center gap-3 rounded-lg bg-slate-800/50 px-4 py-3 text-white backdrop-blur-sm"
					>
						<div
							class="h-4 w-4 animate-spin rounded-full border-2 border-white/20 border-t-white"
						></div>
						<span class="text-sm font-medium">
							{#if currentPage === 1}
								{#if useVectorSearch}
									AI is analyzing your query and finding similar games...
								{:else}
									AI is processing your query and building database filters...
								{/if}
							{:else}
								Loading page {currentPage} using optimized pagination...
							{/if}
						</span>
					</div>
				</div>

				<div class="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
					{#each Array(pageSize) as _, i}
						<div
							class="animate-pulse rounded-xl bg-slate-800/30 p-6"
							style="animation-delay: {i * 100}ms"
						>
							<div class="mb-4 h-6 rounded bg-slate-700/50"></div>
							<div class="mb-2 h-4 rounded bg-slate-700/30"></div>
							<div class="mb-2 h-4 w-3/4 rounded bg-slate-700/30"></div>
							<div class="h-4 w-1/2 rounded bg-slate-700/30"></div>
						</div>
					{/each}
				</div>
			</div>
		{/if}
	</main>
</div>
