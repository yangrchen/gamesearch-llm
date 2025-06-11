<script lang="ts">
	import type { Game } from '$lib/types';

	let { game }: { game: Game } = $props();

	function truncateSummary(summary: string, maxLength = 150): string {
		if (!summary || summary.length <= maxLength) return summary || 'No description available';
		return summary.substring(0, maxLength).trim() + '...';
	}

	function formatDate(dateString: string): string {
		if (!dateString) return 'Unknown';
		try {
			return new Date(dateString).getFullYear().toString();
		} catch {
			return 'Unknown';
		}
	}

	const truncatedSummary = $derived(truncateSummary(game.summary));
	const releaseYear = $derived(formatDate(game.first_release_date));
</script>

<div
	class="group relative overflow-hidden rounded-xl border border-slate-700/30 bg-slate-800/30 backdrop-blur-sm transition-all duration-300 hover:-translate-y-1 hover:border-purple-500/30 hover:bg-slate-800/50 hover:shadow-xl hover:shadow-purple-500/10"
>
	<!-- Hover gradient overlay -->
	<div
		class="absolute inset-0 bg-gradient-to-br from-purple-600/5 to-pink-600/5 opacity-0 transition-opacity duration-300 group-hover:opacity-100"
	></div>

	<div class="relative p-6">
		<!-- Header -->
		<div class="mb-4">
			<h3
				class="mb-2 text-xl font-bold text-white transition-colors duration-200 group-hover:text-purple-300"
			>
				{game.name}
			</h3>
			<div class="flex items-center gap-2 text-sm text-slate-400">
				<span class="icon-[material-symbols--calendar-today] text-base"></span>
				<span>{releaseYear}</span>
			</div>
		</div>

		<!-- Genres -->
		{#if game.genres && game.genres.length > 0}
			<div class="mb-4">
				<div class="flex flex-wrap gap-2">
					{#each game.genres.slice(0, 3) as genre}
						<span
							class="rounded-full border border-purple-500/30 bg-purple-500/20 px-3 py-1 text-xs font-medium text-purple-300"
						>
							{genre}
						</span>
					{/each}
					{#if game.genres.length > 3}
						<span class="rounded-full bg-slate-600/50 px-3 py-1 text-xs text-slate-400">
							+{game.genres.length - 3} more
						</span>
					{/if}
				</div>
			</div>
		{/if}

		<!-- Franchises -->
		{#if game.franchises && game.franchises.length > 0}
			<div class="mb-4">
				<div class="flex items-center gap-2 text-sm">
					<span class="icon-[material-symbols--movie-filter] text-pink-400"></span>
					<span class="text-slate-300">{game.franchises[0]}</span>
					{#if game.franchises.length > 1}
						<span class="text-slate-500">+{game.franchises.length - 1}</span>
					{/if}
				</div>
			</div>
		{/if}

		<!-- Summary -->
		<div class="mb-4">
			<p class="text-sm leading-relaxed text-slate-300">
				{truncatedSummary}
			</p>
		</div>

		<!-- Footer -->
		<div class="flex items-center justify-between border-t border-slate-700/30 pt-4">
			<div class="flex items-center gap-2 text-xs text-slate-500">
				<span class="icon-[material-symbols--game-controller] text-base"></span>
				<span>Game ID: {game._id}</span>
			</div>

			<button
				class="group/btn flex items-center gap-2 rounded-lg bg-purple-600/20 px-3 py-2 text-xs font-medium text-purple-300 transition-all duration-200 hover:bg-purple-600/30 hover:text-purple-200"
			>
				<span>View Details</span>
				<span
					class="icon-[material-symbols--arrow-outward] transition-transform duration-200 group-hover/btn:translate-x-0.5 group-hover/btn:-translate-y-0.5"
				></span>
			</button>
		</div>
	</div>
</div>
