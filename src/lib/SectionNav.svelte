<script lang="ts">
  import Icon from "$lib/Icon.svelte";
  import { SECTIONS, GROUPS, type SectionId } from "$lib/registry";

  type Props = { active?: SectionId; onPick?: (id: SectionId) => void };
  let { active = "playground", onPick = () => {} }: Props = $props();
</script>

<nav class="flex h-full flex-col overflow-y-auto border-r border-line px-2.5 py-4">
  {#each GROUPS as group}
    <div class="mb-4 last:mb-0">
      <span class="label block px-2 pb-1.5">{group}</span>
      {#each SECTIONS.filter((s) => s.group === group) as s}
        <button
          class="relative flex h-8 w-full items-center gap-2.5 rounded-[5px] px-2 text-left text-[12.5px] transition-colors
            {active === s.id
            ? 'bg-nav-active font-medium text-ink'
            : 'text-ink-2 hover:bg-hover hover:text-ink'}"
          onclick={() => onPick(s.id)}
        >
          <Icon name={s.icon} size={13} />
          <span>{s.label}</span>
          {#if active === s.id}
            <span class="absolute top-2 bottom-2 left-0 w-0.5 rounded bg-ink"></span>
          {/if}
        </button>
      {/each}
    </div>
  {/each}
</nav>
