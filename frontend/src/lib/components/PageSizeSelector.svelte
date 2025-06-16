<script lang="ts">
	interface PageSizeSelectorProps {
		pageSize: number;
		onPageSizeChange: (size: number) => void;
		disabled?: boolean;
	}

	let { pageSize, onPageSizeChange, disabled = false }: PageSizeSelectorProps = $props();

	const pageSizeOptions = [
		{ value: 6, label: '6 per page' },
		{ value: 12, label: '12 per page' },
		{ value: 24, label: '24 per page' },
		{ value: 48, label: '48 per page' }
	];

	let isOpen = $state(false);

	function selectPageSize(size: number) {
		if (disabled) return;
		onPageSizeChange(size);
		isOpen = false;
	}

	function toggleDropdown() {
		if (disabled) return;
		isOpen = !isOpen;
	}

	function handleKeydown(event: KeyboardEvent) {
		if (event.key === 'Escape') {
			isOpen = false;
		}
	}

	// Close dropdown when clicking outside
	function handleClickOutside(event: MouseEvent) {
		const target = event.target as Element;
		if (!target.closest('[data-page-size-selector]')) {
			isOpen = false;
		}
	}

	$effect(() => {
		if (isOpen) {
			document.addEventListener('click', handleClickOutside);
			document.addEventListener('keydown', handleKeydown);

			return () => {
				document.removeEventListener('click', handleClickOutside);
				document.removeEventListener('keydown', handleKeydown);
			};
		}
	});

	const selectedOption = $derived(
		pageSizeOptions.find((option) => option.value === pageSize) || pageSizeOptions[1]
	);
</script>

<div class="relative" data-page-size-selector>
	<button
		type="button"
		onclick={toggleDropdown}
		{disabled}
		class="flex items-center gap-2 rounded-lg border border-slate-600/50 bg-slate-800/30 px-3 py-2 text-sm font-medium text-slate-300 transition-all duration-200 hover:border-purple-500/50 hover:bg-slate-700/50 hover:text-purple-300 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:border-slate-600/50 disabled:hover:bg-slate-800/30 disabled:hover:text-slate-300"
		aria-haspopup="listbox"
		aria-expanded={isOpen}
		aria-label="Select page size"
	>
		<span class="icon-[material-symbols--grid-view] text-base"></span>
		<span>{selectedOption.label}</span>
		<span
			class="icon-[material-symbols--expand-more] transition-transform duration-200 {isOpen
				? 'rotate-180'
				: ''}"
		></span>
	</button>

	{#if isOpen}
		<div
			class="absolute right-0 top-full z-50 mt-2 min-w-full overflow-hidden rounded-lg border border-slate-600/50 bg-slate-800/95 backdrop-blur-sm"
			role="listbox"
			aria-label="Page size options"
		>
			{#each pageSizeOptions as option}
				<button
					type="button"
					onclick={() => selectPageSize(option.value)}
					class="flex w-full items-center gap-3 px-4 py-3 text-left text-sm text-slate-300 transition-colors duration-150 hover:bg-slate-700/50 hover:text-purple-300 {option.value ===
					pageSize
						? 'bg-purple-600/20 text-purple-300'
						: ''}"
					role="option"
					aria-selected={option.value === pageSize}
				>
					<span class="icon-[material-symbols--grid-view] text-base opacity-60"></span>
					<span>{option.label}</span>
					{#if option.value === pageSize}
						<span class="icon-[material-symbols--check] ml-auto text-purple-400"></span>
					{/if}
				</button>
			{/each}
		</div>
	{/if}
</div>
