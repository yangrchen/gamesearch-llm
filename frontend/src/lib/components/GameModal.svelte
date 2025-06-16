<script lang="ts">
	import type { Game } from '$lib/types';

	let { game, isOpen = $bindable(false) }: { game: Game | null; isOpen: boolean } = $props();

	function closeModal() {
		isOpen = false;
	}

	function handleKeydown(event: KeyboardEvent) {
		if (event.key === 'Escape') {
			closeModal();
		}
	}

	function handleBackdropClick(event: MouseEvent) {
		if (event.target === event.currentTarget) {
			closeModal();
		}
	}

	function formatDate(dateString: string): string {
		if (!dateString) return 'Unknown';
		try {
			const date = new Date(dateString);
			return date.toLocaleDateString('en-US', {
				year: 'numeric',
				month: 'long',
				day: 'numeric'
			});
		} catch {
			return 'Unknown';
		}
	}

	function formatLastUpdated(dateString: string): string {
		if (!dateString) return 'Unknown';
		try {
			const date = new Date(dateString);
			return date.toLocaleDateString('en-US', {
				year: 'numeric',
				month: 'short',
				day: 'numeric',
				hour: '2-digit',
				minute: '2-digit'
			});
		} catch {
			return 'Unknown';
		}
	}
</script>

<svelte:window on:keydown={handleKeydown} />

{#if isOpen && game}
	<!-- Modal backdrop -->
	<div
		class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
		onclick={handleBackdropClick}
		onkeydown={handleKeydown}
		role="dialog"
		tabindex="0"
		aria-modal="true"
		aria-labelledby="modal-title"
	>
		<!-- Modal content -->
		<div
			class="relative mx-4 max-h-[90vh] w-full max-w-4xl overflow-hidden rounded-2xl border border-slate-600/30 bg-slate-900/95 shadow-2xl shadow-purple-500/10 backdrop-blur-md"
		>
			<!-- Header -->
			<div class="sticky top-0 z-10 border-b border-slate-700/30 bg-slate-900/90 px-8 py-6">
				<div class="flex items-start justify-between">
					<div>
						<h2 id="modal-title" class="text-3xl font-bold text-white">
							{game.name}
						</h2>
						<div class="mt-2 flex items-center gap-2 text-slate-400">
							<span class="icon-[material-symbols--calendar-today] text-base"></span>
							<span>{formatDate(game.first_release_date)}</span>
						</div>
					</div>
					<button
						onclick={closeModal}
						class="rounded-full p-2 text-slate-400 transition-colors hover:bg-slate-700/50 hover:text-white"
						aria-label="Close modal"
					>
						<span class="icon-[material-symbols--close] text-2xl"></span>
					</button>
				</div>
			</div>

			<!-- Body -->
			<div class="max-h-[calc(90vh-120px)] overflow-y-auto px-8 py-6">
				<div class="space-y-8">
					<!-- Game ID -->
					<div class="flex items-center gap-2 text-sm text-slate-500">
						<span class="icon-[material-symbols--game-controller] text-base"></span>
						<span>Game ID: {game._id}</span>
					</div>

					<!-- Genres Section -->
					{#if game.genres && game.genres.length > 0}
						<div>
							<h3 class="mb-4 flex items-center gap-2 text-xl font-semibold text-white">
								<span class="icon-[material-symbols--category] text-purple-400"></span>
								Genres
							</h3>
							<div class="flex flex-wrap gap-3">
								{#each game.genres as genre}
									<span
										class="rounded-full border border-purple-500/30 bg-purple-500/20 px-4 py-2 text-sm font-medium text-purple-300"
									>
										{genre}
									</span>
								{/each}
							</div>
						</div>
					{/if}

					<!-- Franchises Section -->
					{#if game.franchises && game.franchises.length > 0}
						<div>
							<h3 class="mb-4 flex items-center gap-2 text-xl font-semibold text-white">
								<span class="icon-[material-symbols--movie-filter] text-pink-400"></span>
								Franchises
							</h3>
							<div class="space-y-2">
								{#each game.franchises as franchise}
									<div
										class="rounded-lg border border-pink-500/20 bg-pink-500/10 px-4 py-3 text-pink-300"
									>
										{franchise}
									</div>
								{/each}
							</div>
						</div>
					{/if}

					<!-- Summary Section -->
					<div>
						<h3 class="mb-4 flex items-center gap-2 text-xl font-semibold text-white">
							<span class="icon-[material-symbols--description] text-blue-400"></span>
							Description
						</h3>
						<div
							class="rounded-xl border border-slate-700/30 bg-slate-800/30 p-6 leading-relaxed text-slate-300"
						>
							{#if game.summary}
								<p class="whitespace-pre-wrap">{game.summary}</p>
							{:else}
								<p class="text-slate-500 italic">No description available for this game.</p>
							{/if}
						</div>
					</div>

					<!-- Metadata Section -->
					<div>
						<h3 class="mb-4 flex items-center gap-2 text-xl font-semibold text-white">
							<span class="icon-[material-symbols--info] text-emerald-400"></span>
							Information
						</h3>
						<div class="grid gap-4 sm:grid-cols-2">
							<div class="rounded-lg border border-slate-700/30 bg-slate-800/20 p-4">
								<div class="mb-2 text-sm font-medium text-slate-400">Release Date</div>
								<div class="text-white">{formatDate(game.first_release_date)}</div>
							</div>
							<div class="rounded-lg border border-slate-700/30 bg-slate-800/20 p-4">
								<div class="mb-2 text-sm font-medium text-slate-400">Last Updated</div>
								<div class="text-white">{formatLastUpdated(game.last_updated)}</div>
							</div>
						</div>
					</div>
				</div>
			</div>

			<!-- Footer -->
			<div class="sticky bottom-0 border-t border-slate-700/30 bg-slate-900/90 px-8 py-4">
				<div class="flex justify-end">
					<button
						onclick={closeModal}
						class="rounded-lg bg-purple-600 px-6 py-2 font-medium text-white transition-colors hover:bg-purple-700 focus:ring-2 focus:ring-purple-500 focus:ring-offset-2 focus:ring-offset-slate-900 focus:outline-none"
					>
						Close
					</button>
				</div>
			</div>
		</div>
	</div>
{/if}
