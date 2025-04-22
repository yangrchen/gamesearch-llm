<script lang="ts">
	import type { Game } from '$lib/types';

	let { game }: { game: Game } = $props();

	function truncateSummary(summary: string, maxLength = 150): string {
		if (summary.length <= maxLength) return summary;
		return summary.substring(0, maxLength).trim() + '...';
	}

	const truncatedSummary = $derived(truncateSummary(game.summary));
</script>

<div class="overflow-hidden rounded-lg bg-white shadow-md transition duration-300 hover:shadow-lg">
	<div class="p-6">
		<h2 class="mb-2 text-xl font-bold text-gray-800">{game.name}</h2>
	</div>
</div>
