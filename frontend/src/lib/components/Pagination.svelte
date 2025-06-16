<script lang="ts">
	interface PaginationProps {
		currentPage: number;
		hasNextPage: boolean;
		pageSize: number;
		onPageChange: (page: number) => void;
		loading?: boolean;
	}

	let {
		currentPage,
		hasNextPage,
		pageSize,
		onPageChange,
		loading = false
	}: PaginationProps = $props();

	const hasPreviousPage = $derived(currentPage > 1);
	const startResult = $derived((currentPage - 1) * pageSize + 1);
	const endResult = $derived(currentPage * pageSize);

	function goToPage(page: number) {
		if (loading) return;
		onPageChange(page);
	}

	function goToPrevious() {
		if (hasPreviousPage && !loading) {
			goToPage(currentPage - 1);
		}
	}

	function goToNext() {
		if (hasNextPage && !loading) {
			goToPage(currentPage + 1);
		}
	}

	// Generate page numbers to show (current page and a few around it)
	const visiblePages = $derived(() => {
		const pages = [];
		const maxVisible = 5;

		// Always show current page
		pages.push(currentPage);

		// Add pages before current
		for (let i = 1; i < Math.min(3, currentPage); i++) {
			pages.unshift(currentPage - i);
		}

		// Add pages after current (only if we know they exist or haven't reached the limit)
		for (let i = 1; i < 3; i++) {
			const nextPage = currentPage + i;
			// Only add if we know there are more pages or if it's the immediate next page and hasNextPage is true
			if (i === 1 && hasNextPage) {
				pages.push(nextPage);
			} else if (i > 1 && pages.length < maxVisible) {
				// For pages beyond the immediate next, we can't be sure they exist
				// so we'll be conservative and not show them
				break;
			}
		}

		return pages.sort((a, b) => a - b);
	});
</script>

{#if currentPage > 1 || hasNextPage}
	<div class="flex items-center justify-between border-t border-slate-700/30 pt-6">
		<!-- Results info -->
		<div class="flex items-center gap-2 text-sm text-slate-400">
			<span class="icon-[material-symbols--info-outline]"></span>
			<span>
				Showing results {startResult}–{endResult}
				• Page {currentPage}
			</span>
		</div>

		<!-- Pagination controls -->
		<div class="flex items-center gap-2">
			<!-- Previous button -->
			<button
				onclick={goToPrevious}
				disabled={!hasPreviousPage || loading}
				class="group flex items-center gap-2 rounded-lg border border-slate-600/50 bg-slate-800/30 px-3 py-2 text-sm font-medium text-slate-300 transition-all duration-200 hover:border-purple-500/50 hover:bg-slate-700/50 hover:text-purple-300 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:border-slate-600/50 disabled:hover:bg-slate-800/30 disabled:hover:text-slate-300"
				aria-label="Go to previous page"
			>
				<span
					class="icon-[material-symbols--chevron-left] transition-transform duration-200 group-hover:-translate-x-0.5"
				></span>
				Previous
			</button>

			<!-- Page numbers -->
			<div class="flex items-center gap-1">
				{#each visiblePages as page}
					<button
						onclick={() => goToPage(page)}
						disabled={loading}
						class={`flex h-10 w-10 items-center justify-center rounded-lg text-sm font-medium transition-all duration-200 ${
							page === currentPage
								? 'bg-gradient-to-r from-purple-600 to-pink-600 text-white shadow-lg shadow-purple-500/25'
								: 'border border-slate-600/50 bg-slate-800/30 text-slate-300 hover:border-purple-500/50 hover:bg-slate-700/50 hover:text-purple-300'
						} disabled:cursor-not-allowed disabled:opacity-40`}
						aria-label={page === currentPage ? `Current page ${page}` : `Go to page ${page}`}
						aria-current={page === currentPage ? 'page' : undefined}
					>
						{page}
					</button>
				{/each}
			</div>

			<!-- Next button -->
			<button
				onclick={goToNext}
				disabled={!hasNextPage || loading}
				class="group flex items-center gap-2 rounded-lg border border-slate-600/50 bg-slate-800/30 px-3 py-2 text-sm font-medium text-slate-300 transition-all duration-200 hover:border-purple-500/50 hover:bg-slate-700/50 hover:text-purple-300 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:border-slate-600/50 disabled:hover:bg-slate-800/30 disabled:hover:text-slate-300"
				aria-label="Go to next page"
			>
				Next
				<span
					class="icon-[material-symbols--chevron-right] transition-transform duration-200 group-hover:translate-x-0.5"
				></span>
			</button>
		</div>
	</div>
{/if}

<!-- Loading overlay for pagination -->
{#if loading}
	<div class="absolute inset-0 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm">
		<div class="flex items-center gap-3 rounded-lg bg-slate-800/80 px-4 py-3 text-white">
			<div class="h-4 w-4 animate-spin rounded-full border-2 border-white/20 border-t-white"></div>
			<span class="text-sm font-medium">Loading page {currentPage}...</span>
		</div>
	</div>
{/if}
