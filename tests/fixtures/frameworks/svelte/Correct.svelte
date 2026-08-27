<button aria-label={closeLabel} on:click={close}>×</button>
<label for="q">{searchLabel}</label>
<input id="q" bind:value={query} />
<img src={photo.url} alt={photo.caption} />
